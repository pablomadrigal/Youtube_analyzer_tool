"""
Security utilities for API authentication.
"""
import logging
from typing import Optional
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from config import config
from app_logging import log_with_context

logger = logging.getLogger(__name__)

# HTTP Bearer token scheme
security_scheme = HTTPBearer(
    scheme_name="API Token",
    description="Enter your API token",
    auto_error=False
)


def verify_api_token(token: str) -> bool:
    """
    Verify the provided API token against the configured static token.
    
    Args:
        token: The token to verify
        
    Returns:
        bool: True if token is valid, False otherwise
    """
    if not config.api_token:
        log_with_context("warning", "API token not configured - authentication disabled")
        return True  # Allow access if no token is configured
    
    if not token:
        return False
        
    return token == config.api_token


async def get_current_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme)):
    """
    FastAPI dependency to authenticate requests using static API token.
    
    Args:
        credentials: HTTP authorization credentials from the request
        
    Returns:
        dict: User information if authenticated
        
    Raises:
        HTTPException: If authentication fails
    """
    # If no token is configured, allow access (for development/testing)
    if not config.api_token:
        log_with_context("warning", "API token not configured - allowing access")
        return {"authenticated": True, "token_configured": False}
    
    # If no credentials provided, return 401
    if not credentials:
        log_with_context("warning", "Authentication required but no token provided")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Verify the token
    if not verify_api_token(credentials.credentials):
        log_with_context("warning", f"Invalid API token provided: {credentials.credentials[:8]}...")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    log_with_context("info", "Authentication successful")
    return {"authenticated": True, "token_configured": True}


def require_auth():
    """
    Decorator function to require authentication for endpoints.
    
    Returns:
        Dependency function for FastAPI
    """
    return Depends(get_current_user)
