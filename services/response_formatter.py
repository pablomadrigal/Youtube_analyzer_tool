"""
Response formatter service for generating Markdown and formatted outputs.
"""
import logging
from typing import Optional, Dict, Any
from datetime import datetime

from models import VideoResult, VideoMetadata, Transcripts, Summaries, MarkdownFields
from app_logging import log_with_context

logger = logging.getLogger(__name__)


class ResponseFormatter:
    """Formats video analysis results into various output formats."""
    
    def __init__(self):
        """Initialize the response formatter."""
        pass
    
    def format_video_result(self, result: VideoResult, include_markdown: bool = False) -> VideoResult:
        """
        Format a video result with optional Markdown fields.
        
        Args:
            result: Video result to format
            include_markdown: Whether to include Markdown fields
            
        Returns:
            Formatted video result
        """
        if not include_markdown:
            return result
        
        try:
            markdown_fields = self._generate_markdown_fields(result)
            
            # Create updated result with Markdown fields
            return VideoResult(
                url=result.url,
                video_id=result.video_id,
                status=result.status,
                metadata=result.metadata,
                transcripts=result.transcripts,
                summaries=result.summaries,
                markdown=markdown_fields,
                error=result.error
            )
            
        except Exception as e:
            log_with_context("error", f"Error formatting result: {str(e)}")
            return result
    
    def _generate_markdown_fields(self, result: VideoResult) -> Optional[MarkdownFields]:
        """Generate Markdown fields for a video result."""
        if result.status != "ok":
            return None
        
        try:
            markdown_fields = MarkdownFields()
            
            # Generate summary Markdown
            if result.summaries:
                if result.summaries.es:
                    markdown_fields.summary_es = self._format_summary_markdown(result.summaries.es, "es")
                if result.summaries.en:
                    markdown_fields.summary_en = self._format_summary_markdown(result.summaries.en, "en")
            
            # Generate transcript Markdown for multiple languages
            if result.transcripts:
                # Original language transcript
                if result.transcripts.original:
                    original_language = result.transcripts.language or "unknown"
                    markdown_fields.transcript_es = self._format_transcript_markdown(
                        result.transcripts.original, 
                        original_language
                    )
                
                # English transcript if available
                if result.transcripts.english:
                    markdown_fields.transcript_en = self._format_transcript_markdown(
                        result.transcripts.english, 
                        "en"
                    )
                elif result.transcripts.original:
                    # If no English transcript, use original for both fields
                    markdown_fields.transcript_en = markdown_fields.transcript_es
            
            return markdown_fields
            
        except Exception as e:
            log_with_context("error", f"Error generating Markdown fields: {str(e)}")
            return None
    
    def _format_summary_markdown(self, summary_data, language: str) -> str:
        """Format summary data as Markdown."""
        if not summary_data:
            return ""
        
        lang_header = "Resumen" if language == "es" else "Summary"
        
        markdown_parts = [f"# {lang_header}"]
        
        # Add metadata if available
        markdown_parts.append(f"*Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")
        markdown_parts.append("")
        
        # Topics section
        if summary_data.topics:
            topics_header = "## Temas Principales" if language == "es" else "## Main Topics"
            markdown_parts.append(topics_header)
            for topic in summary_data.topics:
                markdown_parts.append(f"- {topic}")
            markdown_parts.append("")
        
        # Key points section
        if summary_data.bullets:
            bullets_header = "## Puntos Clave" if language == "es" else "## Key Points"
            markdown_parts.append(bullets_header)
            for bullet in summary_data.bullets:
                markdown_parts.append(f"- {bullet}")
            markdown_parts.append("")
        
        # Quotes section
        if summary_data.quotes:
            quotes_header = "## Citas Notables" if language == "es" else "## Notable Quotes"
            markdown_parts.append(quotes_header)
            for quote in summary_data.quotes:
                markdown_parts.append(f"> {quote}")
            markdown_parts.append("")
        
        # Actions section
        if summary_data.actions:
            actions_header = "## Acciones Recomendadas" if language == "es" else "## Recommended Actions"
            markdown_parts.append(actions_header)
            for action in summary_data.actions:
                markdown_parts.append(f"- {action}")
            markdown_parts.append("")
        
        return "\n".join(markdown_parts)
    
    def _format_transcript_markdown(self, transcript_data, language: str) -> str:
        """Format transcript data as Markdown."""
        if not transcript_data or not transcript_data.segments:
            return ""
        
        # Use the detected language from the transcript data if available
        detected_language = getattr(transcript_data, 'language', language)
        
        # Import language names mapping
        from models import LANGUAGE_NAMES
        
        if detected_language:
            language_name = LANGUAGE_NAMES.get(detected_language, detected_language.upper())
            lang_header = f"Transcripción ({language_name})"
        else:
            lang_header = "Transcripción"
        
        source_note = ""
        if transcript_data.source == "auto":
            source_note = " (Generada automáticamente)"
        elif transcript_data.source == "manual":
            source_note = " (Manual)"
        elif transcript_data.source == "whisper":
            source_note = " (Transcrita por Whisper AI)"
        
        markdown_parts = [f"# {lang_header}{source_note}"]
        markdown_parts.append("")
        
        # Add segments
        for segment in transcript_data.segments:
            # Format timestamp
            timestamp = self._format_timestamp(segment.start)
            markdown_parts.append(f"**[{timestamp}]** {segment.text}")
            markdown_parts.append("")
        
        return "\n".join(markdown_parts)
    
    def _format_timestamp(self, seconds: float) -> str:
        """Format seconds as MM:SS timestamp."""
        minutes = int(seconds // 60)
        seconds = int(seconds % 60)
        return f"{minutes:02d}:{seconds:02d}"
    
    def format_analysis_response(self, response_data: Dict[str, Any], include_markdown: bool = False) -> Dict[str, Any]:
        """
        Format an entire analysis response with optional Markdown.
        
        Args:
            response_data: Analysis response data
            include_markdown: Whether to include Markdown fields
            
        Returns:
            Formatted response data
        """
        if not include_markdown:
            return response_data
        
        try:
            # Format each result
            formatted_results = []
            for result in response_data.get("results", []):
                if isinstance(result, dict):
                    # Convert dict to VideoResult if needed
                    video_result = VideoResult(**result)
                    formatted_result = self.format_video_result(video_result, include_markdown)
                    formatted_results.append(formatted_result.dict())
                else:
                    formatted_results.append(result)
            
            # Update response with formatted results
            response_data["results"] = formatted_results
            return response_data
            
        except Exception as e:
            log_with_context("error", f"Error formatting analysis response: {str(e)}")
            return response_data


# Global instance
response_formatter = ResponseFormatter()
