"""
Audio downloader service using yt-dlp to download audio from YouTube videos.
"""
import os
import tempfile
import logging
from typing import Optional, Tuple
from pathlib import Path
import yt_dlp
from models import ErrorInfo
from app_logging import log_with_context
from config import config

logger = logging.getLogger(__name__)


class AudioDownloader:
    """Downloads audio from YouTube videos using yt-dlp."""
    
    def __init__(self):
        """Initialize the audio downloader."""
        self.temp_dir = None
        self._setup_temp_dir()
    
    def _setup_temp_dir(self):
        """Setup temporary directory for audio files."""
        try:
            self.temp_dir = tempfile.mkdtemp(prefix="youtube_audio_")
            log_with_context("info", f"Created temporary directory: {self.temp_dir}")
        except Exception as e:
            log_with_context("error", f"Failed to create temporary directory: {str(e)}")
            self.temp_dir = None
    
    def extract_video_id(self, url: str) -> Optional[str]:
        """Extract video ID from YouTube URL."""
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
    
    def download_audio(self, url: str, max_duration: int = None) -> Tuple[Optional[str], Optional[ErrorInfo]]:
        """
        Download audio from YouTube video.
        
        Args:
            url: YouTube video URL
            max_duration: Maximum duration in seconds (default: from config)
            
        Returns:
            Tuple of (audio_file_path, error). If successful, audio_file_path is populated and error is None.
            If failed, audio_file_path is None and error contains error information.
        """
        if max_duration is None:
            max_duration = config.whisper_max_audio_duration
            
        if not self.temp_dir:
            return None, ErrorInfo(
                code="TEMP_DIR_ERROR",
                message="Failed to create temporary directory for audio download"
            )
        
        try:
            video_id = self.extract_video_id(url)
            if not video_id:
                return None, ErrorInfo(
                    code="INVALID_URL",
                    message="Could not extract video ID from URL"
                )
            
            log_with_context("info", f"Downloading audio for video {video_id}")
            
            # Configure yt-dlp options
            output_path = os.path.join(self.temp_dir, f"{video_id}.%(ext)s")
            
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': output_path,
                'extractaudio': True,
                'audioformat': 'wav',
                'audioquality': '192K',
                'noplaylist': True,
                'max_duration': max_duration,
                'quiet': True,
                'no_warnings': False,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Extract info first to check video duration
                info = ydl.extract_info(url, download=False)
                duration = info.get('duration', 0)
                
                if duration > max_duration:
                    return None, ErrorInfo(
                        code="VIDEO_TOO_LONG",
                        message=f"Video duration ({duration}s) exceeds maximum allowed duration ({max_duration}s)"
                    )
                
                # Download the audio
                ydl.download([url])
            
            # Find the downloaded file
            downloaded_file = self._find_downloaded_file(video_id)
            if not downloaded_file:
                return None, ErrorInfo(
                    code="DOWNLOAD_FAILED",
                    message="Audio download completed but file not found"
                )
            
            log_with_context("info", f"Successfully downloaded audio: {downloaded_file}")
            return downloaded_file, None
            
        except yt_dlp.DownloadError as e:
            if "Video unavailable" in str(e):
                return None, ErrorInfo(
                    code="VIDEO_UNAVAILABLE",
                    message="Video is unavailable or private"
                )
            elif "Private video" in str(e):
                return None, ErrorInfo(
                    code="VIDEO_PRIVATE",
                    message="Video is private"
                )
            else:
                log_with_context("error", f"yt-dlp download error: {str(e)}")
                return None, ErrorInfo(
                    code="DOWNLOAD_ERROR",
                    message=f"Failed to download audio: {str(e)}"
                )
                
        except Exception as e:
            log_with_context("error", f"Unexpected error downloading audio: {str(e)}")
            return None, ErrorInfo(
                code="DOWNLOAD_ERROR",
                message=f"Unexpected error: {str(e)}"
            )
    
    def _find_downloaded_file(self, video_id: str) -> Optional[str]:
        """Find the downloaded audio file."""
        try:
            if not self.temp_dir:
                return None
            
            # Look for files with the video ID in the name
            temp_path = Path(self.temp_dir)
            for file_path in temp_path.iterdir():
                if file_path.is_file() and video_id in file_path.name:
                    return str(file_path)
            
            return None
            
        except Exception as e:
            log_with_context("error", f"Error finding downloaded file: {str(e)}")
            return None
    
    def cleanup_audio_file(self, file_path: str) -> bool:
        """
        Clean up downloaded audio file.
        
        Args:
            file_path: Path to the audio file to delete
            
        Returns:
            True if cleanup successful, False otherwise
        """
        try:
            if file_path and os.path.exists(file_path):
                os.remove(file_path)
                log_with_context("info", f"Cleaned up audio file: {file_path}")
                return True
            return True
            
        except Exception as e:
            log_with_context("error", f"Error cleaning up audio file {file_path}: {str(e)}")
            return False
    
    def cleanup_temp_dir(self):
        """Clean up the entire temporary directory."""
        try:
            if self.temp_dir and os.path.exists(self.temp_dir):
                import shutil
                shutil.rmtree(self.temp_dir)
                log_with_context("info", f"Cleaned up temporary directory: {self.temp_dir}")
                self.temp_dir = None
                
        except Exception as e:
            log_with_context("error", f"Error cleaning up temporary directory: {str(e)}")


# Global instance
audio_downloader = AudioDownloader()
