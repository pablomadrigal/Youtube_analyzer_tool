"""
Tests for the summarization service.
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import json

from app.services.summarization_service import (
    SummarizationService, SummarizationConfig, PromptTemplates
)
from app.models import SummaryData, Summaries, TranscriptChunk, ErrorInfo


class TestPromptTemplates:
    """Test cases for PromptTemplates."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.templates = PromptTemplates()
    
    def test_get_spanish_prompt(self):
        """Test Spanish prompt generation."""
        text = "Este es un video sobre programación"
        prompt = self.templates._get_spanish_prompt(text)
        
        assert "Analiza el siguiente texto" in prompt
        assert "resumen estructurado en español" in prompt
        assert text in prompt
        assert "topics" in prompt
        assert "bullets" in prompt
        assert "quotes" in prompt
        assert "actions" in prompt
    
    def test_get_english_prompt(self):
        """Test English prompt generation."""
        text = "This is a video about programming"
        prompt = self.templates._get_english_prompt(text)
        
        assert "Analyze the following" in prompt
        assert "structured summary in English" in prompt
        assert text in prompt
        assert "topics" in prompt
        assert "bullets" in prompt
        assert "quotes" in prompt
        assert "actions" in prompt
    
    def test_get_summary_prompt_spanish(self):
        """Test getting Spanish prompt."""
        text = "Test text"
        prompt = self.templates.get_summary_prompt(text, "es")
        
        assert "español" in prompt
        assert text in prompt
    
    def test_get_summary_prompt_english(self):
        """Test getting English prompt."""
        text = "Test text"
        prompt = self.templates.get_summary_prompt(text, "en")
        
        assert "English" in prompt
        assert text in prompt


class TestSummarizationConfig:
    """Test cases for SummarizationConfig."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = SummarizationConfig()
        
        assert config.provider == "openai/gpt-4o-mini"
        assert config.temperature == 0.2
        assert config.max_tokens == 1200
        assert config.timeout == 30
        assert config.max_retries == 3
        assert config.retry_delay == 1.0
    
    def test_custom_config(self):
        """Test custom configuration values."""
        config = SummarizationConfig(
            provider="anthropic/claude-3",
            temperature=0.5,
            max_tokens=2000,
            timeout=60,
            max_retries=5,
            retry_delay=2.0
        )
        
        assert config.provider == "anthropic/claude-3"
        assert config.temperature == 0.5
        assert config.max_tokens == 2000
        assert config.timeout == 60
        assert config.max_retries == 5
        assert config.retry_delay == 2.0


class TestSummarizationService:
    """Test cases for SummarizationService."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.config = SummarizationConfig(
            provider="openai/gpt-4o-mini",
            temperature=0.2,
            max_tokens=100,
            timeout=5,
            max_retries=1
        )
        self.service = SummarizationService(self.config)
    
    def create_test_chunks(self, num_chunks: int = 3) -> List[TranscriptChunk]:
        """Create test transcript chunks."""
        chunks = []
        for i in range(num_chunks):
            chunks.append(TranscriptChunk(
                text=f"This is test chunk {i+1} with some content.",
                segments=[],
                start_time=float(i * 10),
                end_time=float((i + 1) * 10),
                token_count=20,
                char_count=50,
                chunk_index=i,
                language="en"
            ))
        return chunks
    
    def test_combine_chunks(self):
        """Test combining chunks into single text."""
        chunks = self.create_test_chunks(3)
        combined = self.service._combine_chunks(chunks)
        
        assert "This is test chunk 1" in combined
        assert "This is test chunk 2" in combined
        assert "This is test chunk 3" in combined
        assert "--- Chunk 2 ---" in combined
        assert "--- Chunk 3 ---" in combined
    
    def test_parse_json_summary(self):
        """Test parsing JSON-formatted summary."""
        json_summary = json.dumps({
            "topics": ["Programming", "Python"],
            "bullets": ["Learn Python basics", "Practice coding"],
            "quotes": ["Code is poetry"],
            "actions": ["Start coding", "Join community"]
        })
        
        summary = self.service._parse_json_summary(json_summary)
        
        assert summary.topics == ["Programming", "Python"]
        assert summary.bullets == ["Learn Python basics", "Practice coding"]
        assert summary.quotes == ["Code is poetry"]
        assert summary.actions == ["Start coding", "Join community"]
    
    def test_parse_text_summary(self):
        """Test parsing text-formatted summary."""
        text_summary = """
        Topics:
        - Programming
        - Python
        
        Key Points:
        - Learn Python basics
        - Practice coding
        
        Quotes:
        - Code is poetry
        
        Actions:
        - Start coding
        - Join community
        """
        
        summary = self.service._parse_text_summary(text_summary, "en")
        
        assert "Programming" in summary.topics
        assert "Learn Python basics" in summary.bullets
        assert "Code is poetry" in summary.quotes
        assert "Start coding" in summary.actions
    
    def test_parse_summary_fallback(self):
        """Test fallback parsing when JSON parsing fails."""
        invalid_json = "This is not valid JSON"
        summary = self.service._parse_summary(invalid_json, "en")
        
        assert summary is not None
        assert len(summary.topics) > 0
        assert len(summary.bullets) > 0
    
    @pytest.mark.asyncio
    async def test_summarize_transcript_success(self):
        """Test successful transcript summarization."""
        chunks = self.create_test_chunks(2)
        
        # Mock the LLM response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps({
            "topics": ["Test Topic"],
            "bullets": ["Test Bullet"],
            "quotes": ["Test Quote"],
            "actions": ["Test Action"]
        })
        
        with patch('litellm.completion', new_callable=AsyncMock) as mock_completion:
            mock_completion.return_value = mock_response
            
            summary, error = await self.service.summarize_transcript(chunks, "en")
            
            assert summary is not None
            assert error is None
            assert summary.topics == ["Test Topic"]
            assert summary.bullets == ["Test Bullet"]
    
    @pytest.mark.asyncio
    async def test_summarize_transcript_no_chunks(self):
        """Test summarization with no chunks."""
        summary, error = await self.service.summarize_transcript([], "en")
        
        assert summary is None
        assert error is not None
        assert error.code == "NO_CHUNKS"
    
    @pytest.mark.asyncio
    async def test_summarize_transcript_llm_failure(self):
        """Test summarization when LLM fails."""
        chunks = self.create_test_chunks(1)
        
        with patch('litellm.completion', new_callable=AsyncMock) as mock_completion:
            mock_completion.side_effect = Exception("LLM Error")
            
            summary, error = await self.service.summarize_transcript(chunks, "en")
            
            assert summary is None
            assert error is not None
            assert error.code == "SUMMARIZATION_ERROR"
    
    @pytest.mark.asyncio
    async def test_summarize_transcript_timeout(self):
        """Test summarization with timeout."""
        chunks = self.create_test_chunks(1)
        
        with patch('litellm.completion', new_callable=AsyncMock) as mock_completion:
            mock_completion.side_effect = asyncio.TimeoutError()
            
            summary, error = await self.service.summarize_transcript(chunks, "en")
            
            assert summary is None
            assert error is not None
            assert error.code == "SUMMARIZATION_ERROR"
    
    @pytest.mark.asyncio
    async def test_summarize_bilingual_success(self):
        """Test successful bilingual summarization."""
        es_chunks = self.create_test_chunks(1)
        en_chunks = self.create_test_chunks(1)
        
        # Mock LLM responses
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps({
            "topics": ["Test Topic"],
            "bullets": ["Test Bullet"],
            "quotes": ["Test Quote"],
            "actions": ["Test Action"]
        })
        
        with patch('litellm.completion', new_callable=AsyncMock) as mock_completion:
            mock_completion.return_value = mock_response
            
            summaries, error = await self.service.summarize_bilingual(es_chunks, en_chunks)
            
            assert summaries is not None
            assert error is None
            assert summaries.es is not None
            assert summaries.en is not None
    
    @pytest.mark.asyncio
    async def test_summarize_bilingual_partial_success(self):
        """Test bilingual summarization with partial success."""
        es_chunks = self.create_test_chunks(1)
        en_chunks = []
        
        # Mock LLM response for Spanish only
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps({
            "topics": ["Test Topic"],
            "bullets": ["Test Bullet"],
            "quotes": ["Test Quote"],
            "actions": ["Test Action"]
        })
        
        with patch('litellm.completion', new_callable=AsyncMock) as mock_completion:
            mock_completion.return_value = mock_response
            
            summaries, error = await self.service.summarize_bilingual(es_chunks, en_chunks)
            
            assert summaries is not None
            assert error is None
            assert summaries.es is not None
            assert summaries.en is None
    
    @pytest.mark.asyncio
    async def test_summarize_bilingual_no_chunks(self):
        """Test bilingual summarization with no chunks."""
        summaries, error = await self.service.summarize_bilingual([], [])
        
        assert summaries is None
        assert error is not None
        assert error.code == "NO_SUMMARIES"


