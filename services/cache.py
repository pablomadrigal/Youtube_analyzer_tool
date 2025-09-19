"""
Simple in-memory cache for transcripts.
"""
from typing import Optional, Dict, List
from models import TranscriptLine
import threading
import time


class TranscriptCache:
    """Simple in-memory cache for transcripts with TTL."""
    
    def __init__(self, ttl_seconds: int = 3600):
        """
        Initialize cache with TTL.
        
        Args:
            ttl_seconds: Time to live for cached items in seconds
        """
        self._cache: Dict[str, tuple] = {}  # video_id -> (transcript_lines, timestamp)
        self._ttl = ttl_seconds
        self._lock = threading.Lock()
    
    def get_transcript(self, video_id: str) -> Optional[List[TranscriptLine]]:
        """
        Get cached transcript for video ID.
        
        Args:
            video_id: YouTube video ID
            
        Returns:
            Cached transcript lines or None if not found/expired
        """
        with self._lock:
            if video_id not in self._cache:
                return None
            
            transcript_lines, timestamp = self._cache[video_id]
            
            # Check if expired
            if time.time() - timestamp > self._ttl:
                del self._cache[video_id]
                return None
            
            return transcript_lines
    
    def set_transcript(self, video_id: str, transcript_lines: List[TranscriptLine]) -> None:
        """
        Cache transcript for video ID.
        
        Args:
            video_id: YouTube video ID
            transcript_lines: Transcript lines to cache
        """
        with self._lock:
            self._cache[video_id] = (transcript_lines, time.time())
    
    def clear(self) -> None:
        """Clear all cached transcripts."""
        with self._lock:
            self._cache.clear()
    
    def size(self) -> int:
        """Get number of cached items."""
        with self._lock:
            return len(self._cache)


# Global cache instance
cache = TranscriptCache()
