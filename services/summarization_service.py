"""
Summarization service using LiteLLM to generate structured bilingual summaries.
"""
import logging
import json
import asyncio
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import litellm
from litellm import completion

from models import SummaryData, Summaries, TranscriptChunk, ErrorInfo
from app_logging import log_with_context
from config import config

logger = logging.getLogger(__name__)


@dataclass
class SummarizationConfig:
    """Configuration for summarization service."""
    provider: str = "openai/gpt-4o-mini"
    temperature: float = 0.2
    max_tokens: int = 1200
    timeout: int = 30
    max_retries: int = 3
    retry_delay: float = 1.0


class SummarizationService:
    """Service for generating structured summaries using LLM providers."""
    
    def __init__(self, summarization_config: SummarizationConfig = None):
        """Initialize the summarization service."""
        self.config = summarization_config or SummarizationConfig()
        self.prompt_templates = PromptTemplates()
    
    async def summarize_transcript(self, chunks: List[TranscriptChunk], language: str) -> Tuple[Optional[SummaryData], Optional[ErrorInfo]]:
        """
        Summarize transcript chunks into structured format.
        
        Args:
            chunks: List of transcript chunks to summarize
            language: Target language for summary (es/en)
            
        Returns:
            Tuple of (summary_data, error)
        """
        if not chunks:
            return None, ErrorInfo(
                code="NO_CHUNKS",
                message="No transcript chunks provided for summarization"
            )
        
        try:
            log_with_context("info", f"Summarizing {len(chunks)} chunks in {language}")
            
            # Combine chunks into single text
            combined_text = self._combine_chunks(chunks)
            
            # Generate summary using LLM
            summary_text = await self._generate_summary(combined_text, language)
            
            if not summary_text:
                return None, ErrorInfo(
                    code="SUMMARIZATION_FAILED",
                    message="Failed to generate summary from LLM"
                )
            
            # Parse structured summary
            summary_data = self._parse_summary(summary_text, language)
            
            log_with_context("info", f"Successfully generated {language} summary")
            return summary_data, None
            
        except Exception as e:
            log_with_context("error", f"Error summarizing transcript: {str(e)}")
            return None, ErrorInfo(
                code="SUMMARIZATION_ERROR",
                message=f"Unexpected error: {str(e)}"
            )
    
    def _combine_chunks(self, chunks: List[TranscriptChunk]) -> str:
        """Combine transcript chunks into a single text."""
        combined_parts = []
        
        for i, chunk in enumerate(chunks):
            # Add chunk separator for clarity
            if i > 0:
                combined_parts.append(f"\n--- Chunk {i+1} ---\n")
            
            combined_parts.append(chunk.text)
        
        return "".join(combined_parts)
    
    async def _generate_summary(self, text: str, language: str) -> Optional[str]:
        """Generate summary using LLM provider."""
        try:
            # Get prompt template for the language
            prompt = self.prompt_templates.get_summary_prompt(text, language)
            
            # Configure LiteLLM
            litellm.set_verbose = False
            
            # Make API call with retry logic
            for attempt in range(self.config.max_retries):
                try:
                    response = await asyncio.wait_for(
                        completion(
                            model=self.config.provider,
                            messages=[
                                {"role": "user", "content": prompt}
                            ],
                            temperature=self.config.temperature,
                            max_tokens=self.config.max_tokens,
                        ),
                        timeout=self.config.timeout
                    )
                    
                    if response and response.choices:
                        return response.choices[0].message.content
                    
                except asyncio.TimeoutError:
                    log_with_context("warning", f"LLM request timeout (attempt {attempt + 1})")
                    if attempt < self.config.max_retries - 1:
                        await asyncio.sleep(self.config.retry_delay * (2 ** attempt))
                    else:
                        raise
                
                except Exception as e:
                    log_with_context("warning", f"LLM request failed (attempt {attempt + 1}): {str(e)}")
                    if attempt < self.config.max_retries - 1:
                        await asyncio.sleep(self.config.retry_delay * (2 ** attempt))
                    else:
                        raise
            
            return None
            
        except Exception as e:
            log_with_context("error", f"LLM generation failed: {str(e)}")
            return None
    
    def _parse_summary(self, summary_text: str, language: str) -> SummaryData:
        """Parse LLM response into structured summary data."""
        try:
            # Try to parse as JSON first
            if summary_text.strip().startswith('{'):
                return self._parse_json_summary(summary_text)
            
            # Fallback to text parsing
            return self._parse_text_summary(summary_text, language)
            
        except Exception as e:
            log_with_context("warning", f"Error parsing summary: {str(e)}")
            # Return basic summary with the raw text
            return SummaryData(
                topics=[f"Summary in {language}"],
                bullets=[summary_text[:200] + "..." if len(summary_text) > 200 else summary_text],
                quotes=[],
                actions=[]
            )
    
    def _parse_json_summary(self, summary_text: str) -> SummaryData:
        """Parse JSON-formatted summary."""
        try:
            data = json.loads(summary_text)
            
            return SummaryData(
                topics=data.get("topics", []),
                bullets=data.get("bullets", []),
                quotes=data.get("quotes", []),
                actions=data.get("actions", [])
            )
        except json.JSONDecodeError:
            # If JSON parsing fails, fall back to text parsing
            return self._parse_text_summary(summary_text, "en")
    
    def _parse_text_summary(self, summary_text: str, language: str) -> SummaryData:
        """Parse text-formatted summary into structured data."""
        lines = summary_text.strip().split('\n')
        
        topics = []
        bullets = []
        quotes = []
        actions = []
        
        current_section = None
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Detect section headers
            if any(keyword in line.lower() for keyword in ['topic', 'temas', 'puntos clave']):
                current_section = 'topics'
            elif any(keyword in line.lower() for keyword in ['bullet', 'punto', 'resumen']):
                current_section = 'bullets'
            elif any(keyword in line.lower() for keyword in ['quote', 'cita', 'frase']):
                current_section = 'quotes'
            elif any(keyword in line.lower() for keyword in ['action', 'acción', 'tarea']):
                current_section = 'actions'
            else:
                # Add content to current section
                if current_section == 'topics':
                    topics.append(line)
                elif current_section == 'bullets':
                    bullets.append(line)
                elif current_section == 'quotes':
                    quotes.append(line)
                elif current_section == 'actions':
                    actions.append(line)
                else:
                    # Default to bullets if no section detected
                    bullets.append(line)
        
        return SummaryData(
            topics=topics,
            bullets=bullets,
            quotes=quotes,
            actions=actions
        )
    
    async def summarize_bilingual(self, es_chunks: List[TranscriptChunk], en_chunks: List[TranscriptChunk]) -> Tuple[Optional[Summaries], Optional[ErrorInfo]]:
        """
        Generate bilingual summaries from Spanish and English chunks.
        
        Args:
            es_chunks: Spanish transcript chunks
            en_chunks: English transcript chunks
            
        Returns:
            Tuple of (summaries, error)
        """
        try:
            summaries = Summaries()
            
            # Generate Spanish summary if chunks available
            if es_chunks:
                es_summary, es_error = await self.summarize_transcript(es_chunks, "es")
                if es_error:
                    log_with_context("warning", f"Spanish summary failed: {es_error.message}")
                else:
                    summaries.es = es_summary
            
            # Generate English summary if chunks available
            if en_chunks:
                en_summary, en_error = await self.summarize_transcript(en_chunks, "en")
                if en_error:
                    log_with_context("warning", f"English summary failed: {en_error.message}")
                else:
                    summaries.en = en_summary
            
            # Check if we got at least one summary
            if not summaries.es and not summaries.en:
                return None, ErrorInfo(
                    code="NO_SUMMARIES",
                    message="Failed to generate summaries in any language"
                )
            
            return summaries, None
            
        except Exception as e:
            log_with_context("error", f"Error generating bilingual summaries: {str(e)}")
            return None, ErrorInfo(
                code="BILINGUAL_SUMMARIZATION_ERROR",
                message=f"Unexpected error: {str(e)}"
            )


