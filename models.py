"""
Pydantic models for request/response schemas.
"""
from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field, HttpUrl
from datetime import datetime
from dataclasses import dataclass


# Language mapping for human-readable names
LANGUAGE_NAMES = {
    'en': 'English',
    'es': 'Español',
    'fr': 'Français',
    'de': 'Deutsch',
    'it': 'Italiano',
    'pt': 'Português',
    'ru': 'Русский',
    'zh': '中文',
    'ja': '日本語',
    'ko': '한국어',
    'ar': 'العربية',
    'hi': 'हिन्दी',
    'th': 'ไทย',
    'vi': 'Tiếng Việt',
    'tr': 'Türkçe',
    'pl': 'Polski',
    'nl': 'Nederlands',
    'sv': 'Svenska',
    'da': 'Dansk',
    'no': 'Norsk',
    'fi': 'Suomi',
    'cs': 'Čeština',
    'hu': 'Magyar',
    'ro': 'Română',
    'bg': 'Български',
    'hr': 'Hrvatski',
    'sk': 'Slovenčina',
    'sl': 'Slovenščina',
    'et': 'Eesti',
    'lv': 'Latviešu',
    'lt': 'Lietuvių',
    'mt': 'Malti',
    'cy': 'Cymraeg',
    'ga': 'Gaeilge',
    'eu': 'Euskera',
    'ca': 'Català',
    'gl': 'Galego'
}


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
    """Transcript in the original language of the video."""
    transcript: Optional[TranscriptData] = Field(default=None, description="Video transcript in original language")
    language: Optional[str] = Field(default=None, description="Language code of the transcript (e.g., 'en', 'es', 'fr')")
    language_name: Optional[str] = Field(default=None, description="Human-readable language name (e.g., 'English', 'Español')")
    available_languages: List[str] = Field(default_factory=list, description="List of all available transcript languages for this video")
    unavailable_reason: Optional[str] = Field(default=None, description="Reason if transcript is unavailable")


class FrameworkData(BaseModel):
    """Framework or method with step-by-step breakdown."""
    name: str = Field(..., description="Name of the framework or method")
    description: str = Field(..., description="Description of what the framework does")
    steps: List[str] = Field(..., description="Step-by-step breakdown of the framework")


class SummaryData(BaseModel):
    """Enhanced structured summary data with comprehensive insights."""
    summary: str = Field(..., description="2-3 paragraph executive summary of the core message and value")
    key_insights: List[str] = Field(..., description="8-12 most important insights as detailed paragraphs")
    frameworks: List[FrameworkData] = Field(default_factory=list, description="Actionable frameworks/methods with step-by-step breakdowns")
    key_moments: List[str] = Field(..., description="Chronological sequence of important events/topics discussed")
    
    # Legacy fields for backward compatibility
    topics: List[str] = Field(default_factory=list, description="Key topics (legacy)")
    bullets: List[str] = Field(default_factory=list, description="Key bullet points (legacy)")
    quotes: List[str] = Field(default_factory=list, description="Notable quotes (legacy)")
    actions: List[str] = Field(default_factory=list, description="Action items (legacy)")


class ChunkSummaryData(BaseModel):
    """Summary data for a single chunk with context information."""
    chunk_index: int = Field(..., description="Index of this chunk")
    start_time: float = Field(..., description="Start time of this chunk in seconds")
    end_time: float = Field(..., description="End time of this chunk in seconds")
    summary: str = Field(..., description="2-3 paragraph summary for this chunk")
    key_insights: List[str] = Field(..., description="Key insights from this chunk")
    frameworks: List[FrameworkData] = Field(default_factory=list, description="Frameworks mentioned in this chunk")
    key_moments: List[str] = Field(..., description="Important moments in this chunk")
    is_final_chunk: bool = Field(default=False, description="Whether this is the final chunk")


class Summaries(BaseModel):
    """Summaries in multiple languages."""
    es: Optional[SummaryData] = Field(default=None, description="Spanish summary")
    en: Optional[SummaryData] = Field(default=None, description="English summary")
    chunk_summaries: Optional[List[ChunkSummaryData]] = Field(default=None, description="Individual chunk summaries for markdown generation")


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
