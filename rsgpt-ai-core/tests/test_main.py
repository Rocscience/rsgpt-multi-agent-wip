"""Tests for main application endpoints"""

import pytest
from fastapi.testclient import TestClient


def test_root_endpoint(client):
    """Test root endpoint returns correct response"""
    response = client.get("/")
    assert response.status_code == 200

    data = response.json()
    assert "message" in data
    assert "environment" in data
    assert "version" in data
    assert data["message"] == "RSGPT AI Core API is running"


def test_health_endpoint(client):
    """Test health endpoint returns healthy status"""
    response = client.get("/health")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "rsgpt-ai-core"
    assert "environment" in data


def test_config_endpoint_development(client):
    """Test config endpoint returns configuration in development mode"""
    # This should work because test environment is set to development-like in conftest
    response = client.get("/config")

    # Should be forbidden because we're in testing mode, not development
    assert response.status_code == 403


def test_api_health_endpoint(client):
    """Test API health endpoint"""
    response = client.get("/api/v1/health/")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "rsgpt-ai-core"


def test_api_detailed_health_endpoint(client):
    """Test API detailed health endpoint"""
    response = client.get("/api/v1/health/detailed")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "healthy"
    assert "timestamp" in data
    assert "checks" in data
