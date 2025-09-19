"""
API router initialization.
"""
from fastapi import APIRouter
from api.analyze import router as analyze_router

# Create main API router
router = APIRouter()

# Include sub-routers
router.include_router(analyze_router)
