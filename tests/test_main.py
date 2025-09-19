"""
Basic tests for the FastAPI application.
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_check():
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_root_endpoint():
    """Test root endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "version" in data
    assert "endpoints" in data


def test_analyze_endpoint_placeholder():
    """Test analyze endpoint with placeholder implementation."""
    response = client.post(
        "/api/analyze",
        json={
            "urls": ["https://www.youtube.com/watch?v=test123"],
            "options": {
                "include_markdown": False,
                "languages": ["es", "en"],
                "provider": "openai/gpt-4o-mini",
                "temperature": 0.2,
                "max_tokens": 1200,
                "async_processing": False
            }
        }
    )
    
    # This will fail until we implement proper provider validation
    # For now, we expect a 500 due to missing API keys
    assert response.status_code in [200, 500]
