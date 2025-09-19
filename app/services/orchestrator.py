"""
Orchestrator service to coordinate the complete video analysis workflow.
"""
import logging
import asyncio
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

from app.models import (
    VideoResult, VideoMetadata, Transcripts, Summaries, 
    TranscriptChunk, ErrorInfo, AnalysisOptions
)
from app.logging import log_with_context
from app.services.metadata_fetcher import metadata_fetcher
from app.services.transcript_fetcher import transcript_fetcher
from app.services.transcript_chunker import default_chunker
from app.services.summarization_service import SummarizationService, SummarizationConfig

logger = logging.getLogger(__name__)


@dataclass
class ProcessingStats:
    """Statistics for processing a single video."""
    start_time: datetime
    end_time: Optional[datetime] = None
    metadata_fetch_time: Optional[float] = None
    transcript_fetch_time: Optional[float] = None
    chunking_time: Optional[float] = None
    summarization_time: Optional[float] = None
    total_time: Optional[float] = None
    
    def complete(self):
        """Mark processing as complete and calculate total time."""
        self.end_time = datetime.now()
        if self.start_time:
            self.total_time = (self.end_time - self.start_time).total_seconds()


class VideoOrchestrator:
    """Orchestrates the complete video analysis workflow."""
    
    def __init__(self):
        """Initialize the orchestrator."""
        self.metadata_fetcher = metadata_fetcher
        self.transcript_fetcher = transcript_fetcher
        self.chunker = default_chunker
    
    async def process_video(self, url: str, options: AnalysisOptions) -> Tuple[VideoResult, ProcessingStats]:
        """
        Process a single video through the complete workflow.
        
        Args:
            url: YouTube video URL
            options: Analysis options
            
        Returns:
            Tuple of (result, processing_stats)
        """
        stats = ProcessingStats(start_time=datetime.now())
        video_id = "unknown"
        
        try:
            log_with_context("info", f"Starting video processing: {url}")
            
            # Step 1: Extract video ID
            video_id = self.metadata_fetcher.extract_video_id(url)
            if not video_id:
                return self._create_error_result(url, "unknown", "INVALID_URL", "Could not extract video ID"), stats
            
            # Step 2: Fetch metadata
            metadata, metadata_error = await self._fetch_metadata(url, video_id, stats)
            if metadata_error:
                return self._create_error_result(url, video_id, metadata_error.code, metadata_error.message), stats
            
            # Step 3: Fetch transcripts
            transcripts, transcript_error = await self._fetch_transcripts(url, video_id, options, stats)
            if transcript_error:
                log_with_context("warning", f"Transcript fetch failed: {transcript_error.message}")
                # Continue with metadata only
                transcripts = None
            
            # Step 4: Chunk transcripts
            es_chunks, en_chunks = await self._chunk_transcripts(transcripts, options, stats)
            
            # Step 5: Generate summaries
            summaries = await self._generate_summaries(es_chunks, en_chunks, options, stats)
            
            # Step 6: Create result
            result = VideoResult(
                url=url,
                video_id=video_id,
                status="ok",
                metadata=metadata,
                transcripts=transcripts,
                summaries=summaries,
                markdown=None  # TODO: Implement in response formatter
            )
            
            stats.complete()
            log_with_context("info", f"Successfully processed video: {url}")
            return result, stats
            
        except Exception as e:
            log_with_context("error", f"Unexpected error processing {url}: {str(e)}")
            stats.complete()
            return self._create_error_result(url, video_id, "PROCESSING_ERROR", str(e)), stats
    
    async def _fetch_metadata(self, url: str, video_id: str, stats: ProcessingStats) -> Tuple[Optional[VideoMetadata], Optional[ErrorInfo]]:
        """Fetch video metadata."""
        start_time = datetime.now()
        
        try:
            metadata, error = self.metadata_fetcher.fetch_metadata(url)
            stats.metadata_fetch_time = (datetime.now() - start_time).total_seconds()
            
            if error:
                log_with_context("error", f"Metadata fetch failed: {error.message}")
                return None, error
            
            log_with_context("info", f"Metadata fetched: {metadata.title}")
            return metadata, None
            
        except Exception as e:
            stats.metadata_fetch_time = (datetime.now() - start_time).total_seconds()
            log_with_context("error", f"Metadata fetch error: {str(e)}")
            return None, ErrorInfo(code="METADATA_ERROR", message=str(e))
    
    async def _fetch_transcripts(self, url: str, video_id: str, options: AnalysisOptions, stats: ProcessingStats) -> Tuple[Optional[Transcripts], Optional[ErrorInfo]]:
        """Fetch video transcripts."""
        start_time = datetime.now()
        
        try:
            transcripts, error = self.transcript_fetcher.fetch_transcripts(url, options.languages)
            stats.transcript_fetch_time = (datetime.now() - start_time).total_seconds()
            
            if error:
                log_with_context("warning", f"Transcript fetch failed: {error.message}")
                return None, error
            
            log_with_context("info", f"Transcripts fetched: {list(transcripts.__dict__.keys())}")
            return transcripts, None
            
        except Exception as e:
            stats.transcript_fetch_time = (datetime.now() - start_time).total_seconds()
            log_with_context("error", f"Transcript fetch error: {str(e)}")
            return None, ErrorInfo(code="TRANSCRIPT_ERROR", message=str(e))
    
    async def _chunk_transcripts(self, transcripts: Optional[Transcripts], options: AnalysisOptions, stats: ProcessingStats) -> Tuple[List[TranscriptChunk], List[TranscriptChunk]]:
        """Chunk transcripts for processing."""
        start_time = datetime.now()
        es_chunks = []
        en_chunks = []
        
        try:
            if transcripts:
                if transcripts.es:
                    es_chunks = self.chunker.chunk_transcript(transcripts.es, "es")
                    log_with_context("info", f"Created {len(es_chunks)} Spanish chunks")
                
                if transcripts.en:
                    en_chunks = self.chunker.chunk_transcript(transcripts.en, "en")
                    log_with_context("info", f"Created {len(en_chunks)} English chunks")
            
            stats.chunking_time = (datetime.now() - start_time).total_seconds()
            return es_chunks, en_chunks
            
        except Exception as e:
            stats.chunking_time = (datetime.now() - start_time).total_seconds()
            log_with_context("error", f"Chunking error: {str(e)}")
            return [], []
    
    async def _generate_summaries(self, es_chunks: List[TranscriptChunk], en_chunks: List[TranscriptChunk], options: AnalysisOptions, stats: ProcessingStats) -> Optional[Summaries]:
        """Generate summaries from chunks."""
        start_time = datetime.now()
        
        try:
            if not es_chunks and not en_chunks:
                log_with_context("info", "No chunks available for summarization")
                return None
            
            # Configure summarizer
            summarizer_config = SummarizationConfig(
                provider=options.provider,
                temperature=options.temperature,
                max_tokens=options.max_tokens
            )
            summarizer = SummarizationService(summarizer_config)
            
            # Generate summaries
            summaries, error = await summarizer.summarize_bilingual(es_chunks, en_chunks)
            stats.summarization_time = (datetime.now() - start_time).total_seconds()
            
            if error:
                log_with_context("warning", f"Summary generation failed: {error.message}")
                return None
            
            log_with_context("info", "Summaries generated successfully")
            return summaries
            
        except Exception as e:
            stats.summarization_time = (datetime.now() - start_time).total_seconds()
            log_with_context("error", f"Summary generation error: {str(e)}")
            return None
    
    def _create_error_result(self, url: str, video_id: str, error_code: str, error_message: str) -> VideoResult:
        """Create an error result."""
        return VideoResult(
            url=url,
            video_id=video_id,
            status="error",
            error={
                "code": error_code,
                "message": error_message
            }
        )


# Global instance
video_orchestrator = VideoOrchestrator()
