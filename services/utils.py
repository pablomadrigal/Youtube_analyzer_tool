"""
Shared utilities for common functionality across services.
"""
import logging
import re
from typing import Optional
from urllib.parse import urlparse, parse_qs

from app_logging import log_with_context
from config import config

logger = logging.getLogger(__name__)


def extract_video_id(url: str) -> Optional[str]:
    """
    Extract video ID from YouTube URL.
    
    Args:
        url: YouTube video URL
        
    Returns:
        Video ID or None if extraction fails
    """
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


def validate_provider_config(provider: str) -> bool:
    """
    Validate that the provider is properly configured.
    
    Args:
        provider: Provider string (e.g., "openai/gpt-4o-mini")
        
    Returns:
        True if provider is properly configured, False otherwise
    """
    if provider.startswith("openai/"):
        return config.openai_api_key is not None
    elif provider.startswith("anthropic/"):
        return config.anthropic_api_key is not None
    else:
        # For now, assume other providers are valid
        return True


class RetryManager:
    """Manages retry logic with exponential backoff."""
    
    def __init__(self, max_retries: int = 3, base_delay: float = 1.0):
        self.max_retries = max_retries
        self.base_delay = base_delay
    
    async def execute_with_retry(self, func, *args, **kwargs):
        """
        Execute function with retry logic.
        
        Args:
            func: Function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Function result
            
        Raises:
            Exception: If all retries fail
        """
        import asyncio
        
        last_exception = None
        
        for attempt in range(self.max_retries):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                
                if attempt < self.max_retries - 1:
                    delay = self.base_delay * (2 ** attempt)
                    log_with_context("warning", f"Attempt {attempt + 1} failed: {str(e)}. Retrying in {delay}s...")
                    await asyncio.sleep(delay)
                else:
                    log_with_context("error", f"All {self.max_retries} attempts failed")
        
        raise last_exception


class TimingContext:
    """Context manager for timing operations."""
    
    def __init__(self, operation_name: str):
        self.operation_name = operation_name
        self.start_time = None
        self.duration = None
    
    def __enter__(self):
        from datetime import datetime
        self.start_time = datetime.now()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        from datetime import datetime
        if self.start_time:
            self.duration = (datetime.now() - self.start_time).total_seconds()
            log_with_context("info", f"{self.operation_name} took {self.duration:.2f}s")
    
    @property
    def elapsed_seconds(self) -> Optional[float]:
        """Get elapsed time in seconds."""
        return self.duration
