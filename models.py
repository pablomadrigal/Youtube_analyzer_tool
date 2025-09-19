"""
Pydantic models for request/response schemas.
"""
from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field, HttpUrl
from datetime import datetime
from dataclasses import dataclass


class TranscriptLine(BaseModel):
    """Individual transcript line with timing information."""
    start: float = Field(..., description="Start time in seconds")
    duration: float = Field(..., description="Duration in seconds")
    text: str = Field(..., description="Transcript text")


class TranscriptUnavailableError(Exception):
    """Exception raised when transcript is unavailable."""
    pass


class AnalysisOptions(BaseModel):
    """Options for video analysis."""
    include_markdown: bool = Field(default=False, description="Include Markdown fields in response")
    languages: List[str] = Field(default=["es", "en"], description="Languages for transcripts and summaries")
    provider: str = Field(default="openai/gpt-4o-mini", description="LLM provider and model")
    temperature: float = Field(default=0.2, ge=0.0, le=2.0, description="Temperature for LLM generation")
    max_tokens: int = Field(default=1200, gt=0, description="Maximum tokens for LLM generation")
    async_processing: bool = Field(default=False, description="Process asynchronously")


class AnalysisRequest(BaseModel):
    """Request model for video analysis."""
    urls: List[HttpUrl] = Field(..., min_items=1, description="YouTube URLs to analyze")
    options: Optional[AnalysisOptions] = Field(default_factory=AnalysisOptions, description="Analysis options")


class VideoMetadata(BaseModel):
    """Video metadata information."""
    title: str = Field(..., description="Video title")
    channel: str = Field(..., description="Channel name")
    published_at: str = Field(..., description="Publication date")
    duration_sec: int = Field(..., description="Duration in seconds")
    url: str = Field(..., description="Canonical video URL")


class TranscriptSegment(BaseModel):
    """Individual transcript segment."""
    text: str = Field(..., description="Transcript text")
    start: float = Field(..., description="Start time in seconds")
    duration: float = Field(..., description="Duration in seconds")


class TranscriptData(BaseModel):
    """Transcript data for a language."""
    source: str = Field(..., description="Source of transcript (auto/manual/whisper)")
    segments: List[TranscriptSegment] = Field(..., description="Transcript segments")
    language: Optional[str] = Field(default=None, description="Detected or specified language")


class Transcripts(BaseModel):
    """Transcripts in multiple languages."""
    es: Optional[TranscriptData] = Field(default=None, description="Spanish transcript")
    en: Optional[TranscriptData] = Field(default=None, description="English transcript")
    unavailable: Dict[str, str] = Field(default_factory=dict, description="Unavailable transcripts with reasons")


class SummaryData(BaseModel):
    """Structured summary data."""
    topics: List[str] = Field(..., description="Key topics")
    bullets: List[str] = Field(..., description="Key bullet points")
    quotes: List[str] = Field(..., description="Notable quotes")
    actions: List[str] = Field(..., description="Action items")


class Summaries(BaseModel):
    """Summaries in multiple languages."""
    es: Optional[SummaryData] = Field(default=None, description="Spanish summary")
    en: Optional[SummaryData] = Field(default=None, description="English summary")


class MarkdownFields(BaseModel):
    """Optional Markdown fields."""
    summary_es: Optional[str] = Field(default=None, description="Spanish summary in Markdown")
    summary_en: Optional[str] = Field(default=None, description="English summary in Markdown")
    transcript_es: Optional[str] = Field(default=None, description="Spanish transcript in Markdown")
    transcript_en: Optional[str] = Field(default=None, description="English transcript in Markdown")


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


class ErrorInfo(BaseModel):
    """Error information."""
    code: str = Field(..., description="Error code")
    message: str = Field(..., description="Human-readable error message")


class VideoResult(BaseModel):
    """Result for a single video."""
    url: str = Field(..., description="Original video URL")
    video_id: str = Field(..., description="YouTube video ID")
    status: str = Field(..., description="Processing status (ok/error)")
    metadata: Optional[VideoMetadata] = Field(default=None, description="Video metadata")
    transcripts: Optional[Transcripts] = Field(default=None, description="Video transcripts")
    summaries: Optional[Summaries] = Field(default=None, description="Video summaries")
    markdown: Optional[MarkdownFields] = Field(default=None, description="Markdown fields")
    error: Optional[ErrorInfo] = Field(default=None, description="Error information")


class AggregationInfo(BaseModel):
    """Aggregation information for batch processing."""
    total: int = Field(..., description="Total number of videos")
    succeeded: int = Field(..., description="Number of successful videos")
    failed: int = Field(..., description="Number of failed videos")


class ConfigInfo(BaseModel):
    """Configuration information."""
    provider: str = Field(..., description="LLM provider used")
    temperature: float = Field(..., description="Temperature used")
    max_tokens: int = Field(..., description="Max tokens used")


class AnalysisResponse(BaseModel):
    """Response model for video analysis."""
    request_id: str = Field(..., description="Unique request identifier")
    results: List[VideoResult] = Field(..., description="Results for each video")
    aggregation: AggregationInfo = Field(..., description="Aggregation information")
    config: ConfigInfo = Field(..., description="Configuration used")


class JobStatus(BaseModel):
    """Job status for async processing."""
    job_id: str = Field(..., description="Job identifier")
    status: str = Field(..., description="Job status (pending/running/completed/failed)")
    created_at: datetime = Field(..., description="Job creation time")
    completed_at: Optional[datetime] = Field(default=None, description="Job completion time")
    result: Optional[AnalysisResponse] = Field(default=None, description="Job result")
    error: Optional[ErrorInfo] = Field(default=None, description="Job error")
