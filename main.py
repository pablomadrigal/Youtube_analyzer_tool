"""
FastAPI main application.
"""
import logging
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager

from config import config
from app_logging import setup_logging, set_request_id, log_with_context
from models import AnalysisRequest, AnalysisResponse, JobStatus
from api.analyze import router

# Set up logging
setup_logging(config.log_level)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Starting YouTube Analyzer Service")
    logger.info(f"Configuration loaded: provider={config.default_provider}, "
                f"temperature={config.default_temperature}, "
                f"max_tokens={config.default_max_tokens}")
    
    yield
    
    # Shutdown
    logger.info("Shutting down YouTube Analyzer Service")


# Create FastAPI app
app = FastAPI(
    title="YouTube Analyzer Service",
    description="Service to analyze YouTube videos and generate bilingual summaries",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API router
app.include_router(router)


@app.middleware("http")
async def request_correlation_middleware(request: Request, call_next):
    """Middleware to add request correlation ID."""
    request_id = set_request_id()
    
    # Log request
    log_with_context("info", f"Request started: {request.method} {request.url}")
    
    try:
        response = await call_next(request)
        log_with_context("info", f"Request completed: {response.status_code}")
        return response
    except Exception as e:
        log_with_context("error", f"Request failed: {str(e)}")
        raise


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "youtube-analyzer"}


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "YouTube Analyzer Service",
        "version": "1.0.0",
        "endpoints": {
            "analyze": "/api/analyze",
            "health": "/health",
            "docs": "/docs"
        }
    }


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler."""
    request_id = get_request_id()
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "request_id": request_id,
            "message": "An unexpected error occurred"
        }
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8001,
        reload=True,
        log_level=config.log_level.lower()
    )
