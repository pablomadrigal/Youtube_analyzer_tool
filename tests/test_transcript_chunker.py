"""
Tests for the transcript chunker.
"""
import pytest
from services.transcript_chunker import (
    TranscriptChunker, ChunkingConfig, TranscriptChunk, TokenEstimator
)
from models import TranscriptData, TranscriptSegment


class TestTokenEstimator:
    """Test cases for TokenEstimator."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.estimator = TokenEstimator()
    
    def test_estimate_tokens_english(self):
        """Test token estimation for English text."""
        text = "Hello world this is a test"
        tokens = self.estimator.estimate_tokens(text, "en")
        assert tokens > 0
        assert tokens >= len(text.split())  # Should be at least word count
    
    def test_estimate_tokens_spanish(self):
        """Test token estimation for Spanish text."""
        text = "Hola mundo esto es una prueba"
        tokens = self.estimator.estimate_tokens(text, "es")
        assert tokens > 0
        # Spanish should have slightly more tokens per word
        assert tokens >= len(text.split())
    
    def test_estimate_tokens_chinese(self):
        """Test token estimation for Chinese text."""
        text = "你好世界这是一个测试"
        tokens = self.estimator.estimate_tokens(text, "zh")
        assert tokens > 0
        # Chinese should have more tokens per character
        assert tokens >= len(text)
    
    def test_estimate_tokens_empty(self):
        """Test token estimation for empty text."""
        assert self.estimator.estimate_tokens("", "en") == 0
        assert self.estimator.estimate_tokens(None, "en") == 0
    
    def test_estimate_tokens_unknown_language(self):
        """Test token estimation for unknown language."""
        text = "Hello world"
        tokens = self.estimator.estimate_tokens(text, "unknown")
        assert tokens > 0
        # Should use default multiplier
        assert tokens >= len(text.split())


class TestTranscriptChunker:
    """Test cases for TranscriptChunker."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.config = ChunkingConfig(max_tokens=100, max_chars=500)
        self.chunker = TranscriptChunker(self.config)
    
    def create_test_transcript(self, num_segments: int = 5) -> TranscriptData:
        """Create a test transcript with specified number of segments."""
        segments = []
        for i in range(num_segments):
            segments.append(TranscriptSegment(
                text=f"This is segment {i+1} with some content to make it longer.",
                start=float(i * 10),
                duration=10.0
            ))
        return TranscriptData(source="manual", segments=segments)
    
    def test_chunk_small_transcript(self):
        """Test chunking a small transcript that fits in one chunk."""
        transcript = self.create_test_transcript(2)
        chunks = self.chunker.chunk_transcript(transcript, "en")
        
        assert len(chunks) == 1
        assert chunks[0].chunk_index == 0
        assert chunks[0].language == "en"
        assert chunks[0].text is not None
        assert len(chunks[0].segments) == 2
    
    def test_chunk_large_transcript(self):
        """Test chunking a large transcript that needs multiple chunks."""
        # Create a large transcript
        segments = []
        for i in range(20):  # 20 segments should exceed token limit
            segments.append(TranscriptSegment(
                text=f"This is a very long segment {i+1} with lots of content that should exceed the token limit when combined with other segments to force chunking.",
                start=float(i * 10),
                duration=10.0
            ))
        
        transcript = TranscriptData(source="manual", segments=segments)
        chunks = self.chunker.chunk_transcript(transcript, "en")
        
        assert len(chunks) > 1
        assert all(chunk.token_count <= self.config.max_tokens for chunk in chunks)
        assert all(chunk.char_count <= self.config.max_chars for chunk in chunks)
    
    def test_chunk_empty_transcript(self):
        """Test chunking an empty transcript."""
        transcript = TranscriptData(source="manual", segments=[])
        chunks = self.chunker.chunk_transcript(transcript, "en")
        
        assert len(chunks) == 0
    
    def test_chunk_none_transcript(self):
        """Test chunking a None transcript."""
        chunks = self.chunker.chunk_transcript(None, "en")
        assert len(chunks) == 0
    
    def test_chunk_preserves_boundaries(self):
        """Test that chunking preserves segment boundaries."""
        transcript = self.create_test_transcript(10)
        chunks = self.chunker.chunk_transcript(transcript, "en")
        
        # All segments should be accounted for
        total_segments = sum(len(chunk.segments) for chunk in chunks)
        assert total_segments == len(transcript.segments)
        
        # Segments should be in order
        all_segments = []
        for chunk in chunks:
            all_segments.extend(chunk.segments)
        
        for i in range(len(all_segments) - 1):
            assert all_segments[i].start <= all_segments[i + 1].start
    
    def test_chunk_timing_information(self):
        """Test that chunks have correct timing information."""
        transcript = self.create_test_transcript(5)
        chunks = self.chunker.chunk_transcript(transcript, "en")
        
        for chunk in chunks:
            assert chunk.start_time >= 0
            assert chunk.end_time > chunk.start_time
            assert chunk.start_time == chunk.segments[0].start
            assert chunk.end_time == chunk.segments[-1].start + chunk.segments[-1].duration
    
    def test_chunk_summary(self):
        """Test chunk summary generation."""
        transcript = self.create_test_transcript(10)
        chunks = self.chunker.chunk_transcript(transcript, "en")
        summary = self.chunker.get_chunk_summary(chunks)
        
        assert summary["total_chunks"] == len(chunks)
        assert summary["total_tokens"] > 0
        assert summary["total_chars"] > 0
        assert summary["avg_tokens_per_chunk"] > 0
        assert summary["avg_chars_per_chunk"] > 0
        assert summary["duration_seconds"] > 0
    
    def test_chunk_summary_empty(self):
        """Test chunk summary for empty chunks."""
        summary = self.chunker.get_chunk_summary([])
        
        assert summary["total_chunks"] == 0
        assert summary["total_tokens"] == 0
        assert summary["total_chars"] == 0
        assert summary["avg_tokens_per_chunk"] == 0
        assert summary["avg_chars_per_chunk"] == 0
        assert summary["duration_seconds"] == 0
    
    def test_different_languages(self):
        """Test chunking with different languages."""
        transcript = self.create_test_transcript(10)
        
        # Test English
        chunks_en = self.chunker.chunk_transcript(transcript, "en")
        assert all(chunk.language == "en" for chunk in chunks_en)
        
        # Test Spanish
        chunks_es = self.chunker.chunk_transcript(transcript, "es")
        assert all(chunk.language == "es" for chunk in chunks_es)
    
    def test_custom_config(self):
        """Test chunking with custom configuration."""
        custom_config = ChunkingConfig(
            max_tokens=50,
            max_chars=200,
            overlap_tokens=10
        )
        custom_chunker = TranscriptChunker(custom_config)
        
        transcript = self.create_test_transcript(15)
        chunks = custom_chunker.chunk_transcript(transcript, "en")
        
        # Should create more chunks due to smaller limits
        assert len(chunks) > 1
        assert all(chunk.token_count <= custom_config.max_tokens for chunk in chunks)
        assert all(chunk.char_count <= custom_config.max_chars for chunk in chunks)


