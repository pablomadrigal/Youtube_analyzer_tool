"""
Transcript chunker to split transcripts into manageable chunks for LLM processing.
"""
import logging
import re
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

from models import TranscriptData, TranscriptSegment
from app_logging import log_with_context

logger = logging.getLogger(__name__)


@dataclass
class ChunkingConfig:
    """Configuration for transcript chunking."""
    max_tokens: int = 2000
    max_chars: int = 8000
    overlap_tokens: int = 100
    preserve_boundaries: bool = True
    min_chunk_size: int = 100


@dataclass
class TranscriptChunk:
    """A chunk of transcript with metadata."""
    text: str
    segments: List[TranscriptSegment]
    start_time: float
    end_time: float
    token_count: int
    char_count: int
    chunk_index: int
    language: str


class TranscriptChunker:
    """Chunks transcripts into manageable pieces for LLM processing."""
    
    def __init__(self, config: ChunkingConfig = None):
        """Initialize the transcript chunker."""
        self.config = config or ChunkingConfig()
        self.token_estimator = TokenEstimator()
    
    def chunk_transcript(self, transcript_data: TranscriptData, language: str = "en") -> List[TranscriptChunk]:
        """
        Chunk a transcript into manageable pieces.
        
        Args:
            transcript_data: Transcript data to chunk
            language: Language of the transcript (for token estimation)
            
        Returns:
            List of transcript chunks
        """
        if not transcript_data or not transcript_data.segments:
            log_with_context("warning", "Empty transcript data provided for chunking")
            return []
        
        log_with_context("info", f"Chunking transcript with {len(transcript_data.segments)} segments")
        
        # Convert segments to text
        full_text = self._segments_to_text(transcript_data.segments)
        
        # Estimate total tokens
        total_tokens = self.token_estimator.estimate_tokens(full_text, language)
        log_with_context("info", f"Estimated total tokens: {total_tokens}")
        
        # If transcript is small enough, return as single chunk
        if total_tokens <= self.config.max_tokens:
            return [self._create_single_chunk(transcript_data, language, 0)]
        
        # Chunk the transcript
        chunks = self._create_chunks(transcript_data, language)
        
        log_with_context("info", f"Created {len(chunks)} chunks from transcript")
        return chunks
    
    def _create_single_chunk(self, transcript_data: TranscriptData, language: str, chunk_index: int) -> TranscriptChunk:
        """Create a single chunk from the entire transcript."""
        segments = transcript_data.segments
        text = self._segments_to_text(segments)
        
        return TranscriptChunk(
            text=text,
            segments=segments,
            start_time=segments[0].start if segments else 0.0,
            end_time=segments[-1].start + segments[-1].duration if segments else 0.0,
            token_count=self.token_estimator.estimate_tokens(text, language),
            char_count=len(text),
            chunk_index=chunk_index,
            language=language
        )
    
    def _create_chunks(self, transcript_data: TranscriptData, language: str) -> List[TranscriptChunk]:
        """Create multiple chunks from transcript data."""
        segments = transcript_data.segments
        chunks = []
        chunk_index = 0
        
        current_chunk_segments = []
        current_text = ""
        current_tokens = 0
        
        for segment in segments:
            segment_text = segment.text.strip()
            if not segment_text:
                continue
            
            # Add space if needed
            if current_text and not current_text.endswith(' '):
                segment_text = ' ' + segment_text
            
            # Estimate tokens for this segment
            segment_tokens = self.token_estimator.estimate_tokens(segment_text, language)
            
            # Check if adding this segment would exceed limits
            if (current_tokens + segment_tokens > self.config.max_tokens or 
                len(current_text + segment_text) > self.config.max_chars):
                
                # Create chunk from current segments
                if current_chunk_segments:
                    chunk = self._create_chunk_from_segments(
                        current_chunk_segments, chunk_index, language
                    )
                    chunks.append(chunk)
                    chunk_index += 1
                
                # Start new chunk
                current_chunk_segments = [segment]
                current_text = segment_text
                current_tokens = segment_tokens
            else:
                # Add to current chunk
                current_chunk_segments.append(segment)
                current_text += segment_text
                current_tokens += segment_tokens
        
        # Add final chunk if there are remaining segments
        if current_chunk_segments:
            chunk = self._create_chunk_from_segments(
                current_chunk_segments, chunk_index, language
            )
            chunks.append(chunk)
        
        return chunks
    
    def _create_chunk_from_segments(self, segments: List[TranscriptSegment], chunk_index: int, language: str) -> TranscriptChunk:
        """Create a chunk from a list of segments."""
        text = self._segments_to_text(segments)
        
        return TranscriptChunk(
            text=text,
            segments=segments,
            start_time=segments[0].start if segments else 0.0,
            end_time=segments[-1].start + segments[-1].duration if segments else 0.0,
            token_count=self.token_estimator.estimate_tokens(text, language),
            char_count=len(text),
            chunk_index=chunk_index,
            language=language
        )
    
    def _segments_to_text(self, segments: List[TranscriptSegment]) -> str:
        """Convert segments to plain text."""
        return ' '.join(segment.text.strip() for segment in segments if segment.text.strip())
    
    def get_chunk_summary(self, chunks: List[TranscriptChunk]) -> Dict[str, Any]:
        """Get summary information about chunks."""
        if not chunks:
            return {
                "total_chunks": 0,
                "total_tokens": 0,
                "total_chars": 0,
                "avg_tokens_per_chunk": 0,
                "avg_chars_per_chunk": 0,
                "duration_seconds": 0
            }
        
        total_tokens = sum(chunk.token_count for chunk in chunks)
        total_chars = sum(chunk.char_count for chunk in chunks)
        total_duration = chunks[-1].end_time - chunks[0].start_time if chunks else 0
        
        return {
            "total_chunks": len(chunks),
            "total_tokens": total_tokens,
            "total_chars": total_chars,
            "avg_tokens_per_chunk": total_tokens // len(chunks) if chunks else 0,
            "avg_chars_per_chunk": total_chars // len(chunks) if chunks else 0,
            "duration_seconds": total_duration
        }


