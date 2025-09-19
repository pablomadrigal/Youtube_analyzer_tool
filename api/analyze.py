"""
Analysis API endpoints.
"""
import logging
import time
from typing import List
from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse

from models import AnalysisRequest, AnalysisResponse, JobStatus, VideoResult, VideoMetadata, AggregationInfo, ConfigInfo
from app_logging import get_request_id, log_with_context
from config import config
from services.metadata_fetcher import metadata_fetcher
from services.transcript_fetcher import transcript_fetcher
from services.transcript_chunker import default_chunker
from services.summarization_service import default_summarizer, SummarizationService, SummarizationConfig
from services.orchestrator import video_orchestrator
from services.response_formatter import response_formatter
from services.batch_processor import default_batch_processor
from services.observability import observability_service
from services.utils import validate_provider_config
from .security import require_auth

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["analysis"])


@router.post("/analyze", response_model=AnalysisResponse)
async def analyze_videos(request: AnalysisRequest, current_user: dict = require_auth()):
    """
    Analyze one or more YouTube videos.
    
    This endpoint processes YouTube URLs and returns structured summaries
    with metadata, transcripts, and bilingual summaries.
    """
    request_id = get_request_id()
    
    log_with_context("info", f"Analysis request received: {len(request.urls)} URLs")
    
    # Record request start
    start_time = time.time()
    
    # Validate provider configuration
    if not validate_provider_config(request.options.provider):
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Provider configuration error",
                "message": f"Provider '{request.options.provider}' is not properly configured. "
                          f"Please check your API keys and provider settings.",
                "request_id": request_id
            }
        )
    
    # Check if async processing is requested
    if request.options.async_processing:
        from services.job_manager import job_manager
        
        try:
            # Create async job
            job_id = await job_manager.create_job(request)
            
            log_with_context("info", f"Created async job {job_id}")
            
            return JSONResponse(
                status_code=202,
                content={
                    "job_id": job_id,
                    "status": "pending",
                    "message": "Analysis job created successfully",
                    "request_id": request_id
                }
            )
            
        except Exception as e:
            log_with_context("error", f"Failed to create async job: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail={
                    "error": "Job creation failed",
                    "message": str(e),
                    "request_id": request_id
                }
            )
    
    try:
        # Use batch processor for efficient processing
        response = await default_batch_processor.process_batch(
            [str(url) for url in request.urls],
            request.options,
            request_id
        )
        
        # Format results with optional Markdown
        if request.options.include_markdown:
            formatted_results = []
            for result in response.results:
                formatted_result = response_formatter.format_video_result(result, True)
                formatted_results.append(formatted_result)
            response.results = formatted_results
        
        # Record metrics
        processing_time = time.time() - start_time
        success = response.aggregation.failed == 0
        observability_service.record_request(
            request_type="analysis",
            success=success,
            processing_time=processing_time,
            error_code=None if success else "BATCH_FAILURE",
            provider=request.options.provider,
            languages=request.options.languages
        )
        
        log_with_context("info", f"Analysis completed: {response.aggregation.succeeded} succeeded, {response.aggregation.failed} failed")
        return response
        
    except Exception as e:
        # Record error metrics
        processing_time = time.time() - start_time
        observability_service.record_request(
            request_type="analysis",
            success=False,
            processing_time=processing_time,
            error_code="ANALYSIS_ERROR",
            provider=request.options.provider,
            languages=request.options.languages
        )
        
        log_with_context("error", f"Analysis failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Analysis failed",
                "message": str(e),
                "request_id": request_id
            }
        )


