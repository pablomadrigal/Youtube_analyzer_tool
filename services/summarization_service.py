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

from models import SummaryData, Summaries, TranscriptChunk, ErrorInfo, FrameworkData
from app_logging import log_with_context
from config import config
from .utils import RetryManager

logger = logging.getLogger(__name__)


@dataclass
class SummarizationConfig:
    """Configuration for summarization service."""
    provider: str = "openai/gpt-4o-mini"
    temperature: float = 0.2
    max_tokens: int = 2000  # Increased for comprehensive summaries
    timeout: int = 60  # Increased timeout for longer processing
    max_retries: int = 3
    retry_delay: float = 1.0


class SummarizationService:
    """Service for generating structured summaries using LLM providers."""
    
    def __init__(self, summarization_config: SummarizationConfig = None):
        """Initialize the summarization service."""
        self.config = summarization_config or SummarizationConfig()
        self.prompt_templates = PromptTemplates()
        self.retry_manager = RetryManager(
            max_retries=self.config.max_retries,
            base_delay=self.config.retry_delay
        )
    
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
            
            # If single chunk, process directly
            if len(chunks) == 1:
                chunk = chunks[0]
                chunk_info = {
                    "chunk_index": 1,
                    "total_chunks": 1,
                    "start_time": chunk.start_time,
                    "end_time": chunk.end_time,
                    "is_final_chunk": True
                }
                
                summary_text = await self.retry_manager.execute_with_retry(
                    self._make_llm_request, chunk.text, language, chunk_info
                )
                
                if not summary_text:
                    return None, ErrorInfo(
                        code="SUMMARIZATION_FAILED",
                        message="Failed to generate summary from LLM"
                    )
                
                summary_data = self._parse_summary(summary_text, language)
                log_with_context("info", f"Successfully generated {language} summary for single chunk")
                return summary_data, None
            
            # For multiple chunks, process each individually and combine
            chunk_summaries = []
            all_key_insights = []
            all_frameworks = []
            all_key_moments = []
            
            for i, chunk in enumerate(chunks):
                chunk_info = {
                    "chunk_index": i + 1,
                    "total_chunks": len(chunks),
                    "start_time": chunk.start_time,
                    "end_time": chunk.end_time,
                    "is_final_chunk": (i == len(chunks) - 1)
                }
                
                summary_text = await self.retry_manager.execute_with_retry(
                    self._make_llm_request, chunk.text, language, chunk_info
                )
                
                if summary_text:
                    chunk_data = self._parse_summary(summary_text, language)
                    chunk_summaries.append(chunk_data)
                    
                    # Collect insights, frameworks, and moments
                    all_key_insights.extend(chunk_data.key_insights)
                    all_frameworks.extend(chunk_data.frameworks)
                    all_key_moments.extend(chunk_data.key_moments)
            
            if not chunk_summaries:
                return None, ErrorInfo(
                    code="SUMMARIZATION_FAILED",
                    message="Failed to generate summaries for any chunks"
                )
            
            # Combine summaries into final comprehensive summary
            combined_summary = self._combine_chunk_summaries(chunk_summaries, all_key_insights, all_frameworks, all_key_moments)
            
            log_with_context("info", f"Successfully generated {language} summary from {len(chunks)} chunks")
            return combined_summary, None
            
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
    
    async def _make_llm_request(self, text: str, language: str, chunk_info: dict = None) -> Optional[str]:
        """Make LLM request for summary generation."""
        # Get prompt template for the language with chunk context
        prompt = self.prompt_templates.get_summary_prompt(text, language, chunk_info)
        
        # Configure LiteLLM
        litellm.set_verbose = False
        
        # Make API call
        response = await asyncio.wait_for(
            asyncio.to_thread(
                completion,
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
        
        return None
    
    def _combine_chunk_summaries(self, chunk_summaries: List[SummaryData], all_insights: List[str], 
                                all_frameworks: List, all_moments: List[str]) -> SummaryData:
        """Combine multiple chunk summaries into a comprehensive summary."""
        # Create executive summary from first and last chunk summaries
        executive_summary_parts = []
        if chunk_summaries:
            executive_summary_parts.append(chunk_summaries[0].summary)
            if len(chunk_summaries) > 1:
                executive_summary_parts.append(f"Este análisis completo cubre {len(chunk_summaries)} secciones principales del video.")
        
        # Deduplicate and limit insights
        unique_insights = list(dict.fromkeys(all_insights))  # Preserve order, remove duplicates
        limited_insights = unique_insights[:12]  # Limit to 12 insights
        
        # Deduplicate frameworks by name
        unique_frameworks = {}
        for framework in all_frameworks:
            if framework.name not in unique_frameworks:
                unique_frameworks[framework.name] = framework
        frameworks_list = list(unique_frameworks.values())
        
        # Combine and deduplicate key moments
        unique_moments = list(dict.fromkeys(all_moments))
        
        return SummaryData(
            summary="\n\n".join(executive_summary_parts) if executive_summary_parts else "Resumen no disponible",
            key_insights=limited_insights,
            frameworks=frameworks_list,
            key_moments=unique_moments,
            # Legacy fields for backward compatibility
            topics=[],  # Will be populated from key_moments if needed
            bullets=limited_insights[:8],  # Use first 8 insights as bullets
            quotes=[],
            actions=[]
        )

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
                summary=summary_text[:500] + "..." if len(summary_text) > 500 else summary_text,
                key_insights=[summary_text[:200] + "..." if len(summary_text) > 200 else summary_text],
                frameworks=[],
                key_moments=[],
                topics=[f"Summary in {language}"],
                bullets=[summary_text[:200] + "..." if len(summary_text) > 200 else summary_text],
                quotes=[],
                actions=[]
            )
    
    def _parse_json_summary(self, summary_text: str) -> SummaryData:
        """Parse JSON-formatted summary."""
        try:
            data = json.loads(summary_text)
            
            # Parse frameworks if present
            frameworks = []
            if "frameworks" in data:
                for framework_data in data["frameworks"]:
                    if isinstance(framework_data, dict):
                        from models import FrameworkData
                        frameworks.append(FrameworkData(
                            name=framework_data.get("name", ""),
                            description=framework_data.get("description", ""),
                            steps=framework_data.get("steps", [])
                        ))
            
            return SummaryData(
                summary=data.get("summary", ""),
                key_insights=data.get("key_insights", []),
                frameworks=frameworks,
                key_moments=data.get("key_moments", []),
                # Legacy fields for backward compatibility
                topics=data.get("topics", []),
                bullets=data.get("bullets", []),
                quotes=data.get("quotes", []),
                actions=data.get("actions", [])
            )
        except json.JSONDecodeError:
            # If JSON parsing fails, fall back to text parsing
            return self._parse_text_summary(summary_text, "en")
        except Exception as e:
            log_with_context("warning", f"Error parsing JSON summary: {str(e)}")
            return self._parse_text_summary(summary_text, "en")
    
    def _parse_text_summary(self, summary_text: str, language: str) -> SummaryData:
        """Parse text-formatted summary into structured data."""
        lines = summary_text.strip().split('\n')
        
        summary = ""
        key_insights = []
        frameworks = []
        key_moments = []
        topics = []
        bullets = []
        quotes = []
        actions = []
        
        current_section = None
        current_framework = None
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Detect section headers
            if any(keyword in line.lower() for keyword in ['summary', 'resumen', 'executive summary']):
                current_section = 'summary'
            elif any(keyword in line.lower() for keyword in ['insight', 'insights', 'insight clave']):
                current_section = 'key_insights'
            elif any(keyword in line.lower() for keyword in ['framework', 'frameworks', 'método', 'métodos']):
                current_section = 'frameworks'
            elif any(keyword in line.lower() for keyword in ['moment', 'moments', 'momento', 'momentos']):
                current_section = 'key_moments'
            elif any(keyword in line.lower() for keyword in ['topic', 'temas', 'puntos clave']):
                current_section = 'topics'
            elif any(keyword in line.lower() for keyword in ['bullet', 'punto', 'resumen']):
                current_section = 'bullets'
            elif any(keyword in line.lower() for keyword in ['quote', 'cita', 'frase']):
                current_section = 'quotes'
            elif any(keyword in line.lower() for keyword in ['action', 'acción', 'tarea']):
                current_section = 'actions'
            else:
                # Add content to current section
                if current_section == 'summary':
                    summary += line + " "
                elif current_section == 'key_insights':
                    key_insights.append(line)
                elif current_section == 'frameworks':
                    # Simple framework parsing - could be enhanced
                    if line.startswith('Name:') or line.startswith('Nombre:'):
                        if current_framework:
                            frameworks.append(current_framework)
                        from models import FrameworkData
                        current_framework = FrameworkData(name=line.split(':', 1)[1].strip(), description="", steps=[])
                    elif line.startswith('Description:') or line.startswith('Descripción:'):
                        if current_framework:
                            current_framework.description = line.split(':', 1)[1].strip()
                    elif line.startswith('Steps:') or line.startswith('Pasos:'):
                        if current_framework:
                            current_framework.steps = [s.strip() for s in line.split(':', 1)[1].split(',')]
                    elif current_framework and line.startswith('-'):
                        current_framework.steps.append(line[1:].strip())
                elif current_section == 'key_moments':
                    key_moments.append(line)
                elif current_section == 'topics':
                    topics.append(line)
                elif current_section == 'bullets':
                    bullets.append(line)
                elif current_section == 'quotes':
                    quotes.append(line)
                elif current_section == 'actions':
                    actions.append(line)
                else:
                    # Default to key_insights if no section detected
                    key_insights.append(line)
        
        # Add final framework if exists
        if current_framework:
            frameworks.append(current_framework)
        
        # Use the full text as summary if no specific summary section found
        if not summary.strip():
            summary = summary_text[:500] + "..." if len(summary_text) > 500 else summary_text
        
        return SummaryData(
            summary=summary.strip(),
            key_insights=key_insights,
            frameworks=frameworks,
            key_moments=key_moments,
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

    def generate_markdown_summary(self, summary_data: SummaryData, language: str = "en", 
                                 video_title: str = "", video_url: str = "") -> str:
        """
        Generate markdown document from summary data.
        
        Args:
            summary_data: Summary data to convert to markdown
            language: Language for the markdown (es/en)
            video_title: Video title for the header
            video_url: Video URL for reference
            
        Returns:
            Markdown formatted string
        """
        if language == "es":
            return self._generate_spanish_markdown(summary_data, video_title, video_url)
        else:
            return self._generate_english_markdown(summary_data, video_title, video_url)

    def _generate_english_markdown(self, summary_data: SummaryData, video_title: str, video_url: str) -> str:
        """Generate English markdown from summary data."""
        markdown_parts = []
        
        # Header
        if video_title:
            markdown_parts.append(f"# {video_title}")
            markdown_parts.append("")
        if video_url:
            markdown_parts.append(f"**Video URL:** {video_url}")
            markdown_parts.append("")
        
        # Executive Summary
        markdown_parts.append("## Executive Summary")
        markdown_parts.append("")
        markdown_parts.append(summary_data.summary)
        markdown_parts.append("")
        
        # Key Insights
        if summary_data.key_insights:
            markdown_parts.append("## Key Insights")
            markdown_parts.append("")
            for i, insight in enumerate(summary_data.key_insights, 1):
                markdown_parts.append(f"### {i}. {self._extract_insight_title(insight)}")
                markdown_parts.append("")
                markdown_parts.append(insight)
                markdown_parts.append("")
        
        # Frameworks
        if summary_data.frameworks:
            markdown_parts.append("## Actionable Frameworks")
            markdown_parts.append("")
            for framework in summary_data.frameworks:
                markdown_parts.append(f"### {framework.name}")
                markdown_parts.append("")
                if framework.description:
                    markdown_parts.append(f"**Description:** {framework.description}")
                    markdown_parts.append("")
                if framework.steps:
                    markdown_parts.append("**Steps:**")
                    markdown_parts.append("")
                    for i, step in enumerate(framework.steps, 1):
                        markdown_parts.append(f"{i}. {step}")
                    markdown_parts.append("")
        
        # Key Moments
        if summary_data.key_moments:
            markdown_parts.append("## Key Moments")
            markdown_parts.append("")
            for i, moment in enumerate(summary_data.key_moments, 1):
                markdown_parts.append(f"{i}. {moment}")
            markdown_parts.append("")
        
        return "\n".join(markdown_parts)

    def _generate_spanish_markdown(self, summary_data: SummaryData, video_title: str, video_url: str) -> str:
        """Generate Spanish markdown from summary data."""
        markdown_parts = []
        
        # Header
        if video_title:
            markdown_parts.append(f"# {video_title}")
            markdown_parts.append("")
        if video_url:
            markdown_parts.append(f"**URL del Video:** {video_url}")
            markdown_parts.append("")
        
        # Executive Summary
        markdown_parts.append("## Resumen Ejecutivo")
        markdown_parts.append("")
        markdown_parts.append(summary_data.summary)
        markdown_parts.append("")
        
        # Key Insights
        if summary_data.key_insights:
            markdown_parts.append("## Insights Clave")
            markdown_parts.append("")
            for i, insight in enumerate(summary_data.key_insights, 1):
                markdown_parts.append(f"### {i}. {self._extract_insight_title(insight)}")
                markdown_parts.append("")
                markdown_parts.append(insight)
                markdown_parts.append("")
        
        # Frameworks
        if summary_data.frameworks:
            markdown_parts.append("## Frameworks Accionables")
            markdown_parts.append("")
            for framework in summary_data.frameworks:
                markdown_parts.append(f"### {framework.name}")
                markdown_parts.append("")
                if framework.description:
                    markdown_parts.append(f"**Descripción:** {framework.description}")
                    markdown_parts.append("")
                if framework.steps:
                    markdown_parts.append("**Pasos:**")
                    markdown_parts.append("")
                    for i, step in enumerate(framework.steps, 1):
                        markdown_parts.append(f"{i}. {step}")
                    markdown_parts.append("")
        
        # Key Moments
        if summary_data.key_moments:
            markdown_parts.append("## Momentos Clave")
            markdown_parts.append("")
            for i, moment in enumerate(summary_data.key_moments, 1):
                markdown_parts.append(f"{i}. {moment}")
            markdown_parts.append("")
        
        return "\n".join(markdown_parts)

    def _extract_insight_title(self, insight: str) -> str:
        """Extract a title from insight text (first few words)."""
        words = insight.split()
        if len(words) <= 8:
            return insight
        return " ".join(words[:8]) + "..."


class PromptTemplates:
    """Enhanced prompt templates for comprehensive video analysis."""
    
    def get_summary_prompt(self, text: str, language: str, chunk_info: dict = None) -> str:
        """Get appropriate prompt template for the language with enhanced analysis."""
        if language == "es":
            return self._get_spanish_prompt(text, chunk_info)
        else:
            return self._get_english_prompt(text, chunk_info)
    
    def _get_spanish_prompt(self, text: str, chunk_info: dict = None) -> str:
        """Get comprehensive Spanish prompt template."""
        chunk_context = ""
        if chunk_info:
            chunk_context = f"\nCONTEXTO DEL FRAGMENTO:\n"
            chunk_context += f"- Fragmento {chunk_info.get('chunk_index', 1)} de {chunk_info.get('total_chunks', 1)}\n"
            chunk_context += f"- Tiempo: {self._format_time(chunk_info.get('start_time', 0))} - {self._format_time(chunk_info.get('end_time', 0))}\n"
            chunk_context += f"- Es fragmento final: {'Sí' if chunk_info.get('is_final_chunk', False) else 'No'}\n\n"
        
        return f"""Eres un analista experto de contenido de YouTube especializado en extraer insights valiosos y accionables de videos largos.

{chunk_context}INSTRUCCIONES CRÍTICAS:
- Responde ÚNICAMENTE con JSON válido, sin texto adicional, comentarios o formato markdown
- Tu respuesta completa debe ser JSON válido que se pueda parsear directamente
- Enfócate en insights prácticos y accionables que proporcionen valor real
- Cada insight debe ser un párrafo estructurado (3-5 oraciones) explicando el concepto completamente
- Incluye ejemplos específicos, estrategias y razonamiento del video
- Usa el contexto completo para identificar temas generales y conexiones

FORMATO JSON REQUERIDO:
{{
  "summary": "Resumen ejecutivo de 2-3 párrafos del mensaje central y valor del contenido",
  "key_insights": [
    "Párrafo detallado explicando el primer insight principal con contexto y ejemplos...",
    "Otro párrafo estructurado sobre el segundo concepto clave..."
  ],
  "frameworks": [
    {{
      "name": "Nombre del Framework",
      "description": "Qué hace y por qué es útil",
      "steps": [
        "Paso 1 con detalles específicos",
        "Paso 2 con contexto y aplicación"
      ]
    }}
  ],
  "key_moments": [
    "Primer tema principal introducido",
    "Transición o desarrollo clave",
    "Conclusión importante o llamada a la acción"
  ]
}}

GUÍAS ESPECÍFICAS:
- Genera 8-12 insights clave como párrafos detallados (no puntos de lista)
- Los frameworks deben incluir pasos claros y contexto detallado
- Presenta los momentos clave en orden cronológico como aparecen en el video
- Enfócate en contenido práctico y accionable que proporcione valor real
- Si es un fragmento de un video largo, considera el contexto del fragmento

Transcripción del video:

{text}"""

    def _get_english_prompt(self, text: str, chunk_info: dict = None) -> str:
        """Get comprehensive English prompt template."""
        chunk_context = ""
        if chunk_info:
            chunk_context = f"\nCHUNK CONTEXT:\n"
            chunk_context += f"- Chunk {chunk_info.get('chunk_index', 1)} of {chunk_info.get('total_chunks', 1)}\n"
            chunk_context += f"- Time: {self._format_time(chunk_info.get('start_time', 0))} - {self._format_time(chunk_info.get('end_time', 0))}\n"
            chunk_context += f"- Is final chunk: {'Yes' if chunk_info.get('is_final_chunk', False) else 'No'}\n\n"
        
        return f"""You are analyzing a complete YouTube video transcript to extract the most valuable insights. The user wants structured, actionable content with full context understanding.

{chunk_context}CRITICAL: Return ONLY valid JSON with no additional text, comments, or markdown formatting. Your entire response must be valid JSON that can be parsed directly.

Return strict JSON with these keys:
- 'summary': 2-3 paragraph executive summary of the core message and value
- 'key_insights': 8-12 most important insights as detailed paragraphs (not bullet points)
- 'frameworks': actionable frameworks/methods with step-by-step breakdowns
- 'key_moments': chronological sequence of important events/topics discussed

Guidelines:
- Focus on practical, actionable insights that provide real value
- Each key insight should be a structured paragraph (3-5 sentences) explaining the concept fully
- Include specific examples, strategies, and reasoning from the video
- Use the full context to identify overarching themes and connections
- Frameworks should be detailed with clear steps and context
- Present key moments in chronological order as they appear in the video

Example format:
{{
  "summary": "Comprehensive 2-3 paragraph overview of the core message and value proposition...",
  "key_insights": [
    "Detailed paragraph explaining first major insight with context and examples from the video...",
    "Another structured paragraph about second key concept with practical applications..."
  ],
  "frameworks": [
    {{
      "name": "Framework Name",
      "description": "What it does and why it's valuable",
      "steps": [
        "Step 1 with specific details and context",
        "Step 2 with implementation guidance"
      ]
    }}
  ],
  "key_moments": [
    "First major topic introduced",
    "Key transition or development",
    "Important conclusion or call to action"
  ]
}}

Full transcript:

{text}"""
    
    def _format_time(self, seconds: float) -> str:
        """Format seconds into MM:SS or HH:MM:SS format."""
        if seconds < 3600:
            minutes = int(seconds // 60)
            secs = int(seconds % 60)
            return f"{minutes:02d}:{secs:02d}"
        else:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            secs = int(seconds % 60)
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"


# Global instances
default_summarizer = SummarizationService()
summarizer_with_high_temp = SummarizationService(
    SummarizationConfig(temperature=0.7, max_tokens=2500)
)
summarizer_with_low_temp = SummarizationService(
    SummarizationConfig(temperature=0.1, max_tokens=1500)
)
summarizer_for_long_videos = SummarizationService(
    SummarizationConfig(temperature=0.3, max_tokens=3000, timeout=90)
)
