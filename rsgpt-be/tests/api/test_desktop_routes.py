"""Tests for Desktop API routes"""

import pytest
from unittest.mock import Mock, patch
from uuid import uuid4
from fastapi.testclient import TestClient
from fastapi import HTTPException
from botocore.exceptions import ClientError

from app.api.main import api_app
from app.models.mcp_registry import S3DownloadResponse
from app.services.desktop_service import (
    DesktopReleaseNotFoundError,
    DesktopInstallerNotFoundError
)
from app.dependencies import get_current_user


@pytest.fixture
def mock_current_user():
    """Mock current user for authentication"""
    return {
        "sub": str(uuid4()),
        "email": "test@example.com"
    }


@pytest.fixture
def client(mock_current_user):
    """Create a test client with mocked authentication"""
    # Override the get_current_user dependency to return our mock user
    api_app.dependency_overrides[get_current_user] = lambda: mock_current_user
    yield TestClient(api_app)
    # Clean up the override after the test
    api_app.dependency_overrides.clear()


@pytest.fixture
def unauthenticated_client():
    """Create a test client without authentication override"""
    # Clear any existing overrides
    api_app.dependency_overrides.clear()
    return TestClient(api_app)


@pytest.fixture
def mock_download_response():
    """Fixture for mock S3DownloadResponse"""
    return S3DownloadResponse(
        download_url="https://s3.amazonaws.com/presigned-url-test",
        checksum_sha256=None,
        filename="RSInsight Desktop Setup 1.0.6.exe",
        size_bytes=85000000
    )


class TestGetDesktopPresignedUrl:
    """Test cases for GET /desktop/get-presigned-url endpoint"""

    def test_get_presigned_url_success(self, client, mock_download_response):
        """Test successful retrieval of presigned URL with authentication"""
        with patch('app.api.routes.desktop.get_desktop_service') as mock_get_service:
            mock_service = Mock()
            mock_service.get_latest_release_presigned_url.return_value = mock_download_response
            mock_get_service.return_value = mock_service

            response = client.get("/desktop/get-presigned-url")

            assert response.status_code == 200
            data = response.json()
            assert data["download_url"] == mock_download_response.download_url
            assert data["filename"] == mock_download_response.filename
            assert data["size_bytes"] == mock_download_response.size_bytes
            assert data["checksum_sha256"] is None

    def test_get_presigned_url_release_not_found_returns_500(self, client):
        """Test 500 when no release is found in S3 (DesktopReleaseNotFoundError)"""
        with patch('app.api.routes.desktop.get_desktop_service') as mock_get_service:
            mock_service = Mock()
            mock_service.get_latest_release_presigned_url.side_effect = DesktopReleaseNotFoundError(
                "No desktop release found in s3://bucket/path"
            )
            mock_get_service.return_value = mock_service

            response = client.get("/desktop/get-presigned-url")

            assert response.status_code == 500
            data = response.json()
            assert "No release found in storage" in data["detail"]

    def test_get_presigned_url_installer_not_found_returns_500(self, client):
        """Test 500 when no installer file is found (DesktopInstallerNotFoundError)"""
        with patch('app.api.routes.desktop.get_desktop_service') as mock_get_service:
            mock_service = Mock()
            mock_service.get_latest_release_presigned_url.side_effect = DesktopInstallerNotFoundError(
                "No installer (.exe) file found in s3://bucket/path"
            )
            mock_get_service.return_value = mock_service

            response = client.get("/desktop/get-presigned-url")

            assert response.status_code == 500
            data = response.json()
            assert "Installer file missing" in data["detail"]

    def test_get_presigned_url_s3_error_returns_500(self, client):
        """Test 500 when S3 ClientError occurs"""
        with patch('app.api.routes.desktop.get_desktop_service') as mock_get_service:
            mock_service = Mock()
            error_response = {'Error': {'Code': 'AccessDenied', 'Message': 'Access Denied'}}
            mock_service.get_latest_release_presigned_url.side_effect = ClientError(
                error_response, 'ListObjectsV2'
            )
            mock_get_service.return_value = mock_service

            response = client.get("/desktop/get-presigned-url")

            assert response.status_code == 500
            data = response.json()
            assert "Failed to generate download URL" in data["detail"]

    def test_get_presigned_url_generic_error_returns_500(self, client):
        """Test 500 when generic exception occurs"""
        with patch('app.api.routes.desktop.get_desktop_service') as mock_get_service:
            mock_service = Mock()
            mock_service.get_latest_release_presigned_url.side_effect = Exception("Unexpected error")
            mock_get_service.return_value = mock_service

            response = client.get("/desktop/get-presigned-url")

            assert response.status_code == 500
            data = response.json()
            assert "Failed to generate download URL" in data["detail"]

    def test_endpoint_path_is_correct(self, client, mock_download_response):
        """Test that endpoint is accessible at the expected path"""
        with patch('app.api.routes.desktop.get_desktop_service') as mock_get_service:
            mock_service = Mock()
            mock_service.get_latest_release_presigned_url.return_value = mock_download_response
            mock_get_service.return_value = mock_service

            # Verify the endpoint is at /desktop/get-presigned-url
            response = client.get("/desktop/get-presigned-url")
            assert response.status_code == 200

            # Verify wrong path returns 404
            response = client.get("/desktop/presigned-url")
            assert response.status_code == 404

    def test_get_presigned_url_unauthenticated_returns_error(self, unauthenticated_client):
        """Test that unauthenticated users cannot access the endpoint"""
        # Without the dependency override, the real get_current_user will be called
        # which should return an error when no valid Authorization header is present
        response = unauthenticated_client.get("/desktop/get-presigned-url")

        # Should return 400, 401, or 403 depending on auth implementation
        # 400 = Bad Request (missing required auth parameter)
        # 401 = Unauthorized (invalid/missing token)
        # 403 = Forbidden (token valid but no access)
        assert response.status_code in [400, 401, 403]
        # Most importantly, verify it's NOT 200 (success)
        assert response.status_code != 200