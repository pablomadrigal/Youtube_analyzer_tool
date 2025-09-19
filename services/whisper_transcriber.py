"""
Whisper transcription service using OpenAI's Whisper API for audio-to-text conversion.
"""
import os
import logging
from typing import Optional, Tuple, List
import openai
from models import TranscriptData, TranscriptSegment, ErrorInfo
from app_logging import log_with_context
from config import config

logger = logging.getLogger(__name__)


class WhisperTranscriber:
    """Transcribes audio files using OpenAI's Whisper API."""
    
    def __init__(self):
        """Initialize the Whisper transcriber."""
        if not config.openai_api_key:
            raise ValueError("OpenAI API key is required for Whisper transcription")
        
        self.client = openai.OpenAI(api_key=config.openai_api_key)
        self.max_file_size = 25 * 1024 * 1024  # 25MB limit for Whisper API
        self.supported_formats = ['.mp3', '.mp4', '.mpeg', '.mpga', '.m4a', '.wav', '.webm']
    
    def transcribe_audio(self, audio_file_path: str, language: str = None) -> Tuple[Optional[TranscriptData], Optional[ErrorInfo]]:
        """
        Transcribe audio file using OpenAI Whisper API.
        
        Args:
            audio_file_path: Path to the audio file
            language: Optional language code (e.g., 'en', 'es'). If None, auto-detect.
            
        Returns:
            Tuple of (transcript_data, error). If successful, transcript_data is populated and error is None.
            If failed, transcript_data is None and error contains error information.
        """
        try:
            # Validate file
            if not os.path.exists(audio_file_path):
                return None, ErrorInfo(
                    code="FILE_NOT_FOUND",
                    message="Audio file not found"
                )
            
            # Check file size
            file_size = os.path.getsize(audio_file_path)
            if file_size > self.max_file_size:
                return None, ErrorInfo(
                    code="FILE_TOO_LARGE",
                    message=f"Audio file size ({file_size / (1024*1024):.1f}MB) exceeds Whisper API limit (25MB)"
                )
            
            # Check file format
            file_ext = os.path.splitext(audio_file_path)[1].lower()
            if file_ext not in self.supported_formats:
                return None, ErrorInfo(
                    code="UNSUPPORTED_FORMAT",
                    message=f"Audio format '{file_ext}' is not supported by Whisper API"
                )
            
            log_with_context("info", f"Transcribing audio file: {audio_file_path} (language: {language or 'auto-detect'})")
            
            # Prepare transcription parameters
            transcription_params = {
                "model": "whisper-1",
                "response_format": "verbose_json",
            }
            
            if language:
                transcription_params["language"] = language
            
            # Transcribe the audio
            with open(audio_file_path, "rb") as audio_file:
                response = self.client.audio.transcriptions.create(
                    file=audio_file,
                    **transcription_params
                )
            
            # Convert response to our format
            transcript_data = self._convert_whisper_response(response, language)
            
            log_with_context("info", f"Successfully transcribed audio: {len(transcript_data.segments)} segments")
            return transcript_data, None
            
        except openai.RateLimitError:
            return None, ErrorInfo(
                code="RATE_LIMIT",
                message="OpenAI API rate limit exceeded. Please try again later."
            )
            
        except openai.AuthenticationError:
            return None, ErrorInfo(
                code="AUTH_ERROR",
                message="OpenAI API authentication failed. Please check your API key."
            )
            
        except openai.BadRequestError as e:
            if "file size" in str(e).lower():
                return None, ErrorInfo(
                    code="FILE_TOO_LARGE",
                    message="Audio file is too large for Whisper API"
                )
            else:
                return None, ErrorInfo(
                    code="BAD_REQUEST",
                    message=f"Invalid request to Whisper API: {str(e)}"
                )
                
        except Exception as e:
            log_with_context("error", f"Unexpected error transcribing audio: {str(e)}")
            return None, ErrorInfo(
                code="TRANSCRIPTION_ERROR",
                message=f"Unexpected error: {str(e)}"
            )
    
    def _convert_whisper_response(self, response, language: str = None) -> TranscriptData:
        """Convert Whisper API response to our TranscriptData format."""
        segments = []
        
        # Whisper API returns segments with word-level timing
        for segment in response.segments:
            transcript_segment = TranscriptSegment(
                text=segment.text.strip(),
                start=segment.start,
                duration=segment.end - segment.start
            )
            segments.append(transcript_segment)
        
        # Determine language (use detected language if not specified)
        detected_language = getattr(response, 'language', language or 'unknown')
        
        return TranscriptData(
            source="whisper",
            segments=segments,
            language=detected_language
        )
    
    def transcribe_with_chunking(self, audio_file_path: str, language: str = None, chunk_duration: int = 600) -> Tuple[Optional[TranscriptData], Optional[ErrorInfo]]:
        """
        Transcribe long audio files by chunking them (for files longer than 25MB).
        
        Args:
            audio_file_path: Path to the audio file
            language: Optional language code
            chunk_duration: Duration of each chunk in seconds (default: 10 minutes)
            
        Returns:
            Tuple of (transcript_data, error)
        """
        try:
            import librosa
            import soundfile as sf
            import numpy as np
            
            log_with_context("info", f"Transcribing long audio file with chunking: {audio_file_path}")
            
            # Load audio file
            audio_data, sample_rate = librosa.load(audio_file_path, sr=None)
            duration = len(audio_data) / sample_rate
            
            if duration <= chunk_duration:
                # File is short enough, use regular transcription
                return self.transcribe_audio(audio_file_path, language)
            
            # Split into chunks
            chunk_samples = int(chunk_duration * sample_rate)
            all_segments = []
            
            for i in range(0, len(audio_data), chunk_samples):
                chunk = audio_data[i:i + chunk_samples]
                chunk_start_time = i / sample_rate
                
                # Save chunk to temporary file
                chunk_path = f"{audio_file_path}_chunk_{i // chunk_samples}.wav"
                sf.write(chunk_path, chunk, sample_rate)
                
                try:
                    # Transcribe chunk
                    chunk_transcript, error = self.transcribe_audio(chunk_path, language)
                    if error:
                        log_with_context("warning", f"Failed to transcribe chunk {i // chunk_samples}: {error.message}")
                        continue
                    
                    # Adjust timestamps for chunk
                    for segment in chunk_transcript.segments:
                        segment.start += chunk_start_time
                    
                    all_segments.extend(chunk_transcript.segments)
                    
                finally:
                    # Clean up chunk file
                    if os.path.exists(chunk_path):
                        os.remove(chunk_path)
            
            if not all_segments:
                return None, ErrorInfo(
                    code="CHUNK_TRANSCRIPTION_FAILED",
                    message="Failed to transcribe any audio chunks"
                )
            
            transcript_data = TranscriptData(
                source="whisper_chunked",
                segments=all_segments,
                language=language or "unknown"
            )
            
            log_with_context("info", f"Successfully transcribed chunked audio: {len(all_segments)} segments")
            return transcript_data, None
            
        except ImportError:
            return None, ErrorInfo(
                code="MISSING_DEPENDENCIES",
                message="librosa and soundfile are required for chunked transcription"
            )
            
        except Exception as e:
            log_with_context("error", f"Error in chunked transcription: {str(e)}")
            return None, ErrorInfo(
                code="CHUNK_TRANSCRIPTION_ERROR",
                message=f"Chunked transcription failed: {str(e)}"
            )


# Global instance
whisper_transcriber = WhisperTranscriber()
