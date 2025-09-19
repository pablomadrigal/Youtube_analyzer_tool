"""
Tests for the transcript fetcher.
"""
import pytest
from unittest.mock import patch, MagicMock
from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound, VideoUnavailable, TooManyRequests

from services.transcript_fetcher import TranscriptFetcher, transcript_fetcher
from models import TranscriptData, TranscriptSegment, Transcripts, ErrorInfo


class TestTranscriptFetcher:
    """Test cases for TranscriptFetcher."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.fetcher = TranscriptFetcher()
    
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
    
    @patch('youtube_transcript_api.YouTubeTranscriptApi.list_transcripts')
    def test_fetch_transcripts_success(self, mock_list_transcripts):
        """Test successful transcript fetching."""
        # Mock transcript list
        mock_transcript_list = MagicMock()
        mock_list_transcripts.return_value = mock_transcript_list
        
        # Mock transcript objects
        mock_es_transcript = MagicMock()
        mock_es_transcript.is_generated = False
        mock_es_transcript.fetch.return_value = [
            {'text': 'Hola mundo', 'start': 0.0, 'duration': 2.0},
            {'text': 'Este es un video', 'start': 2.0, 'duration': 3.0}
        ]
        
        mock_en_transcript = MagicMock()
        mock_en_transcript.is_generated = True
        mock_en_transcript.fetch.return_value = [
            {'text': 'Hello world', 'start': 0.0, 'duration': 2.0},
            {'text': 'This is a video', 'start': 2.0, 'duration': 3.0}
        ]
        
        # Mock find_transcript method
        def mock_find_transcript(languages):
            if 'es' in languages:
                return mock_es_transcript
            elif 'en' in languages:
                return mock_en_transcript
            else:
                raise NoTranscriptFound()
        
        mock_transcript_list.find_transcript.side_effect = mock_find_transcript
        
        url = "https://www.youtube.com/watch?v=test123"
        transcripts, error = self.fetcher.fetch_transcripts(url, ['es', 'en'])
        
        assert transcripts is not None
        assert error is None
        assert transcripts.es is not None
        assert transcripts.en is not None
        assert transcripts.es.source == "manual"
        assert transcripts.en.source == "auto"
        assert len(transcripts.es.segments) == 2
        assert len(transcripts.en.segments) == 2
    
    @patch('youtube_transcript_api.YouTubeTranscriptApi.list_transcripts')
    def test_fetch_transcripts_partial_success(self, mock_list_transcripts):
        """Test transcript fetching with partial success."""
        mock_transcript_list = MagicMock()
        mock_list_transcripts.return_value = mock_transcript_list
        
        # Only English transcript available
        mock_en_transcript = MagicMock()
        mock_en_transcript.is_generated = True
        mock_en_transcript.fetch.return_value = [
            {'text': 'Hello world', 'start': 0.0, 'duration': 2.0}
        ]
        
        def mock_find_transcript(languages):
            if 'en' in languages:
                return mock_en_transcript
            else:
                raise NoTranscriptFound()
        
        mock_transcript_list.find_transcript.side_effect = mock_find_transcript
        
        url = "https://www.youtube.com/watch?v=test123"
        transcripts, error = self.fetcher.fetch_transcripts(url, ['es', 'en'])
        
        assert transcripts is not None
        assert error is None
        assert transcripts.es is None
        assert transcripts.en is not None
        assert 'es' in transcripts.unavailable
        assert transcripts.unavailable['es'] == "not_available"
    
    @patch('youtube_transcript_api.YouTubeTranscriptApi.list_transcripts')
    def test_fetch_transcripts_no_transcripts(self, mock_list_transcripts):
        """Test handling when no transcripts are available."""
        mock_transcript_list = MagicMock()
        mock_list_transcripts.return_value = mock_transcript_list
        mock_transcript_list.find_transcript.side_effect = NoTranscriptFound()
        
        url = "https://www.youtube.com/watch?v=test123"
        transcripts, error = self.fetcher.fetch_transcripts(url, ['es', 'en'])
        
        assert transcripts is None
        assert error is not None
        assert error.code == "NO_TRANSCRIPTS"
    
    @patch('youtube_transcript_api.YouTubeTranscriptApi.list_transcripts')
    def test_fetch_transcripts_video_unavailable(self, mock_list_transcripts):
        """Test handling of unavailable videos."""
        mock_list_transcripts.side_effect = VideoUnavailable("test123")
        
        url = "https://www.youtube.com/watch?v=test123"
        transcripts, error = self.fetcher.fetch_transcripts(url, ['es', 'en'])
        
        assert transcripts is None
        assert error is not None
        assert error.code == "VIDEO_UNAVAILABLE"
    
    @patch('youtube_transcript_api.YouTubeTranscriptApi.list_transcripts')
    def test_fetch_transcripts_rate_limit(self, mock_list_transcripts):
        """Test handling of rate limiting."""
        mock_list_transcripts.side_effect = TooManyRequests()
        
        url = "https://www.youtube.com/watch?v=test123"
        transcripts, error = self.fetcher.fetch_transcripts(url, ['es', 'en'])
        
        assert transcripts is None
        assert error is not None
        assert error.code == "RATE_LIMIT"
    
    def test_fetch_transcripts_invalid_url(self):
        """Test handling of invalid URLs."""
        url = "https://www.google.com"
        transcripts, error = self.fetcher.fetch_transcripts(url, ['es', 'en'])
        
        assert transcripts is None
        assert error is not None
        assert error.code == "INVALID_URL"
    
    def test_find_transcript_manual_preference(self):
        """Test that manual transcripts are preferred over auto-generated."""
        # Mock transcript list with both manual and auto-generated
        mock_manual_transcript = MagicMock()
        mock_manual_transcript.is_generated = False
        mock_manual_transcript.language_code = 'es'
        
        mock_auto_transcript = MagicMock()
        mock_auto_transcript.is_generated = True
        mock_auto_transcript.language_code = 'es'
        
        mock_transcript_list = MagicMock()
        mock_transcript_list.__iter__ = MagicMock(return_value=iter([mock_manual_transcript, mock_auto_transcript]))
        
        result = self.fetcher._find_transcript(mock_transcript_list, 'es')
        assert result == mock_manual_transcript
    
    def test_find_transcript_fallback(self):
        """Test fallback logic when exact language not available."""
        # Mock transcript list with different language
        mock_transcript = MagicMock()
        mock_transcript.is_generated = True
        mock_transcript.language_code = 'en'
        
        mock_transcript_list = MagicMock()
        mock_transcript_list.__iter__ = MagicMock(return_value=iter([mock_transcript]))
        mock_transcript_list.find_transcript.side_effect = NoTranscriptFound()
        
        result = self.fetcher._find_transcript(mock_transcript_list, 'es')
        assert result == mock_transcript
    
    def test_format_transcript_as_text(self):
        """Test formatting transcript as text."""
        transcript_data = TranscriptData(
            source="manual",
            segments=[
                TranscriptSegment(text="Hello", start=0.0, duration=1.0),
                TranscriptSegment(text="World", start=1.0, duration=1.0)
            ]
        )
        
        result = self.fetcher.format_transcript_as_text(transcript_data)
        assert "Hello" in result
        assert "World" in result
    
    def test_format_transcript_empty(self):
        """Test formatting empty transcript."""
        transcript_data = TranscriptData(source="manual", segments=[])
        result = self.fetcher.format_transcript_as_text(transcript_data)
        assert result == ""
    
    @patch('youtube_transcript_api.YouTubeTranscriptApi.list_transcripts')
    def test_get_available_languages_success(self, mock_list_transcripts):
        """Test getting available languages."""
        mock_transcript1 = MagicMock()
        mock_transcript1.language_code = 'es'
        mock_transcript2 = MagicMock()
        mock_transcript2.language_code = 'en'
        
        mock_transcript_list = MagicMock()
        mock_transcript_list.__iter__ = MagicMock(return_value=iter([mock_transcript1, mock_transcript2]))
        mock_list_transcripts.return_value = mock_transcript_list
        
        url = "https://www.youtube.com/watch?v=test123"
        languages, error = self.fetcher.get_available_languages(url)
        
        assert languages is not None
        assert error is None
        assert 'es' in languages
        assert 'en' in languages
    
    def test_get_available_languages_invalid_url(self):
        """Test getting available languages with invalid URL."""
        url = "https://www.google.com"
        languages, error = self.fetcher.get_available_languages(url)
        
        assert languages is None
        assert error is not None
        assert error.code == "INVALID_URL"


class TestTranscriptFetcherIntegration:
    """Integration tests for transcript fetcher."""
    
    def test_global_instance(self):
        """Test that global instance is properly initialized."""
        assert transcript_fetcher is not None
        assert isinstance(transcript_fetcher, TranscriptFetcher)
    
    @pytest.mark.integration
    def test_real_youtube_url(self):
        """Test with a real YouTube URL (requires internet connection)."""
        # This test is marked as integration and will be skipped in unit tests
        # Use a well-known public video with transcripts
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"  # Rick Roll - usually has transcripts
        
        transcripts, error = transcript_fetcher.fetch_transcripts(url, ['en'])
        
        if error is None:
            assert transcripts is not None
            # At least one transcript should be available
            assert transcripts.en is not None or transcripts.es is not None
        else:
            # If it fails, it should be a known error type
            assert error.code in [
                "VIDEO_UNAVAILABLE", "NO_TRANSCRIPTS", "TRANSCRIPT_ERROR", 
                "RATE_LIMIT", "INVALID_URL"
            ]
