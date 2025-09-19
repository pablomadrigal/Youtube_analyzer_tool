"""
Tests for security functionality.
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch
from main import app


class TestSecurity:
    """Test security functionality."""
    
    @patch('config.config.api_token', 'test_token_123')
    def test_analyze_endpoint_without_token(self):
        """Test that analyze endpoint requires authentication."""
        client = TestClient(app)
        
        response = client.post(
            "/api/analyze",
            json={
                "urls": ["https://www.youtube.com/watch?v=test"],
                "options": {
                    "provider": "openai/gpt-4o-mini",
                    "languages": ["en"]
                }
            }
        )
        
        # Should return 401 Unauthorized when no token is provided
        assert response.status_code == 401
        assert "Authentication required" in response.json()["detail"]
    
    @patch('config.config.api_token', 'test_token_123')
    def test_analyze_endpoint_with_invalid_token(self):
        """Test that analyze endpoint rejects invalid tokens."""
        client = TestClient(app)
        
        response = client.post(
            "/api/analyze",
            json={
                "urls": ["https://www.youtube.com/watch?v=test"],
                "options": {
                    "provider": "openai/gpt-4o-mini",
                    "languages": ["en"]
                }
            },
            headers={"Authorization": "Bearer invalid_token"}
        )
        
        # Should return 401 Unauthorized for invalid token
        assert response.status_code == 401
        assert "Invalid authentication token" in response.json()["detail"]
    
    @patch('config.config.api_token', 'test_token_123')
    def test_analyze_endpoint_with_valid_token(self):
        """Test that analyze endpoint accepts valid tokens."""
        client = TestClient(app)
        
        # Mock the batch processor to avoid actual processing
        with patch('api.analyze.default_batch_processor.process_batch') as mock_process:
            mock_process.return_value = {
                "results": [],
                "aggregation": {"succeeded": 0, "failed": 1}
            }
            
            response = client.post(
                "/api/analyze",
                json={
                    "urls": ["https://www.youtube.com/watch?v=test"],
                    "options": {
                        "provider": "openai/gpt-4o-mini",
                        "languages": ["en"]
                    }
                },
                headers={"Authorization": "Bearer test_token_123"}
            )
            
            # Should not return 401 when valid token is provided
            assert response.status_code != 401
    
    @patch('config.config.api_token', None)
    def test_analyze_endpoint_no_token_configured(self):
        """Test that analyze endpoint allows access when no token is configured."""
        client = TestClient(app)
        
        # Mock the batch processor to avoid actual processing
        with patch('api.analyze.default_batch_processor.process_batch') as mock_process:
            mock_process.return_value = {
                "results": [],
                "aggregation": {"succeeded": 0, "failed": 1}
            }
            
            response = client.post(
                "/api/analyze",
                json={
                    "urls": ["https://www.youtube.com/watch?v=test"],
                    "options": {
                        "provider": "openai/gpt-4o-mini",
                        "languages": ["en"]
                    }
                }
            )
            
            # Should not return 401 when no token is configured
            assert response.status_code != 401
    
    def test_health_endpoint_no_auth_required(self):
        """Test that health endpoint doesn't require authentication."""
        client = TestClient(app)
        
        response = client.get("/health")
        
        # Should return 200 OK without authentication
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"
    
    def test_root_endpoint_no_auth_required(self):
        """Test that root endpoint doesn't require authentication."""
        client = TestClient(app)
        
        response = client.get("/")
        
        # Should return 200 OK without authentication
        assert response.status_code == 200
        data = response.json()
        assert "YouTube Analyzer Service" in data["message"]
        assert "authentication" in data
        assert "endpoints" in data
        assert "features" in data
        assert "supported_providers" in data
        
        # Check that analyze endpoint info includes authentication status
        analyze_endpoint = data["endpoints"]["analyze"]
        assert analyze_endpoint["path"] == "/api/analyze"
        assert analyze_endpoint["method"] == "POST"
        assert "authentication" in analyze_endpoint
    
    @patch('config.config.api_token', 'test_token_123')
    def test_root_endpoint_with_token_configured(self):
        """Test root endpoint response when API token is configured."""
        client = TestClient(app)
        
        response = client.get("/")
        
        assert response.status_code == 200
        data = response.json()
        
        # Check authentication section shows token is required
        auth_info = data["authentication"]
        assert auth_info["required"] is True
        assert auth_info["method"] == "Bearer Token"
        assert auth_info["header"] == "Authorization: Bearer <token>"
        
        # Check analyze endpoint shows authentication required
        analyze_endpoint = data["endpoints"]["analyze"]
        assert analyze_endpoint["authentication"] == "Required"
    
    @patch('config.config.api_token', None)
    def test_root_endpoint_without_token_configured(self):
        """Test root endpoint response when no API token is configured."""
        client = TestClient(app)
        
        response = client.get("/")
        
        assert response.status_code == 200
        data = response.json()
        
        # Check authentication section shows no token required
        auth_info = data["authentication"]
        assert auth_info["required"] is False
        assert auth_info["method"] == "None (development mode)"
        assert auth_info["header"] is None
        
        # Check analyze endpoint shows no authentication required
        analyze_endpoint = data["endpoints"]["analyze"]
        assert analyze_endpoint["authentication"] == "None"
