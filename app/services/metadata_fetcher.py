"""
Metadata fetcher using yt-dlp to extract video information.
"""
import logging
import re
from typing import Optional, Dict, Any
from urllib.parse import urlparse, parse_qs
import yt_dlp
from datetime import datetime

from app.models import VideoMetadata, ErrorInfo
from app.logging import log_with_context

logger = logging.getLogger(__name__)


class MetadataFetcher:
    """Fetches video metadata using yt-dlp."""
    
    def __init__(self):
        """Initialize the metadata fetcher."""
        self.ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'writeinfojson': False,
            'writethumbnail': False,
            'writesubtitles': False,
            'writeautomaticsub': False,
        }
    
    def extract_video_id(self, url: str) -> Optional[str]:
        """Extract video ID from YouTube URL."""
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
    
    def fetch_metadata(self, url: str) -> tuple[Optional[VideoMetadata], Optional[ErrorInfo]]:
        """
        Fetch video metadata using yt-dlp.
        
        Args:
            url: YouTube video URL
            
        Returns:
            Tuple of (metadata, error). If successful, metadata is populated and error is None.
            If failed, metadata is None and error contains error information.
        """
        try:
            log_with_context("info", f"Fetching metadata for URL: {url}")
            
            # Extract video ID first
            video_id = self.extract_video_id(url)
            if not video_id:
                return None, ErrorInfo(
                    code="INVALID_URL",
                    message="Could not extract video ID from URL. Please provide a valid YouTube URL."
                )
            
            # Use yt-dlp to fetch metadata
            with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
                try:
                    info = ydl.extract_info(url, download=False)
                except Exception as e:
                    error_msg = str(e)
                    if "Video unavailable" in error_msg:
                        return None, ErrorInfo(
                            code="VIDEO_UNAVAILABLE",
                            message="Video is unavailable or private"
                        )
                    elif "Video unavailable" in error_msg or "Private video" in error_msg:
                        return None, ErrorInfo(
                            code="VIDEO_PRIVATE",
                            message="Video is private or unavailable"
                        )
                    else:
                        return None, ErrorInfo(
                            code="METADATA_FETCH_ERROR",
                            message=f"Failed to fetch metadata: {error_msg}"
                        )
                
                if not info:
                    return None, ErrorInfo(
                        code="NO_INFO",
                        message="No metadata could be extracted from the video"
                    )
                
                # Extract and normalize metadata
                metadata = self._normalize_metadata(info, url, video_id)
                log_with_context("info", f"Successfully fetched metadata for video: {metadata.title}")
                
                return metadata, None
                
        except Exception as e:
            log_with_context("error", f"Unexpected error fetching metadata for {url}: {str(e)}")
            return None, ErrorInfo(
                code="METADATA_ERROR",
                message=f"Unexpected error: {str(e)}"
            )
    
    def _normalize_metadata(self, info: Dict[str, Any], url: str, video_id: str) -> VideoMetadata:
        """Normalize yt-dlp metadata into our VideoMetadata model."""
        try:
            # Extract title
            title = info.get('title', 'Unknown Title')
            if not title or title == 'Unknown Title':
                title = f"Video {video_id}"
            
            # Extract channel name
            channel = info.get('uploader', info.get('channel', 'Unknown Channel'))
            if not channel or channel == 'Unknown Channel':
                channel = info.get('uploader_id', 'Unknown Channel')
            
            # Extract publish date
            published_at = self._extract_publish_date(info)
            
            # Extract duration
            duration_sec = int(info.get('duration', 0)) if info.get('duration') else 0
            
            # Use canonical URL if available, otherwise use original
            canonical_url = info.get('webpage_url', url)
            
            return VideoMetadata(
                title=title,
                channel=channel,
                published_at=published_at,
                duration_sec=duration_sec,
                url=canonical_url
            )
            
        except Exception as e:
            log_with_context("error", f"Error normalizing metadata: {str(e)}")
            # Return minimal metadata if normalization fails
            return VideoMetadata(
                title=f"Video {video_id}",
                channel="Unknown Channel",
                published_at="1970-01-01T00:00:00Z",
                duration_sec=0,
                url=url
            )
    
    def _extract_publish_date(self, info: Dict[str, Any]) -> str:
        """Extract and format publish date."""
        try:
            # Try different date fields
            date_fields = ['upload_date', 'release_date', 'timestamp']
            
            for field in date_fields:
                if field in info and info[field]:
                    date_value = info[field]
                    
                    # Handle timestamp (seconds since epoch)
                    if isinstance(date_value, (int, float)):
                        dt = datetime.fromtimestamp(date_value)
                        return dt.strftime('%Y-%m-%dT%H:%M:%SZ')
                    
                    # Handle string dates (YYYYMMDD format)
                    if isinstance(date_value, str) and len(date_value) == 8:
                        try:
                            dt = datetime.strptime(date_value, '%Y%m%d')
                            return dt.strftime('%Y-%m-%dT%H:%M:%SZ')
                        except ValueError:
                            continue
            
            # Fallback to current time if no date found
            return datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')
            
        except Exception as e:
            log_with_context("error", f"Error extracting publish date: {str(e)}")
            return datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')


# Global instance
metadata_fetcher = MetadataFetcher()
