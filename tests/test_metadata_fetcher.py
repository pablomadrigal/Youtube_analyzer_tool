"""
Tests for the metadata fetcher.
"""
import pytest
from unittest.mock import patch, MagicMock
from app.services.metadata_fetcher import MetadataFetcher, metadata_fetcher
from app.models import VideoMetadata, ErrorInfo


class TestMetadataFetcher:
    """Test cases for MetadataFetcher."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.fetcher = MetadataFetcher()
    
    def test_extract_video_id_standard_url(self):
        """Test extracting video ID from standard YouTube URLs."""
        test_cases = [
            ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
            ("https://youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
            ("https://youtu.be/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
            ("https://www.youtube.com/embed/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ]
        
        for url, expected_id in test_cases:
            result = self.fetcher.extract_video_id(url)
            assert result == expected_id, f"Failed for URL: {url}"
    
    def test_extract_video_id_with_parameters(self):
        """Test extracting video ID from URLs with additional parameters."""
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=10s&list=PLrAXtmRdnEQy6nuLMOV8u4"
        result = self.fetcher.extract_video_id(url)
        assert result == "dQw4w9WgXcQ"
    
    def test_extract_video_id_invalid_url(self):
        """Test extracting video ID from invalid URLs."""
        invalid_urls = [
            "https://www.google.com",
            "https://www.youtube.com/watch",
            "not-a-url",
            "",
        ]
        
        for url in invalid_urls:
            result = self.fetcher.extract_video_id(url)
            assert result is None, f"Should return None for invalid URL: {url}"
    
    @patch('yt_dlp.YoutubeDL')
    def test_fetch_metadata_success(self, mock_ydl_class):
        """Test successful metadata fetching."""
        # Mock yt-dlp response
        mock_ydl_instance = MagicMock()
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl_instance
        
        mock_info = {
            'title': 'Test Video Title',
            'uploader': 'Test Channel',
            'upload_date': '20240101',
            'duration': 300,
            'webpage_url': 'https://www.youtube.com/watch?v=test123',
            'id': 'test123'
        }
        mock_ydl_instance.extract_info.return_value = mock_info
        
        url = "https://www.youtube.com/watch?v=test123"
        metadata, error = self.fetcher.fetch_metadata(url)
        
        assert metadata is not None
        assert error is None
        assert metadata.title == 'Test Video Title'
        assert metadata.channel == 'Test Channel'
        assert metadata.duration_sec == 300
        assert metadata.url == 'https://www.youtube.com/watch?v=test123'
    
    @patch('yt_dlp.YoutubeDL')
    def test_fetch_metadata_video_unavailable(self, mock_ydl_class):
        """Test handling of unavailable videos."""
        mock_ydl_instance = MagicMock()
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl_instance
        mock_ydl_instance.extract_info.side_effect = Exception("Video unavailable")
        
        url = "https://www.youtube.com/watch?v=unavailable"
        metadata, error = self.fetcher.fetch_metadata(url)
        
        assert metadata is None
        assert error is not None
        assert error.code == "VIDEO_UNAVAILABLE"
    
    @patch('yt_dlp.YoutubeDL')
    def test_fetch_metadata_private_video(self, mock_ydl_class):
        """Test handling of private videos."""
        mock_ydl_instance = MagicMock()
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl_instance
        mock_ydl_instance.extract_info.side_effect = Exception("Private video")
        
        url = "https://www.youtube.com/watch?v=private"
        metadata, error = self.fetcher.fetch_metadata(url)
        
        assert metadata is None
        assert error is not None
        assert error.code == "VIDEO_PRIVATE"
    
    def test_fetch_metadata_invalid_url(self):
        """Test handling of invalid URLs."""
        url = "https://www.google.com"
        metadata, error = self.fetcher.fetch_metadata(url)
        
        assert metadata is None
        assert error is not None
        assert error.code == "INVALID_URL"
    
    def test_normalize_metadata_complete(self):
        """Test metadata normalization with complete data."""
        info = {
            'title': 'Test Video',
            'uploader': 'Test Channel',
            'upload_date': '20240101',
            'duration': 300,
            'webpage_url': 'https://www.youtube.com/watch?v=test123'
        }
        
        metadata = self.fetcher._normalize_metadata(info, "https://www.youtube.com/watch?v=test123", "test123")
        
        assert metadata.title == 'Test Video'
        assert metadata.channel == 'Test Channel'
        assert metadata.duration_sec == 300
        assert metadata.url == 'https://www.youtube.com/watch?v=test123'
        assert metadata.published_at == '2024-01-01T00:00:00Z'
    
    def test_normalize_metadata_minimal(self):
        """Test metadata normalization with minimal data."""
        info = {
            'title': '',
            'uploader': '',
            'duration': None,
            'webpage_url': 'https://www.youtube.com/watch?v=test123'
        }
        
        metadata = self.fetcher._normalize_metadata(info, "https://www.youtube.com/watch?v=test123", "test123")
        
        assert metadata.title == 'Video test123'
        assert metadata.channel == 'Unknown Channel'
        assert metadata.duration_sec == 0
        assert metadata.url == 'https://www.youtube.com/watch?v=test123'
    
    def test_extract_publish_date_timestamp(self):
        """Test extracting publish date from timestamp."""
        info = {'upload_date': 1704067200}  # 2024-01-01 00:00:00 UTC
        result = self.fetcher._extract_publish_date(info)
        assert result == '2024-01-01T00:00:00Z'
    
    def test_extract_publish_date_string(self):
        """Test extracting publish date from string format."""
        info = {'upload_date': '20240101'}
        result = self.fetcher._extract_publish_date(info)
        assert result == '2024-01-01T00:00:00Z'
    
    def test_extract_publish_date_fallback(self):
        """Test fallback when no date is available."""
        info = {}
        result = self.fetcher._extract_publish_date(info)
        # Should return current time in ISO format
        assert result.endswith('Z')
        assert len(result) == 20  # YYYY-MM-DDTHH:MM:SSZ


class TestMetadataFetcherIntegration:
    """Integration tests for metadata fetcher."""
    
    def test_global_instance(self):
        """Test that global instance is properly initialized."""
        assert metadata_fetcher is not None
        assert isinstance(metadata_fetcher, MetadataFetcher)
    
    @pytest.mark.integration
    def test_real_youtube_url(self):
        """Test with a real YouTube URL (requires internet connection)."""
        # This test is marked as integration and will be skipped in unit tests
        # Use a well-known public video
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"  # Rick Roll - always available
        
        metadata, error = metadata_fetcher.fetch_metadata(url)
        
        if error is None:
            assert metadata is not None
            assert metadata.title is not None
            assert metadata.channel is not None
            assert metadata.duration_sec > 0
        else:
            # If it fails, it should be a known error type
            assert error.code in ["VIDEO_UNAVAILABLE", "VIDEO_PRIVATE", "METADATA_ERROR"]
