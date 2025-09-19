"""
Analysis API endpoints.
"""
import logging
from typing import List
from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse

from app.models import AnalysisRequest, AnalysisResponse, JobStatus, VideoResult, VideoMetadata, AggregationInfo, ConfigInfo
from app.logging import get_request_id, log_with_context
from app.config import config
from app.services.metadata_fetcher import metadata_fetcher
from app.services.transcript_fetcher import transcript_fetcher
from app.services.transcript_chunker import default_chunker

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["analysis"])


@router.post("/analyze", response_model=AnalysisResponse)
async def analyze_videos(request: AnalysisRequest):
    """
    Analyze one or more YouTube videos.
    
    This endpoint processes YouTube URLs and returns structured summaries
    with metadata, transcripts, and bilingual summaries.
    """
    request_id = get_request_id()
    
    log_with_context("info", f"Analysis request received: {len(request.urls)} URLs")
    
    # Validate provider configuration
    if not _validate_provider_config(request.options.provider):
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Provider configuration error",
                "message": f"Provider '{request.options.provider}' is not properly configured. "
                          f"Please check your API keys and provider settings.",
                "request_id": request_id
            }
        )
    
    try:
        results = []
        succeeded = 0
        failed = 0
        
        for url in request.urls:
            try:
                log_with_context("info", f"Processing URL: {url}")
                
                # Extract video ID
                video_id = metadata_fetcher.extract_video_id(str(url))
                if not video_id:
                    results.append(VideoResult(
                        url=str(url),
                        video_id="unknown",
                        status="error",
                        error={
                            "code": "INVALID_URL",
                            "message": "Could not extract video ID from URL"
                        }
                    ))
                    failed += 1
                    continue
                
                # Fetch metadata
                metadata, error = metadata_fetcher.fetch_metadata(str(url))
                if error:
                    results.append(VideoResult(
                        url=str(url),
                        video_id=video_id,
                        status="error",
                        error={
                            "code": error.code,
                            "message": error.message
                        }
                    ))
                    failed += 1
                    continue
                
                # Fetch transcripts
                transcripts, transcript_error = transcript_fetcher.fetch_transcripts(
                    str(url), 
                    request.options.languages
                )
                
                # If transcript fetching fails, we still continue with metadata only
                if transcript_error:
                    log_with_context("warning", f"Transcript fetch failed for {url}: {transcript_error.message}")
                    transcripts = None
                else:
                    # Chunk transcripts for processing
                    if transcripts:
                        log_with_context("info", f"Chunking transcripts for {url}")
                        
                        # Chunk Spanish transcript if available
                        if transcripts.es:
                            es_chunks = default_chunker.chunk_transcript(transcripts.es, "es")
                            log_with_context("info", f"Created {len(es_chunks)} Spanish chunks")
                        
                        # Chunk English transcript if available
                        if transcripts.en:
                            en_chunks = default_chunker.chunk_transcript(transcripts.en, "en")
                            log_with_context("info", f"Created {len(en_chunks)} English chunks")
                
                # Create successful result with metadata and transcripts
                result = VideoResult(
                    url=str(url),
                    video_id=video_id,
                    status="ok",
                    metadata=metadata,
                    transcripts=transcripts,
                    summaries=None,    # TODO: Implement in next task
                    markdown=None if not request.options.include_markdown else {
                        "summary_es": None,
                        "summary_en": None,
                        "transcript_es": None,
                        "transcript_en": None
                    }
                )
                
                results.append(result)
                succeeded += 1
                log_with_context("info", f"Successfully processed: {url}")
                
            except Exception as e:
                log_with_context("error", f"Error processing {url}: {str(e)}")
                results.append(VideoResult(
                    url=str(url),
                    video_id="unknown",
                    status="error",
                    error={
                        "code": "PROCESSING_ERROR",
                        "message": str(e)
                    }
                ))
                failed += 1
        
        response = AnalysisResponse(
            request_id=request_id,
            results=results,
            aggregation=AggregationInfo(
                total=len(request.urls),
                succeeded=succeeded,
                failed=failed
            ),
            config=ConfigInfo(
                provider=request.options.provider,
                temperature=request.options.temperature,
                max_tokens=request.options.max_tokens
            )
        )
        
        log_with_context("info", f"Analysis completed: {succeeded} succeeded, {failed} failed")
        return response
        
    except Exception as e:
        log_with_context("error", f"Analysis failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Analysis failed",
                "message": str(e),
                "request_id": request_id
            }
        )


def _validate_provider_config(provider: str) -> bool:
    """Validate that the provider is properly configured."""
    if provider.startswith("openai/"):
        return config.openai_api_key is not None
    elif provider.startswith("anthropic/"):
        return config.anthropic_api_key is not None
    else:
        # For now, assume other providers are valid
        return True
