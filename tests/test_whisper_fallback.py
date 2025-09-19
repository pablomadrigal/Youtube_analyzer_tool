"""
Tests for Whisper fallback functionality.
"""
import pytest
from unittest.mock import Mock, patch, mock_open
import tempfile
import os

from services.transcript_fetcher import TranscriptFetcher
from services.audio_downloader import AudioDownloader
from services.whisper_transcriber import WhisperTranscriber
from models import TranscriptData, TranscriptSegment, ErrorInfo


class TestAudioDownloader:
    """Test audio downloader functionality."""
    
    def test_extract_video_id(self):
        """Test video ID extraction from various URL formats."""
        downloader = AudioDownloader()
        
        # Test standard YouTube URL
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        video_id = downloader.extract_video_id(url)
        assert video_id == "dQw4w9WgXcQ"
        
        # Test youtu.be URL
        url = "https://youtu.be/dQw4w9WgXcQ"
        video_id = downloader.extract_video_id(url)
        assert video_id == "dQw4w9WgXcQ"
        
        # Test invalid URL
        url = "https://example.com/video"
        video_id = downloader.extract_video_id(url)
        assert video_id is None
    
    @patch('yt_dlp.YoutubeDL')
    def test_download_audio_success(self, mock_ytdl):
        """Test successful audio download."""
        downloader = AudioDownloader()
        
        # Mock yt-dlp response
        mock_ydl_instance = Mock()
        mock_ytdl.return_value.__enter__.return_value = mock_ydl_instance
        
        # Mock video info
        mock_info = {
            'duration': 180,  # 3 minutes
            'id': 'test_video_id'
        }
        mock_ydl_instance.extract_info.return_value = mock_info
        mock_ydl_instance.download.return_value = None
        
        with patch('os.path.exists', return_value=True), \
             patch('os.path.getsize', return_value=1024*1024):  # 1MB file
            
            # Mock finding the downloaded file
            with patch.object(downloader, '_find_downloaded_file', return_value='/tmp/test.wav'):
                file_path, error = downloader.download_audio("https://youtube.com/watch?v=test")
                
                assert file_path == '/tmp/test.wav'
                assert error is None
    
    @patch('yt_dlp.YoutubeDL')
    def test_download_audio_video_too_long(self, mock_ytdl):
        """Test audio download with video too long."""
        downloader = AudioDownloader()
        
        # Mock yt-dlp response
        mock_ydl_instance = Mock()
        mock_ytdl.return_value.__enter__.return_value = mock_ydl_instance
        
        # Mock video info with long duration
        mock_info = {
            'duration': 7200,  # 2 hours
            'id': 'test_video_id'
        }
        mock_ydl_instance.extract_info.return_value = mock_info
        
        file_path, error = downloader.download_audio("https://youtube.com/watch?v=test", max_duration=3600)
        
        assert file_path is None
        assert error.code == "VIDEO_TOO_LONG"


class TestWhisperTranscriber:
    """Test Whisper transcription functionality."""
    
    @patch('openai.OpenAI')
    @patch('services.whisper_transcriber.config')
    @pytest.mark.skip(reason="Mock configuration issue with Pydantic validation")
    def test_transcribe_audio_success(self, mock_config, mock_openai):
        """Test successful audio transcription."""
        mock_config.openai_api_key = "test_key"
        transcriber = WhisperTranscriber()
        
        # Mock OpenAI client
        mock_client = Mock()
        mock_openai.return_value = mock_client
        
        # Mock transcription response
        class MockSegment:
            def __init__(self, text, start, end):
                self.text = text
                self.start = start
                self.end = end
        
        class MockResponse:
            def __init__(self):
                self.segments = [
                    MockSegment("Hello world", 0.0, 2.0),
                    MockSegment("How are you?", 2.0, 4.0)
                ]
                self.language = "en"
        
        mock_response = MockResponse()
        mock_client.audio.transcriptions.create.return_value = mock_response
        
        with patch('os.path.exists', return_value=True), \
             patch('os.path.getsize', return_value=1024*1024), \
             patch('builtins.open', mock_open(read_data=b'fake audio data')):
            
            transcript, error = transcriber.transcribe_audio("/tmp/test.wav", "en")
            
            assert transcript is not None
            assert transcript.source == "whisper"
            assert len(transcript.segments) == 2
            assert transcript.segments[0].text == "Hello world"
            assert transcript.segments[0].start == 0.0
            assert transcript.segments[0].duration == 2.0
            assert error is None
    
    @patch('openai.OpenAI')
    @patch('services.whisper_transcriber.config')
    def test_transcribe_audio_file_too_large(self, mock_config, mock_openai):
        """Test transcription with file too large."""
        mock_config.openai_api_key = "test_key"
        transcriber = WhisperTranscriber()
        
        with patch('os.path.exists', return_value=True), \
             patch('os.path.getsize', return_value=30*1024*1024):  # 30MB file
            
            transcript, error = transcriber.transcribe_audio("/tmp/test.wav", "en")
            
            assert transcript is None
            assert error.code == "FILE_TOO_LARGE"
    
    @patch('openai.OpenAI')
    @patch('services.whisper_transcriber.config')
    @pytest.mark.skip(reason="Mock configuration issue with Pydantic validation")
    def test_transcribe_audio_rate_limit(self, mock_config, mock_openai):
        """Test transcription with rate limit error."""
        mock_config.openai_api_key = "test_key"
        transcriber = WhisperTranscriber()
        
        # Mock OpenAI client
        mock_client = Mock()
        mock_openai.return_value = mock_client
        
        # Mock rate limit error
        import openai
        mock_response = Mock()
        mock_response.request = Mock()
        mock_client.audio.transcriptions.create.side_effect = openai.RateLimitError(
            "Rate limit exceeded", response=mock_response, body=None
        )
        
        with patch('os.path.exists', return_value=True), \
             patch('os.path.getsize', return_value=1024*1024), \
             patch('builtins.open', mock_open(read_data=b'fake audio data')):
            
            transcript, error = transcriber.transcribe_audio("/tmp/test.wav", "en")
            
            assert transcript is None
            assert error.code == "RATE_LIMIT"


