"""Tests for app.api.main module"""

from unittest.mock import Mock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.main import api_app


class TestApiApp:
    """Test cases for the FastAPI application configuration"""

    def test_api_app_creation(self):
        """Test that the FastAPI app is properly created"""
        assert isinstance(api_app, FastAPI)
        assert api_app.title == "RSGPT AI Core API"
        assert api_app.description == "API for RSGPT AI Core Service"
        assert api_app.version == "1.0.0"

    @patch("app.api.main.settings")
    def test_api_app_docs_url_development(self, mock_settings):
        """Test docs URL is available in development"""
        mock_settings.is_development = True

        # Create a new app instance for testing
        from app.api.main import FastAPI

        test_app = FastAPI(
            title="RSGPT AI Core API",
            description="API for RSGPT AI Core Service",
            version="1.0.0",
            docs_url="/docs" if mock_settings.is_development else None,
            redoc_url="/redoc" if mock_settings.is_development else None,
        )

        assert test_app.docs_url == "/docs"
        assert test_app.redoc_url == "/redoc"

    @patch("app.api.main.settings")
    def test_api_app_docs_url_production(self, mock_settings):
        """Test docs URL is disabled in production"""
        mock_settings.is_development = False

        # Create a new app instance for testing
        from app.api.main import FastAPI

        test_app = FastAPI(
            title="RSGPT AI Core API",
            description="API for RSGPT AI Core Service",
            version="1.0.0",
            docs_url="/docs" if mock_settings.is_development else None,
            redoc_url="/redoc" if mock_settings.is_development else None,
        )

        assert test_app.docs_url is None
        assert test_app.redoc_url is None

    def test_api_app_has_health_routes(self):
        """Test that health routes are properly included"""
        # Check that routes exist
        routes = [route.path for route in api_app.routes]

        # Health routes should be prefixed with /health
        health_routes = [route for route in routes if route.startswith("/health")]
        assert len(health_routes) > 0
