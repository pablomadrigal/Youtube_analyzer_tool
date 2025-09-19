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

from models import TranscriptData, TranscriptSegment, Transcripts, ErrorInfo
from app_logging import log_with_context

logger = logging.getLogger(__name__)


class TranscriptFetcher:
    """Fetches video transcripts using youtube-transcript-api."""
    
    def __init__(self):
        """Initialize the transcript fetcher."""
        self.text_formatter = TextFormatter()
        self.supported_languages = ['es', 'en']
    
    def extract_video_id(self, url: str) -> Optional[str]:
        """Extract video ID from YouTube URL (reused from metadata fetcher)."""
        import re
        from urllib.parse import urlparse, parse_qs
        
        try:
            # Handle various YouTube URL formats
            patterns = [
                r'(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([a-zA-Z0-9_-]{11})',
                r'youtube\.com\/watch\?.*v=([a-zA-Z0-9_-]{11})',
            ]
            
            for pattern in patterns:
                match = re.search(pattern, url)
                if match:
                    return match.group(1)
            
            # Try parsing as URL
            parsed = urlparse(url)
            if 'youtube.com' in parsed.netloc or 'youtu.be' in parsed.netloc:
                if parsed.path.startswith('/watch'):
                    query_params = parse_qs(parsed.query)
                    if 'v' in query_params:
                        return query_params['v'][0]
                elif parsed.path.startswith('/') and len(parsed.path) > 1:
                    # Handle youtu.be/VIDEO_ID format
                    return parsed.path[1:]
            
            return None
            
        except Exception as e:
            log_with_context("error", f"Failed to extract video ID from URL {url}: {str(e)}")
            return None
    
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
            
            # Fetch transcripts for each language
            transcript_data = {}
            unavailable = {}
            
            for lang in languages:
                try:
                    log_with_context("info", f"Fetching {lang} transcript for video {video_id}")
                    
                    # Get transcript list for the video
                    transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
                    
                    # Try to find transcript in the requested language
                    transcript = self._find_transcript(transcript_list, lang)
                    
                    if transcript:
                        # Fetch the actual transcript
                        transcript_segments = transcript.fetch()
                        
                        # Convert to our format
                        segments = [
                            TranscriptSegment(
                                text=segment['text'],
                                start=segment['start'],
                                duration=segment.get('duration', 0.0)
                            )
                            for segment in transcript_segments
                        ]
                        
                        # Determine source (auto-generated vs manual)
                        source = "auto" if transcript.is_generated else "manual"
                        
                        transcript_data[lang] = TranscriptData(
                            source=source,
                            segments=segments
                        )
                        
                        log_with_context("info", f"Successfully fetched {lang} transcript: {len(segments)} segments, source: {source}")
                        
                    else:
                        unavailable[lang] = "not_available"
                        log_with_context("info", f"No {lang} transcript available for video {video_id}")
                        
                except TranscriptsDisabled:
                    unavailable[lang] = "disabled"
                    log_with_context("info", f"Transcripts disabled for {lang} in video {video_id}")
                    
                except NoTranscriptFound:
                    unavailable[lang] = "not_found"
                    log_with_context("info", f"No {lang} transcript found for video {video_id}")
                    
                except VideoUnavailable:
                    return None, ErrorInfo(
                        code="VIDEO_UNAVAILABLE",
                        message="Video is unavailable or private"
                    )
                    
                except TooManyRequests:
                    return None, ErrorInfo(
                        code="RATE_LIMIT",
                        message="Too many requests to YouTube transcript API"
                    )
                    
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
            
        except VideoUnavailable:
            return None, ErrorInfo(
                code="VIDEO_UNAVAILABLE",
                message="Video is unavailable or private"
            )
            
        except Exception as e:
            log_with_context("error", f"Unexpected error fetching transcripts for {url}: {str(e)}")
            return None, ErrorInfo(
                code="TRANSCRIPT_ERROR",
                message=f"Unexpected error: {str(e)}"
            )
    
    def _find_transcript(self, transcript_list, language: str):
        """Find transcript in the requested language, with fallback logic."""
        try:
            # First try to get the exact language
            return transcript_list.find_transcript([language])
        except NoTranscriptFound:
            try:
                # Try to find manually created transcripts first
                manual_transcripts = [t for t in transcript_list if not t.is_generated]
                if manual_transcripts:
                    # Try to find a manual transcript in the requested language
                    for transcript in manual_transcripts:
                        if transcript.language_code == language:
                            return transcript
                    
                    # If no manual transcript in requested language, try any manual transcript
                    return manual_transcripts[0]
                
                # If no manual transcripts, try auto-generated
                auto_transcripts = [t for t in transcript_list if t.is_generated]
                if auto_transcripts:
                    # Try to find auto-generated transcript in the requested language
                    for transcript in auto_transcripts:
                        if transcript.language_code == language:
                            return transcript
                    
                    # If no auto-generated transcript in requested language, try any auto-generated
                    return auto_transcripts[0]
                
                return None
                
            except Exception:
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


# Global instance
transcript_fetcher = TranscriptFetcher()