class TestTranscriptChunk:
    """Test cases for TranscriptChunk dataclass."""
    
    def test_chunk_creation(self):
        """Test creating a transcript chunk."""
        segments = [
            TranscriptSegment(text="Hello", start=0.0, duration=2.0),
            TranscriptSegment(text="World", start=2.0, duration=2.0)
        ]
        
        chunk = TranscriptChunk(
            text="Hello World",
            segments=segments,
            start_time=0.0,
            end_time=4.0,
            token_count=10,
            char_count=11,
            chunk_index=0,
            language="en"
        )
        
        assert chunk.text == "Hello World"
        assert len(chunk.segments) == 2
        assert chunk.start_time == 0.0
        assert chunk.end_time == 4.0
        assert chunk.token_count == 10
        assert chunk.char_count == 11
        assert chunk.chunk_index == 0
        assert chunk.language == "en"


class TestChunkingConfig:
    """Test cases for ChunkingConfig."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = ChunkingConfig()
        
        assert config.max_tokens == 2000
        assert config.max_chars == 8000
        assert config.overlap_tokens == 100
        assert config.preserve_boundaries == True
        assert config.min_chunk_size == 100
    
    def test_custom_config(self):
        """Test custom configuration values."""
        config = ChunkingConfig(
            max_tokens=1000,
            max_chars=4000,
            overlap_tokens=50,
            preserve_boundaries=False,
            min_chunk_size=200
        )
        
        assert config.max_tokens == 1000
        assert config.max_chars == 4000
        assert config.overlap_tokens == 50
        assert config.preserve_boundaries == False
        assert config.min_chunk_size == 200


class TestGlobalInstances:
    """Test global chunker instances."""
    
    def test_default_chunker(self):
        """Test default chunker instance."""
        from services.transcript_chunker import default_chunker
        
        assert default_chunker is not None
        assert isinstance(default_chunker, TranscriptChunker)
        assert default_chunker.config.max_tokens == 2000
    
    def test_large_token_chunker(self):
        """Test chunker with large token limit."""
        from services.transcript_chunker import chunker_with_large_tokens
        
        assert chunker_with_large_tokens is not None
        assert chunker_with_large_tokens.config.max_tokens == 4000
    
    def test_small_token_chunker(self):
        """Test chunker with small token limit."""
        from services.transcript_chunker import chunker_with_small_tokens
        
        assert chunker_with_small_tokens is not None
        assert chunker_with_small_tokens.config.max_tokens == 1000