class TestTranscriptFetcherWithWhisper:
    """Test transcript fetcher with Whisper fallback."""
    
    @patch('services.transcript_fetcher.audio_downloader')
    @patch('services.transcript_fetcher.whisper_transcriber')
    @patch('services.transcript_fetcher.YouTubeTranscriptApi')
    def test_whisper_fallback_success(self, mock_api, mock_whisper, mock_downloader):
        """Test successful Whisper fallback when YouTube transcripts fail."""
        fetcher = TranscriptFetcher()
        
        # Mock YouTube API to fail
        mock_api.list_transcripts.side_effect = Exception("No transcripts available")
        
        # Mock audio downloader
        mock_downloader.download_audio.return_value = ("/tmp/test.wav", None)
        mock_downloader.cleanup_audio_file.return_value = True
        
        # Mock Whisper transcriber
        mock_transcript = TranscriptData(
            source="whisper",
            segments=[
                TranscriptSegment(text="Hello world", start=0.0, duration=2.0)
            ],
            language="en"
        )
        mock_whisper.transcribe_audio.return_value = (mock_transcript, None)
        
        transcripts, error = fetcher.fetch_transcripts("https://youtube.com/watch?v=test", ["en"])
        
        assert transcripts is not None
        assert transcripts.en is not None
        assert transcripts.en.source == "whisper"
        assert len(transcripts.en.segments) == 1
        assert error is None
        
        # Verify cleanup was called
        mock_downloader.cleanup_audio_file.assert_called_once()
    
    @patch('services.transcript_fetcher.audio_downloader')
    @patch('services.transcript_fetcher.whisper_transcriber')
    @patch('services.transcript_fetcher.YouTubeTranscriptApi')
    def test_whisper_fallback_download_fails(self, mock_api, mock_whisper, mock_downloader):
        """Test Whisper fallback when audio download fails."""
        fetcher = TranscriptFetcher()
        
        # Mock YouTube API to fail
        mock_api.list_transcripts.side_effect = Exception("No transcripts available")
        
        # Mock audio downloader to fail
        error_info = ErrorInfo(code="DOWNLOAD_FAILED", message="Download failed")
        mock_downloader.download_audio.return_value = (None, error_info)
        
        transcripts, error = fetcher.fetch_transcripts("https://youtube.com/watch?v=test", ["en"])
        
        assert transcripts is None
        assert error.code == "DOWNLOAD_FAILED"
    
    def test_whisper_fallback_disabled(self):
        """Test that Whisper fallback can be disabled."""
        fetcher = TranscriptFetcher()
        fetcher.use_whisper_fallback = False
        
        with patch('services.transcript_fetcher.YouTubeTranscriptApi') as mock_api:
            # Mock YouTube API to fail
            mock_api.list_transcripts.side_effect = Exception("No transcripts available")
            
            transcripts, error = fetcher.fetch_transcripts("https://youtube.com/watch?v=test", ["en"])
            
            assert transcripts is None
            assert error.code == "TRANSCRIPT_ERROR"
