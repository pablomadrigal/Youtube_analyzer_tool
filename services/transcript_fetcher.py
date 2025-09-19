"""
Transcript fetcher using youtube-transcript-api to extract video transcripts.
"""
import logging
from typing import Optional, Dict, List, Tuple
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.formatters import TextFormatter
from youtube_transcript_api._errors import (
    TranscriptsDisabled, 
    NoTranscriptFound, 
    VideoUnavailable,
    TooManyRequests
)

from models import TranscriptData, TranscriptSegment, Transcripts, ErrorInfo, TranscriptLine, TranscriptUnavailableError
from app_logging import log_with_context
from config import config
from .audio_downloader import audio_downloader
from .whisper_transcriber import whisper_transcriber
from .cache import cache
from .utils import extract_video_id
from rich.console import Console

console = Console()

logger = logging.getLogger(__name__)


class TranscriptFetcher:
    """Fetches video transcripts using youtube-transcript-api."""
    
    def __init__(self):
        """Initialize the transcript fetcher."""
        self.text_formatter = TextFormatter()
        self.supported_languages = ['en', 'es']
        self.use_whisper_fallback = config.use_whisper_fallback
    
    def extract_video_id(self, url: str) -> Optional[str]:
        """Extract video ID from YouTube URL."""
        return extract_video_id(url)
    
    def fetch_transcripts(self, url: str, languages: List[str] = None) -> Tuple[Optional[Transcripts], Optional[ErrorInfo]]:
        """
        Fetch transcripts for a video in specified languages.
        
        Args:
            url: YouTube video URL
            languages: List of language codes to fetch (default: ['es', 'en'])
            
        Returns:
            Tuple of (transcripts, error). If successful, transcripts is populated and error is None.
            If failed, transcripts is None and error contains error information.
        """
        if languages is None:
            languages = self.supported_languages
            
        try:
            log_with_context("info", f"Fetching transcripts for URL: {url}")
            
            # Extract video ID
            video_id = self.extract_video_id(url)
            if not video_id:
                return None, ErrorInfo(
                    code="INVALID_URL",
                    message="Could not extract video ID from URL. Please provide a valid YouTube URL."
                )
            
            # Use the new fetch_transcript method for each language
            transcript_data = {}
            unavailable = {}

            for lang in languages:
                try:
                    log_with_context("info", f"Fetching {lang} transcript for video {video_id}")
                    
                    # Use the new fetch_transcript method
                    transcript_lines = self.fetch_transcript(video_id, [lang])
                    
                    # Convert TranscriptLine to TranscriptSegment
                    segments = [
                        TranscriptSegment(
                            text=line.text,
                            start=line.start,
                            duration=line.duration
                        )
                        for line in transcript_lines
                    ]
                    
                    # Determine source (will be "whisper" if fallback was used)
                    source = "auto"  # Default for YouTube API, will be "whisper" if fallback used
                    
                    transcript_data[lang] = TranscriptData(
                        source=source,
                        segments=segments
                    )
                    
                    log_with_context("info", f"Successfully fetched {lang} transcript: {len(segments)} segments, source: {source}")
                    
                except TranscriptUnavailableError as e:
                    log_with_context("info", f"No {lang} transcript available for video {video_id}: {str(e)}")
                    unavailable[lang] = "not_available"
                    
                except Exception as e:
                    log_with_context("error", f"Error fetching {lang} transcript: {str(e)}")
                    unavailable[lang] = "error"
            
            # Create transcripts object
            transcripts = Transcripts(
                es=transcript_data.get('es'),
                en=transcript_data.get('en'),
                unavailable=unavailable
            )
            
            # Check if we got any transcripts
            if not transcript_data:
                return None, ErrorInfo(
                    code="NO_TRANSCRIPTS",
                    message="No transcripts available in any of the requested languages"
                )
            
            log_with_context("info", f"Successfully fetched transcripts: {list(transcript_data.keys())}")
            return transcripts, None
            
        except Exception as e:
            log_with_context("error", f"Unexpected error fetching transcripts for {url}: {str(e)}")
            return None, ErrorInfo(
                code="TRANSCRIPT_ERROR",
                message=f"Unexpected error: {str(e)}"
            )
    
    
    def get_available_languages(self, url: str) -> Tuple[Optional[List[str]], Optional[ErrorInfo]]:
        """
        Get list of available transcript languages for a video.
        
        Args:
            url: YouTube video URL
            
        Returns:
            Tuple of (languages, error). If successful, languages is populated and error is None.
        """
        try:
            video_id = self.extract_video_id(url)
            if not video_id:
                return None, ErrorInfo(
                    code="INVALID_URL",
                    message="Could not extract video ID from URL"
                )
            
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            languages = [t.language_code for t in transcript_list]
            
            log_with_context("info", f"Available languages for video {video_id}: {languages}")
            return languages, None
            
        except Exception as e:
            log_with_context("error", f"Error getting available languages: {str(e)}")
            return None, ErrorInfo(
                code="LANGUAGE_ERROR",
                message=f"Error getting available languages: {str(e)}"
            )
    
    def format_transcript_as_text(self, transcript_data: TranscriptData) -> str:
        """Format transcript data as plain text."""
        if not transcript_data or not transcript_data.segments:
            return ""
        
        # Convert segments to the format expected by TextFormatter
        segments = [
            {
                'text': segment.text,
                'start': segment.start,
                'duration': segment.duration
            }
            for segment in transcript_data.segments
        ]
        
        return self.text_formatter.format_transcript(segments)
    
    
    def fetch_transcript(
        self, 
        video_id: str, 
        lang_priority: Optional[List[str]] = None
    ) -> List[TranscriptLine]:
        """
        Fetch transcript using YouTube API with Whisper fallback.
        
        Args:
            video_id: YouTube video ID
            lang_priority: Preferred language codes (e.g., ["en", "es"])
        
        Returns:
            List of transcript lines with timing
        """
        if lang_priority is None:
            lang_priority = ["en", "es"]
        
        # Check cache first
        cached_transcript = cache.get_transcript(video_id)
        if cached_transcript:
            console.print("[dim]Using cached transcript[/dim]")
            return cached_transcript
        
        # Try YouTube API first
        transcript_lines = self._try_youtube_api(video_id, lang_priority)
        if transcript_lines:
            cache.set_transcript(video_id, transcript_lines)
            return transcript_lines
        
        # Try Whisper fallback
        try:
            transcript_lines = self._whisper_fallback_transcribe(
                f"https://www.youtube.com/watch?v={video_id}",
                lang_priority
            )
            cache.set_transcript(video_id, transcript_lines)
            return transcript_lines
        except Exception as e:
            raise TranscriptUnavailableError(
                f"No transcript available via YouTube API, and Whisper fallback failed: {e}. "
                "Set OPENAI_API_KEY environment variable to enable transcription."
            )
    
    def _try_youtube_api(self, video_id: str, lang_priority: List[str]) -> Optional[List[TranscriptLine]]:
        """Try to fetch transcript using YouTube API."""
        try:
            api = YouTubeTranscriptApi()
            
            # Try preferred languages
            for lang_code in lang_priority:
                transcript_lines = self._fetch_for_language(api, video_id, lang_code)
                if transcript_lines:
                    return transcript_lines
            
            # Try auto-detect
            return self._fetch_for_language(api, video_id, None)
            
        except Exception as e:
            console.print(f"[yellow]YouTube transcript API failed: {e}[/yellow]")
            return None
    
    def _fetch_for_language(self, api: YouTubeTranscriptApi, video_id: str, lang_code: Optional[str]) -> Optional[List[TranscriptLine]]:
        """Fetch transcript for a specific language."""
        try:
            if lang_code:
                console.print(f"[dim]Trying language: {lang_code}[/dim]")
                transcript_data = api.get_transcript(video_id, languages=[lang_code])
            else:
                console.print("[dim]Trying with auto-detected language[/dim]")
                transcript_data = api.get_transcript(video_id)
            
            transcript_lines = [
                TranscriptLine(
                    start=segment.start,
                    duration=segment.duration,
                    text=segment.text
                )
                for segment in transcript_data
            ]
            
            lang_display = lang_code or "auto-detected"
            console.print(f"[green]✅ Found transcript in {lang_display} with {len(transcript_lines)} segments[/green]")
            return transcript_lines
            
        except Exception as e:
            lang_display = lang_code or "auto-detected"
            console.print(f"[dim]Failed for {lang_display}: {e}[/dim]")
            return None
    
    def _whisper_fallback_transcribe(
        self, 
        video_url: str, 
        lang_priority: Optional[List[str]] = None
    ) -> List[TranscriptLine]:
        """Download audio and transcribe via OpenAI Whisper API."""
        audio_file_path = None
        try:
            # Use existing audio_downloader service
            audio_file_path, error = audio_downloader.download_audio(video_url)
            if error:
                raise TranscriptUnavailableError(f"Audio download failed: {error.message}")
            
            # Use existing whisper_transcriber service
            language = lang_priority[0] if lang_priority else None
            transcript_data, error = whisper_transcriber.transcribe_audio(audio_file_path, language)
            
            if error:
                raise TranscriptUnavailableError(f"Whisper API failed: {error.message}")
            
            # Convert TranscriptData to TranscriptLine objects
            lines = []
            for segment in transcript_data.segments:
                lines.append(TranscriptLine(
                    start=segment.start,
                    duration=segment.duration,
                    text=segment.text
                ))
            
            if not lines:
                raise TranscriptUnavailableError("Whisper produced no segments")
            
            return lines
                
        except Exception as e:
            raise TranscriptUnavailableError(f"Whisper fallback failed: {e}") from e
        finally:
            # Clean up audio file
            if audio_file_path:
                audio_downloader.cleanup_audio_file(audio_file_path)


# Global instance
transcript_fetcher = TranscriptFetcher()
