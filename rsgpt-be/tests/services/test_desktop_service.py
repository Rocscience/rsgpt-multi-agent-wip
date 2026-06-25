"""Tests for Desktop service layer"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone, timedelta
from botocore.exceptions import ClientError

from app.services.desktop_service import (
    DesktopService,
    get_desktop_service,
    DESKTOP_LATEST_PREFIX,
    PRESIGNED_URL_EXPIRATION_SECONDS,
    DesktopReleaseNotFoundError,
    DesktopInstallerNotFoundError
)
from app.models.mcp_registry import S3DownloadResponse


@pytest.fixture
def desktop_service():
    """Fixture for Desktop service with mocked S3 client"""
    with patch('app.services.desktop_service.boto3') as mock_boto3:
        mock_s3_client = Mock()
        mock_boto3.client.return_value = mock_s3_client
        service = DesktopService()
        service.s3_client = mock_s3_client
        yield service


@pytest.fixture
def mock_s3_list_response():
    """Fixture for mock S3 list_objects_v2 response with latest release"""
    return {
        'Contents': [
            {
                'Key': 'rsinsight-desktop/latest/RSInsight Desktop Setup 1.0.6.exe',
                'Size': 85000000,
                'LastModified': datetime.now(timezone.utc)
            },
            {
                'Key': 'rsinsight-desktop/latest/RSInsight Desktop Setup 1.0.6.exe.blockmap',
                'Size': 100000,
                'LastModified': datetime.now(timezone.utc)
            }
        ]
    }


@pytest.fixture
def mock_s3_empty_response():
    """Fixture for mock S3 list_objects_v2 response with no objects"""
    return {}


class TestDesktopService:
    """Test cases for DesktopService"""

    def test_get_latest_release_presigned_url_success(self, desktop_service, mock_s3_list_response):
        """Test successful retrieval of latest release presigned URL"""
        # Setup
        desktop_service.s3_client.list_objects_v2.return_value = mock_s3_list_response

        mock_presigned_url = "https://s3.amazonaws.com/presigned-url"
        mock_expires_at = datetime.now(timezone.utc) + timedelta(seconds=PRESIGNED_URL_EXPIRATION_SECONDS)

        with patch('app.services.desktop_service.get_s3_service') as mock_get_s3:
            mock_s3_service = Mock()
            mock_s3_service.generate_presigned_url.return_value = (mock_presigned_url, mock_expires_at)
            mock_get_s3.return_value = mock_s3_service

            # Execute
            result = desktop_service.get_latest_release_presigned_url()

            # Verify
            assert result is not None
            assert isinstance(result, S3DownloadResponse)
            assert result.download_url == mock_presigned_url
            assert result.filename == "RSInsight Desktop Setup 1.0.6.exe"
            assert result.size_bytes == 85000000
            assert result.checksum_sha256 is None  # Not implemented yet

            # Verify presigned URL was generated with correct expiration
            mock_s3_service.generate_presigned_url.assert_called_once()
            call_kwargs = mock_s3_service.generate_presigned_url.call_args[1]
            assert call_kwargs['expires_in'] == PRESIGNED_URL_EXPIRATION_SECONDS

    def test_get_latest_release_presigned_url_no_objects_raises_error(self, desktop_service, mock_s3_empty_response):
        """Test that DesktopReleaseNotFoundError is raised when no objects in S3 bucket"""
        # Setup
        desktop_service.s3_client.list_objects_v2.return_value = mock_s3_empty_response

        # Execute & Verify
        with pytest.raises(DesktopReleaseNotFoundError) as exc_info:
            desktop_service.get_latest_release_presigned_url()

        assert "No desktop release found" in str(exc_info.value)

    def test_get_latest_release_presigned_url_no_exe_file_raises_error(self, desktop_service):
        """Test that DesktopInstallerNotFoundError is raised when no .exe file in latest folder"""
        # Setup - only non-exe files present
        desktop_service.s3_client.list_objects_v2.return_value = {
            'Contents': [
                {
                    'Key': 'rsinsight-desktop/latest/latest.yml',
                    'Size': 500,
                    'LastModified': datetime.now(timezone.utc)
                }
            ]
        }

        # Execute & Verify
        with pytest.raises(DesktopInstallerNotFoundError) as exc_info:
            desktop_service.get_latest_release_presigned_url()

        assert "No installer (.exe) file found" in str(exc_info.value)

    def test_get_latest_release_presigned_url_excludes_blockmap_raises_error(self, desktop_service):
        """Test that .blockmap files are correctly excluded and error raised if only blockmap exists"""
        # Setup - only blockmap file present
        desktop_service.s3_client.list_objects_v2.return_value = {
            'Contents': [
                {
                    'Key': 'rsinsight-desktop/latest/RSInsight Desktop Setup 1.0.6.exe.blockmap',
                    'Size': 100000,
                    'LastModified': datetime.now(timezone.utc)
                }
            ]
        }

        # Execute & Verify
        with pytest.raises(DesktopInstallerNotFoundError) as exc_info:
            desktop_service.get_latest_release_presigned_url()

        assert "No installer (.exe) file found" in str(exc_info.value)

    def test_get_latest_release_presigned_url_s3_error(self, desktop_service):
        """Test handling of S3 client errors"""
        # Setup
        error_response = {'Error': {'Code': 'AccessDenied', 'Message': 'Access Denied'}}
        desktop_service.s3_client.list_objects_v2.side_effect = ClientError(error_response, 'ListObjectsV2')

        # Execute & Verify
        with pytest.raises(ClientError):
            desktop_service.get_latest_release_presigned_url()

    def test_uses_correct_s3_prefix(self, desktop_service, mock_s3_list_response):
        """Test that the correct S3 prefix is used for listing"""
        # Setup
        desktop_service.s3_client.list_objects_v2.return_value = mock_s3_list_response

        mock_presigned_url = "https://s3.amazonaws.com/presigned-url"
        mock_expires_at = datetime.now(timezone.utc) + timedelta(seconds=PRESIGNED_URL_EXPIRATION_SECONDS)

        with patch('app.services.desktop_service.get_s3_service') as mock_get_s3:
            mock_s3_service = Mock()
            mock_s3_service.generate_presigned_url.return_value = (mock_presigned_url, mock_expires_at)
            mock_get_s3.return_value = mock_s3_service

            # Execute
            desktop_service.get_latest_release_presigned_url()

            # Verify - check that list_objects_v2 was called with correct prefix
            desktop_service.s3_client.list_objects_v2.assert_called_once()
            call_kwargs = desktop_service.s3_client.list_objects_v2.call_args[1]
            assert call_kwargs['Prefix'] == DESKTOP_LATEST_PREFIX

    def test_presigned_url_expiration_is_15_minutes(self):
        """Test that presigned URL expiration constant is 15 minutes (900 seconds)"""
        assert PRESIGNED_URL_EXPIRATION_SECONDS == 900


class TestGetDesktopService:
    """Test cases for get_desktop_service singleton function"""

    def test_returns_singleton_instance(self):
        """Test that get_desktop_service returns the same instance"""
        with patch('app.services.desktop_service.boto3'):
            # Reset singleton
            import app.services.desktop_service as desktop_module
            desktop_module._desktop_service_instance = None

            # Get instances
            service1 = get_desktop_service()
            service2 = get_desktop_service()

            # Verify same instance
            assert service1 is service2
