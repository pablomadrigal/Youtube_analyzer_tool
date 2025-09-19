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

from models import TranscriptData, TranscriptSegment, Transcripts, ErrorInfo, TranscriptLine, TranscriptUnavailableError, LANGUAGE_NAMES
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
        Fetch the original language transcript for a video.
        
        Args:
            url: YouTube video URL
            languages: List of language codes to prefer (default: ['es', 'en'])
            
        Returns:
            Tuple of (transcripts, error). If successful, transcripts contains the original language transcript.
            If failed, transcripts is None and error contains error information.
        """
        if languages is None:
            languages = self.supported_languages
            
        try:
            log_with_context("info", f"Fetching original language transcript for URL: {url}")
            
            # Extract video ID
            video_id = self.extract_video_id(url)
            if not video_id:
                return None, ErrorInfo(
                    code="INVALID_URL",
                    message="Could not extract video ID from URL. Please provide a valid YouTube URL."
                )
            
            # Get available transcripts with language information
            transcript_list, lang_error = self._get_transcript_list(video_id)
            if lang_error:
                return None, lang_error
            
            if not transcript_list:
                return None, ErrorInfo(
                    code="NO_TRANSCRIPTS",
                    message="No transcripts available for this video"
                )
            
            # Find the best transcript (prefer manual over auto-generated, then prefer requested languages)
            best_transcript = self._select_best_transcript(transcript_list, languages)
            
            # If no YouTube transcript is available, try Whisper fallback
            if not best_transcript:
                if self.use_whisper_fallback:
                    log_with_context("info", f"No YouTube transcripts available, trying Whisper fallback for video {video_id}")
                    try:
                        # Use the Whisper transcriber directly to get proper language detection
                        audio_file_path, error = audio_downloader.download_audio(f"https://www.youtube.com/watch?v={video_id}")
                        if error:
                            raise TranscriptUnavailableError(f"Audio download failed: {error.message}")
                        
                        try:
                            # Use Whisper transcriber to get proper TranscriptData with language detection
                            transcript_data, error = whisper_transcriber.transcribe_audio(audio_file_path, None)
                            if error:
                                raise TranscriptUnavailableError(f"Whisper API failed: {error.message}")
                            
                            if not transcript_data:
                                raise TranscriptUnavailableError("Whisper produced no transcript data")
                            
                            log_with_context("info", f"Successfully used Whisper fallback for video {video_id}, detected language: {transcript_data.language}")
                            
                            # Create the new streamlined transcripts structure
                            transcripts = Transcripts(
                                transcript=transcript_data,
                                language=transcript_data.language,
                                language_name=LANGUAGE_NAMES.get(transcript_data.language, transcript_data.language.upper()),
                                available_languages=[transcript_data.language],  # Whisper detected language
                                unavailable_reason=None
                            )
                            return transcripts, None
                            
                        finally:
                            # Clean up audio file
                            audio_downloader.cleanup_audio_file(audio_file_path)
                            
                    except Exception as e:
                        log_with_context("error", f"Whisper fallback failed: {str(e)}")
                
                return Transcripts(
                    transcript=None,
                    language=None,
                    language_name=None,
                    available_languages=[],
                    unavailable_reason="No transcripts available and Whisper fallback is disabled or failed"
                ), None
            
            # Fetch the transcript content
            transcript_content = self._fetch_transcript_content(best_transcript, video_id)
            if not transcript_content:
                return Transcripts(
                    transcript=None,
                    language=None,
                    language_name=None,
                    available_languages=[t.language_code for t in transcript_list] if transcript_list else [],
                    unavailable_reason="Failed to fetch transcript content"
                ), None
            
            # Convert to segments
            segments = [
                TranscriptSegment(
                    text=line.text,
                    start=line.start,
                    duration=line.duration
                )
                for line in transcript_content
            ]
            
            # Create transcript data with the detected language
            detected_language = best_transcript.language_code
            transcript_data = TranscriptData(
                source=best_transcript.is_generated and "auto" or "manual",
                segments=segments,
                language=detected_language
            )
            
            log_with_context("info", f"Successfully fetched transcript in {detected_language}: {len(segments)} segments")
            
            # Create the new streamlined transcripts structure
            transcripts = Transcripts(
                transcript=transcript_data,
                language=detected_language,
                language_name=LANGUAGE_NAMES.get(detected_language, detected_language.upper()),
                available_languages=[t.language_code for t in transcript_list] if transcript_list else [detected_language],
                unavailable_reason=None
            )
            
            return transcripts, None
            
        except Exception as e:
            log_with_context("error", f"Unexpected error fetching transcripts for {url}: {str(e)}")
            return None, ErrorInfo(
                code="TRANSCRIPT_ERROR",
                message=f"Unexpected error: {str(e)}"
            )
    
    
    def _get_transcript_list(self, video_id: str) -> Tuple[Optional[list], Optional[ErrorInfo]]:
        """
        Get the list of available transcripts with their metadata.
        
        Args:
            video_id: YouTube video ID
            
        Returns:
            Tuple of (transcript_list, error)
        """
        try:
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            return list(transcript_list), None
        except Exception as e:
            log_with_context("error", f"Error getting transcript list: {str(e)}")
            return None, ErrorInfo(
                code="TRANSCRIPT_LIST_ERROR",
                message=f"Error getting transcript list: {str(e)}"
            )
    
    def _select_best_transcript(self, transcript_list: list, preferred_languages: List[str]) -> Optional[object]:
        """
        Select the best transcript from the available list.
        
        Args:
            transcript_list: List of transcript objects
            preferred_languages: List of preferred language codes
            
        Returns:
            Best transcript object or None
        """
        if not transcript_list:
            return None
        
        # First, try to find a manual transcript in preferred languages
        for transcript in transcript_list:
            if not transcript.is_generated and transcript.language_code in preferred_languages:
                log_with_context("info", f"Found manual transcript in {transcript.language_code}")
                return transcript
        
        # Then try auto-generated transcripts in preferred languages
        for transcript in transcript_list:
            if transcript.is_generated and transcript.language_code in preferred_languages:
                log_with_context("info", f"Found auto-generated transcript in {transcript.language_code}")
                return transcript
        
        # If no preferred language found, take the first manual transcript
        for transcript in transcript_list:
            if not transcript.is_generated:
                log_with_context("info", f"Using first manual transcript in {transcript.language_code}")
                return transcript
        
        # Finally, take the first available transcript
        if transcript_list:
            transcript = transcript_list[0]
            log_with_context("info", f"Using first available transcript in {transcript.language_code}")
            return transcript
        
        return None
    
    def _fetch_transcript_content(self, transcript, video_id: str) -> Optional[List[TranscriptLine]]:
        """
        Fetch the content of a specific transcript.
        
        Args:
            transcript: Transcript object from YouTube API
            video_id: YouTube video ID for fallback
            
        Returns:
            List of transcript lines or None
        """
        try:
            # Try YouTube API first
            transcript_data = transcript.fetch()
            transcript_lines = [
                TranscriptLine(
                    start=segment.start,
                    duration=segment.duration,
                    text=segment.text
                )
                for segment in transcript_data
            ]
            return transcript_lines
        except Exception as e:
            log_with_context("warning", f"Failed to fetch transcript content: {str(e)}")
            
            # Try Whisper fallback if YouTube API fails
            if self.use_whisper_fallback:
                try:
                    video_url = f"https://www.youtube.com/watch?v={video_id}"
                    return self._whisper_fallback_transcribe(video_url, [transcript.language_code])
                except Exception as whisper_error:
                    log_with_context("error", f"Whisper fallback also failed: {str(whisper_error)}")
            
            return None

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
    
    def _fetch_specific_language(self, video_id: str, lang_code: str) -> Optional[List[TranscriptLine]]:
        """Fetch transcript for a specific language using YouTube API."""
        try:
            api = YouTubeTranscriptApi()
            console.print(f"[dim]Fetching specific language: {lang_code}[/dim]")
            transcript_data = api.get_transcript(video_id, languages=[lang_code])
            
            transcript_lines = [
                TranscriptLine(
                    start=segment.start,
                    duration=segment.duration,
                    text=segment.text
                )
                for segment in transcript_data
            ]
            
            console.print(f"[green]✓ Found {len(transcript_lines)} transcript lines for {lang_code}[/green]")
            return transcript_lines
            
        except Exception as e:
            console.print(f"[red]✗ Failed to fetch {lang_code} transcript: {e}[/red]")
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
            # For Whisper, we transcribe once and let it auto-detect the language
            # The language parameter in Whisper is for the input language, not output
            transcript_data, error = whisper_transcriber.transcribe_audio(audio_file_path, None)
            
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
