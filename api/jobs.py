"""
Async jobs API endpoints.
"""
import logging
from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse

from models import AnalysisRequest, JobStatus
from app_logging import get_request_id, log_with_context
from services.job_manager import job_manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["jobs"])


@router.post("/analyze", response_model=dict)
async def create_async_analysis(request: AnalysisRequest):
    """
    Create an async analysis job.
    
    Returns 202 with job ID for async processing.
    """
    request_id = get_request_id()
    
    log_with_context("info", f"Creating async analysis job: {len(request.urls)} URLs")
    
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


@router.get("/jobs/{job_id}", response_model=JobStatus)
async def get_job_status(job_id: str):
    """
    Get the status of an async job.
    
    Args:
        job_id: Job identifier
        
    Returns:
        Job status information
    """
    request_id = get_request_id()
    
    log_with_context("info", f"Getting status for job {job_id}")
    
    job_status = await job_manager.get_job_status(job_id)
    
    if not job_status:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "Job not found",
                "message": f"Job {job_id} does not exist",
                "request_id": request_id
            }
        )
    
    return job_status


@router.delete("/jobs/{job_id}")
async def cancel_job(job_id: str):
    """
    Cancel an async job.
    
    Args:
        job_id: Job identifier
        
    Returns:
        Cancellation status
    """
    request_id = get_request_id()
    
    log_with_context("info", f"Cancelling job {job_id}")
    
    cancelled = await job_manager.cancel_job(job_id)
    
    if not cancelled:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "Job not found or cannot be cancelled",
                "message": f"Job {job_id} does not exist or is already completed",
                "request_id": request_id
            }
        )
    
    return {
        "job_id": job_id,
        "status": "cancelled",
        "message": "Job cancelled successfully",
        "request_id": request_id
    }


@router.get("/jobs")
async def list_jobs():
    """
    Get job statistics and list.
    
    Returns:
        Job statistics and list
    """
    request_id = get_request_id()
    
    log_with_context("info", "Getting job statistics")
    
    stats = job_manager.get_job_count()
    
    return {
        "statistics": stats,
        "request_id": request_id
    }


def _validate_provider_config(provider: str) -> bool:
    """Validate that the provider is properly configured."""
    from config import config
    
    if provider.startswith("openai/"):
        return config.openai_api_key is not None
    elif provider.startswith("anthropic/"):
        return config.anthropic_api_key is not None
    else:
        # For now, assume other providers are valid
        return True
