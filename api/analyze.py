"""
Analysis API endpoints.
"""
import logging
from typing import List
from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse

from models import AnalysisRequest, AnalysisResponse, JobStatus
from app_logging import get_request_id, log_with_context
from config import config

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
        # TODO: Implement actual analysis logic
        # For now, return a placeholder response
        results = []
        
        for i, url in enumerate(request.urls):
            # Placeholder result - will be replaced with actual implementation
            result = {
                "url": str(url),
                "video_id": f"placeholder_{i}",
                "status": "ok",
                "metadata": {
                    "title": f"Placeholder Video {i+1}",
                    "channel": "Placeholder Channel",
                    "published_at": "2024-01-01T00:00:00Z",
                    "duration_sec": 300,
                    "url": str(url)
                },
                "transcripts": {
                    "es": None,
                    "en": None,
                    "unavailable": {}
                },
                "summaries": {
                    "es": None,
                    "en": None
                },
                "markdown": None if not request.options.include_markdown else {
                    "summary_es": None,
                    "summary_en": None,
                    "transcript_es": None,
                    "transcript_en": None
                }
            }
            results.append(result)
        
        response = AnalysisResponse(
            request_id=request_id,
            results=results,
            aggregation={
                "total": len(request.urls),
                "succeeded": len(results),
                "failed": 0
            },
            config={
                "provider": request.options.provider,
                "temperature": request.options.temperature,
                "max_tokens": request.options.max_tokens
            }
        )
        
        log_with_context("info", f"Analysis completed: {len(results)} results")
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
