"""
API router initialization.
"""
from fastapi import APIRouter
from app.api.analyze import router as analyze_router
from app.api.jobs import router as jobs_router
from app.api.monitoring import router as monitoring_router

# Create main API router
router = APIRouter()

# Include sub-routers
router.include_router(analyze_router)
router.include_router(jobs_router)
router.include_router(monitoring_router)