class PromptTemplates:
    """Prompt templates for different languages and use cases."""
    
    def get_summary_prompt(self, text: str, language: str) -> str:
        """Get appropriate prompt template for the language."""
        if language == "es":
            return self._get_spanish_prompt(text)
        else:
            return self._get_english_prompt(text)
    
    def _get_spanish_prompt(self, text: str) -> str:
        """Get Spanish prompt template."""
        return f"""Analiza el siguiente texto de un video de YouTube y genera un resumen estructurado en español.

Texto del video:
{text}

Por favor, proporciona un resumen en formato JSON con las siguientes secciones:
- "topics": Lista de temas principales (máximo 5)
- "bullets": Puntos clave del contenido (máximo 8)
- "quotes": Frases o citas notables (máximo 3)
- "actions": Acciones o pasos recomendados (máximo 5)

Responde únicamente con el JSON, sin texto adicional."""

    def _get_english_prompt(self, text: str) -> str:
        """Get English prompt template."""
        return f"""Analyze the following YouTube video transcript and generate a structured summary in English.

Video transcript:
{text}

Please provide a summary in JSON format with the following sections:
- "topics": List of main topics (maximum 5)
- "bullets": Key points from the content (maximum 8)
- "quotes": Notable quotes or phrases (maximum 3)
- "actions": Recommended actions or steps (maximum 5)

Respond only with the JSON, no additional text."""


# Global instances
default_summarizer = SummarizationService()
summarizer_with_high_temp = SummarizationService(
    SummarizationConfig(temperature=0.7, max_tokens=1500)
)
summarizer_with_low_temp = SummarizationService(
    SummarizationConfig(temperature=0.1, max_tokens=800)
)
