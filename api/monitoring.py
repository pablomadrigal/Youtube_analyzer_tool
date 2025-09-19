"""
Monitoring and observability API endpoints.
"""
import logging
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from app_logging import get_request_id, log_with_context
from services.observability import observability_service
from services.job_manager import job_manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["monitoring"])


@router.get("/health")
async def health_check():
    """
    Comprehensive health check endpoint.
    
    Returns:
        Health status with detailed metrics
    """
    request_id = get_request_id()
    
    try:
        # Get health status
        health_status = observability_service.get_health_status()
        
        # Get job statistics
        job_stats = job_manager.get_job_count()
        
        # Combine health information
        health_info = {
            "service": "youtube-analyzer",
            "status": health_status["status"],
            "uptime": health_status["uptime_human"],
            "metrics": {
                "requests": {
                    "total": health_status["total_requests"],
                    "success_rate": health_status["success_rate"]
                },
                "jobs": job_stats
            },
            "issues": health_status["issues"],
            "timestamp": health_status["timestamp"],
            "request_id": request_id
        }
        
        # Return appropriate status code
        status_code = 200 if health_status["status"] == "healthy" else 503
        
        return JSONResponse(
            status_code=status_code,
            content=health_info
        )
        
    except Exception as e:
        log_with_context("error", f"Health check failed: {str(e)}")
        return JSONResponse(
            status_code=503,
            content={
                "service": "youtube-analyzer",
                "status": "unhealthy",
                "error": str(e),
                "request_id": request_id
            }
        )


@router.get("/metrics")
async def get_metrics():
    """
    Get detailed service metrics.
    
    Returns:
        Comprehensive metrics and statistics
    """
    request_id = get_request_id()
    
    try:
        metrics = observability_service.get_metrics()
        job_stats = job_manager.get_job_count()
        
        return {
            "metrics": metrics,
            "jobs": job_stats,
            "request_id": request_id
        }
        
    except Exception as e:
        log_with_context("error", f"Failed to get metrics: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Metrics retrieval failed",
                "message": str(e),
                "request_id": request_id
            }
        )


@router.get("/metrics/recent")
async def get_recent_requests(limit: int = 10):
    """
    Get recent request history.
    
    Args:
        limit: Maximum number of recent requests to return
        
    Returns:
        Recent request history
    """
    request_id = get_request_id()
    
    try:
        recent_requests = observability_service.get_recent_requests(limit)
        
        return {
            "recent_requests": recent_requests,
            "count": len(recent_requests),
            "request_id": request_id
        }
        
    except Exception as e:
        log_with_context("error", f"Failed to get recent requests: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Recent requests retrieval failed",
                "message": str(e),
                "request_id": request_id
            }
        )


@router.post("/metrics/reset")
async def reset_metrics():
    """
    Reset all metrics and statistics.
    
    Returns:
        Confirmation of reset
    """
    request_id = get_request_id()
    
    try:
        observability_service.reset_metrics()
        
        log_with_context("info", "Metrics reset requested")
        
        return {
            "message": "Metrics reset successfully",
            "request_id": request_id
        }
        
    except Exception as e:
        log_with_context("error", f"Failed to reset metrics: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Metrics reset failed",
                "message": str(e),
                "request_id": request_id
            }
        )


@router.get("/status")
async def get_status():
    """
    Get service status information.
    
    Returns:
        Service status and configuration
    """
    request_id = get_request_id()
    
    try:
        from config import config
        
        status_info = {
            "service": "youtube-analyzer",
            "version": "1.0.0",
            "configuration": {
                "log_level": config.log_level,
                "default_provider": config.default_provider,
                "default_temperature": config.default_temperature,
                "default_max_tokens": config.default_max_tokens,
                "request_timeout": config.request_timeout,
                "max_concurrent_requests": config.max_concurrent_requests
            },
            "endpoints": {
                "analyze": "/api/analyze",
                "jobs": "/api/jobs",
                "health": "/api/health",
                "metrics": "/api/metrics",
                "docs": "/docs"
            },
            "request_id": request_id
        }
        
        return status_info
        
    except Exception as e:
        log_with_context("error", f"Failed to get status: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Status retrieval failed",
                "message": str(e),
                "request_id": request_id
            }
        )