class TokenEstimator:
    """Estimates token counts for different languages."""
    
    def __init__(self):
        """Initialize token estimator with language-specific rules."""
        # Rough token estimation rules (tokens ≈ words * 1.3 for English)
        self.language_multipliers = {
            'en': 1.3,  # English
            'es': 1.4,  # Spanish (slightly more tokens per word)
            'fr': 1.4,  # French
            'de': 1.5,  # German
            'it': 1.4,  # Italian
            'pt': 1.4,  # Portuguese
            'ru': 1.6,  # Russian (Cyrillic)
            'zh': 2.0,  # Chinese (characters)
            'ja': 2.0,  # Japanese
            'ko': 2.0,  # Korean
        }
    
    def estimate_tokens(self, text: str, language: str = "en") -> int:
        """
        Estimate token count for text in a given language.
        
        Args:
            text: Text to estimate tokens for
            language: Language code
            
        Returns:
            Estimated token count
        """
        if not text:
            return 0
        
        # Count words (split by whitespace)
        words = len(text.split())
        
        # Apply language-specific multiplier
        multiplier = self.language_multipliers.get(language, 1.3)
        
        # Add base overhead for punctuation and formatting
        estimated_tokens = int(words * multiplier) + 10
        
        return max(estimated_tokens, 1)  # At least 1 token
    
    def estimate_tokens_for_chunk(self, chunk: TranscriptChunk) -> int:
        """Estimate tokens for a specific chunk."""
        return self.estimate_tokens(chunk.text, chunk.language)


# Global instances
default_chunker = TranscriptChunker()
chunker_with_large_tokens = TranscriptChunker(ChunkingConfig(max_tokens=4000, max_chars=16000))
chunker_with_small_tokens = TranscriptChunker(ChunkingConfig(max_tokens=1000, max_chars=4000))
