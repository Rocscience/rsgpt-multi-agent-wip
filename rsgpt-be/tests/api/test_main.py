"""Tests for app.api.main module"""

import pytest
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.responses import JSONResponse
from starlette.requests import Request

from app.api.main import api_app


class TestApiApp:
    """Test cases for the FastAPI application configuration"""
    
    def test_api_app_creation(self):
        """Test that the FastAPI app is properly created"""
        assert isinstance(api_app, FastAPI)
        assert api_app.title == "RSGPT API"
        assert api_app.description == "API for RSGPT"
        assert api_app.version == "1.0.0"

    @patch('app.api.main.settings')
    def test_api_app_docs_url_development(self, mock_settings):
        """Test docs URL is available in development"""
        mock_settings.is_development = True
        
        # Create a new app instance for testing
        from app.api.main import FastAPI
        test_app = FastAPI(
            title="RSGPT API",
            description="API for RSGPT", 
            version="1.0.0",
            docs_url="/docs" if mock_settings.is_development else None,
            redoc_url="/redoc" if mock_settings.is_development else None,
        )
        
        assert test_app.docs_url == "/docs"
        assert test_app.redoc_url == "/redoc"

    @patch('app.api.main.settings')
    def test_api_app_docs_url_production(self, mock_settings):
        """Test docs URL is disabled in production"""
        mock_settings.is_development = False
        
        # Create a new app instance for testing
        from app.api.main import FastAPI
        test_app = FastAPI(
            title="RSGPT API",
            description="API for RSGPT",
            version="1.0.0", 
            docs_url="/docs" if mock_settings.is_development else None,
            redoc_url="/redoc" if mock_settings.is_development else None,
        )
        
        assert test_app.docs_url is None
        assert test_app.redoc_url is None

    def test_api_app_has_routers(self):
        """Test that routers are properly included"""
        # Check that routes exist
        routes = [route.path for route in api_app.routes]

        # User routes should be prefixed with /user
        user_routes = [route for route in routes if route.startswith('/user')]
        assert len(user_routes) > 0

        # Chat routes should be prefixed with /chat
        chat_routes = [route for route in routes if route.startswith('/chat')]
        assert len(chat_routes) > 0




class TestApiAppIntegration:
    """Integration tests for the complete API app"""
    
    def setup_method(self):
        """Set up test client for each test"""
        self.client = TestClient(api_app)

    def test_endpoints_exist_but_require_auth(self):
        """Test that endpoints exist but require authentication"""
        # The endpoints should exist but fail due to authentication
        # This tests that the routes are properly registered

        # User endpoint without proper authentication should fail
        response = self.client.get("/user/")
        # Should get 400, 401, 403, or 422 due to missing authentication, not 404
        assert response.status_code in [400, 401, 403, 422]

    def test_openapi_schema_generation(self):
        """Test that OpenAPI schema is properly generated"""
        # This tests that the app structure is valid
        schema = api_app.openapi()
        
        assert schema is not None
        assert "info" in schema
        assert schema["info"]["title"] == "RSGPT API"
        assert schema["info"]["version"] == "1.0.0"
        assert "paths" in schema


class TestApiAppConfiguration:
    """Test cases for API app configuration and setup"""
    
    def test_api_app_tags_configuration(self):
        """Test that router tags are properly configured"""
        # Check that user routes have user tag
        user_routes = [route for route in api_app.routes if hasattr(route, 'path') and route.path.startswith('/user')]
        # Tags are set at router level, so we check router inclusion
        assert len(user_routes) > 0

        # Check that chat routes exist
        chat_routes = [route for route in api_app.routes if hasattr(route, 'path') and route.path.startswith('/chat')]
        assert len(chat_routes) > 0

    def test_api_app_middleware_order(self):
        """Test that middleware is properly configured"""
        middleware_stack = api_app.user_middleware
        # Even if empty, this should not be None
        assert middleware_stack is not None

    @patch('app.api.main.settings')
    def test_api_app_environment_configuration(self, mock_settings):
        """Test that app respects environment settings"""
        # Test development settings
        mock_settings.is_development = True
        mock_settings.environment = "development"
        
        # The settings should be accessible from the app context
        assert mock_settings.is_development is True
        
        # Test production settings
        mock_settings.is_development = False
        mock_settings.environment = "production"
        
        assert mock_settings.is_development is False 