class TestGlobalInstances:
    """Test global summarization service instances."""
    
    def test_default_summarizer(self):
        """Test default summarizer instance."""
        from app.services.summarization_service import default_summarizer
        
        assert default_summarizer is not None
        assert isinstance(default_summarizer, SummarizationService)
        assert default_summarizer.config.provider == "openai/gpt-4o-mini"
    
    def test_high_temp_summarizer(self):
        """Test high temperature summarizer."""
        from app.services.summarization_service import summarizer_with_high_temp
        
        assert summarizer_with_high_temp is not None
        assert summarizer_with_high_temp.config.temperature == 0.7
    
    def test_low_temp_summarizer(self):
        """Test low temperature summarizer."""
        from app.services.summarization_service import summarizer_with_low_temp
        
        assert summarizer_with_low_temp is not None
        assert summarizer_with_low_temp.config.temperature == 0.1


class TestSummaryData:
    """Test cases for SummaryData model."""
    
    def test_summary_data_creation(self):
        """Test creating SummaryData instance."""
        summary = SummaryData(
            topics=["Topic 1", "Topic 2"],
            bullets=["Bullet 1", "Bullet 2"],
            quotes=["Quote 1"],
            actions=["Action 1", "Action 2"]
        )
        
        assert summary.topics == ["Topic 1", "Topic 2"]
        assert summary.bullets == ["Bullet 1", "Bullet 2"]
        assert summary.quotes == ["Quote 1"]
        assert summary.actions == ["Action 1", "Action 2"]
    
    def test_summary_data_empty(self):
        """Test creating empty SummaryData."""
        summary = SummaryData(
            topics=[],
            bullets=[],
            quotes=[],
            actions=[]
        )
        
        assert summary.topics == []
        assert summary.bullets == []
        assert summary.quotes == []
        assert summary.actions == []
