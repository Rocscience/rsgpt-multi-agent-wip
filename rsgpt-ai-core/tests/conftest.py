"""Pytest configuration and shared fixtures"""

import os
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

# Set test environment before importing the app
os.environ["ENVIRONMENT"] = "testing"
os.environ["LOG_LEVEL"] = "DEBUG"
os.environ["CORS_ORIGINS"] = "http://localhost:3000"

# Mock API keys to prevent initialization errors
os.environ["OPENAI_API_KEY"] = "test-openai-key"
os.environ["ANTHROPIC_API_KEY"] = "test-anthropic-key"
os.environ["PINECONE_API_KEY"] = "test-pinecone-key"
os.environ["PINECONE_INDEX_NAME"] = "test-index"
os.environ["COHERE_API_KEY"] = "test-cohere-key"

# Mock service tokens for authentication tests
os.environ["BE_SERVICE_TOKEN"] = "test-be-service-token-12345"
# Unified MCP token for all MCP servers (RS2, RSPile, etc.)
os.environ["MCP_SERVICE_TOKEN"] = "test-mcp-service-token-67890"

# Mock Auth0 settings for testing
os.environ["AUTH0_ACCEPTED_AUDIENCES"] = (
    "rsgpt-be-test-identifier,rsgpt-ai-core-test-identifier"
)

# Patch external services before importing the app to prevent initialization errors
_pinecone_patch = patch("pinecone.Pinecone", return_value=Mock())
_cohere_patch = patch("cohere.ClientV2", return_value=Mock())
_openai_patch = patch("openai.AsyncOpenAI", return_value=Mock())

_pinecone_patch.start()
_cohere_patch.start()
_openai_patch.start()

from app.config import settings
from app.main import app


@pytest.fixture
def client():
    """Create a test client for the FastAPI application"""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def mock_settings():
    """Mock settings for testing"""
    return Mock(
        environment="testing",
        api_title="Test AI Core API",
        api_version="0.1.0",
        debug=True,
        is_development=False,
        is_production=False,
        is_testing=True,
        cors_origins=["http://localhost:3000"],
        log_level="DEBUG",
        host="localhost",
        port=8090,
    )
