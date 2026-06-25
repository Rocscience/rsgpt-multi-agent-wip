"""Tests for MCP Registry API endpoints"""

import os
import pytest
from unittest.mock import Mock, patch
from uuid import uuid4
from datetime import datetime
from fastapi.testclient import TestClient

# Set test environment before importing the app
os.environ["ENVIRONMENT"] = "testing"
os.environ["DATABASE_URL"] = "sqlite:///./test.db"
os.environ["LOG_LEVEL"] = "DEBUG"

from app.main import app
from app.models.mcp_registry import (
    MCPRegistryListResponse,
    MCPRegistrySummary,
    MCPRegistryDetailResponse,
    MCPVersionInfo,
    MCPDownloadResponse,
    MCPInstallLogRequest,
    MCPInstallLogResponse
)


@pytest.fixture
def client():
    """Create a test client for the FastAPI application"""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def mock_current_user():
    """Mock current user for authentication"""
    user = Mock()
    user.id = uuid4()
    user.email = "test@example.com"
    return user


@pytest.fixture
def mock_mcp_summary():
    """Mock MCP summary for list responses"""
    return MCPRegistrySummary(
        id=uuid4(),
        name="test-mcp",
        display_name="Test MCP",
        description="Test description",
        category="dev-tools",
        author="Test Author",
        latest_version="1.0.0",
        downloads_count=100,
        is_official=True
    )


@pytest.fixture
def mock_mcp_detail():
    """Mock MCP detail response"""
    return MCPRegistryDetailResponse(
        id=uuid4(),
        name="test-mcp",
        display_name="Test MCP",
        description="Test description",
        category="dev-tools",
        author="Test Author",
        repo_url="https://github.com/test/test",
        latest_version="1.0.0",
        checksum_sha256="abc123",
        min_app_version="0.1.0",
        release_date=datetime.utcnow(),
        downloads_count=100,
        is_official=True,
        is_active=True,
        metadata={"key": "value"},
        versions=[
            MCPVersionInfo(
                version="1.0.0",
                release_date=datetime.utcnow(),
                release_notes="Initial release"
            )
        ],
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )


class TestMCPRegistryRoutes:
    """Test class for MCP Registry API routes"""

    @patch('app.api.routes.mcp_registry.get_current_user')
    @patch('app.api.routes.mcp_registry.mcp_service.get_mcp_list')
    def test_get_mcp_list_success(self, mock_get_list, mock_auth, client: TestClient,
                                  mock_current_user, mock_mcp_summary):
        """Test successful MCP list retrieval"""
        # Setup mocks
        mock_auth.return_value = mock_current_user
        mock_list_response = MCPRegistryListResponse(
            mcps=[mock_mcp_summary],
            total=1,
            page=1,
            pages=1
        )
        mock_get_list.return_value = mock_list_response

        # Make request
        response = client.get(
            "/api/v1/mcp/registry/list",
            params={
                "category": "dev-tools",
                "page": 1,
                "limit": 20
            }
        )

        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["mcps"]) == 1
        assert data["mcps"][0]["name"] == "test-mcp"

    @patch('app.api.routes.mcp_registry.get_current_user')
    @patch('app.api.routes.mcp_registry.mcp_service.get_mcp_list')
    def test_get_mcp_list_with_search(self, mock_get_list, mock_auth, client: TestClient,
                                      mock_current_user):
        """Test MCP list with search parameter"""
        mock_auth.return_value = mock_current_user
        mock_list_response = MCPRegistryListResponse(
            mcps=[],
            total=0,
            page=1,
            pages=0
        )
        mock_get_list.return_value = mock_list_response

        response = client.get(
            "/api/v1/mcp/registry/list",
            params={
                "search": "nonexistent",
                "official_only": True
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0

    @patch('app.api.routes.mcp_registry.get_current_user')
    @patch('app.api.routes.mcp_registry.mcp_service.get_mcp_list')
    def test_get_mcp_list_error(self, mock_get_list, mock_auth, client: TestClient,
                                mock_current_user):
        """Test MCP list with service error"""
        mock_auth.return_value = mock_current_user
        mock_get_list.side_effect = Exception("Service error")

        response = client.get("/api/v1/mcp/registry/list")

        assert response.status_code == 500
        assert "Failed to retrieve MCP list" in response.json()["detail"]

    @patch('app.api.routes.mcp_registry.get_current_user')
    @patch('app.api.routes.mcp_registry.mcp_service.get_mcp_details')
    def test_get_mcp_details_success(self, mock_get_details, mock_auth, client: TestClient,
                                     mock_current_user, mock_mcp_detail):
        """Test successful MCP details retrieval"""
        mock_auth.return_value = mock_current_user
        mock_get_details.return_value = mock_mcp_detail

        mcp_id = str(mock_mcp_detail.id)
        response = client.get(f"/api/v1/mcp/registry/details/{mcp_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "test-mcp"
        assert len(data["versions"]) == 1

    @patch('app.api.routes.mcp_registry.get_current_user')
    @patch('app.api.routes.mcp_registry.mcp_service.get_mcp_details')
    def test_get_mcp_details_not_found(self, mock_get_details, mock_auth, client: TestClient,
                                       mock_current_user):
        """Test MCP details for non-existent MCP"""
        mock_auth.return_value = mock_current_user
        mock_get_details.return_value = None

        mcp_id = str(uuid4())
        response = client.get(f"/api/v1/mcp/registry/details/{mcp_id}")

        assert response.status_code == 404
        assert "MCP not found" in response.json()["detail"]

    @patch('app.api.routes.mcp_registry.get_current_user')
    @patch('app.api.routes.mcp_registry.mcp_service.get_mcp_download_info')
    def test_get_mcp_download_info_success(self, mock_get_download, mock_auth, client: TestClient,
                                           mock_current_user):
        """Test successful download info retrieval"""
        mock_auth.return_value = mock_current_user
        mock_download_response = MCPDownloadResponse(
            download_url="https://s3.amazonaws.com/rsinsight-mcp-releases-test/test-mcp-v1.0.0.exe?signature=abc",
            checksum_sha256="abc123",
            filename="test-mcp-v1.0.0.exe",
            size_bytes=1024000
        )
        mock_get_download.return_value = mock_download_response

        mcp_id = str(uuid4())
        response = client.get(f"/api/v1/mcp/registry/download/{mcp_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["filename"] == "test-mcp-v1.0.0.exe"

    @patch('app.api.routes.mcp_registry.get_current_user')
    @patch('app.api.routes.mcp_registry.mcp_service.get_mcp_download_info')
    def test_get_mcp_download_info_with_version(self, mock_get_download, mock_auth,
                                                client: TestClient, mock_current_user):
        """Test download info for specific version"""
        mock_auth.return_value = mock_current_user
        mock_download_response = MCPDownloadResponse(
            download_url="https://s3.amazonaws.com/rsinsight-mcp-releases-test/test-mcp-v2.0.0.exe?signature=xyz",
            checksum_sha256="xyz789",
            filename="test-mcp-v2.0.0.exe",
            size_bytes=2048000
        )
        mock_get_download.return_value = mock_download_response

        mcp_id = str(uuid4())
        response = client.get(
            f"/api/v1/mcp/registry/download/{mcp_id}",
            params={"version": "2.0.0"}
        )

        assert response.status_code == 200
        data = response.json()

    @patch('app.api.routes.mcp_registry.get_current_user')
    @patch('app.api.routes.mcp_registry.mcp_service.get_mcp_download_info')
    def test_get_mcp_download_version_not_found(self, mock_get_download, mock_auth,
                                                client: TestClient, mock_current_user):
        """Test download info for non-existent version"""
        mock_auth.return_value = mock_current_user
        mock_get_download.return_value = None

        mcp_id = str(uuid4())
        response = client.get(
            f"/api/v1/mcp/registry/download/{mcp_id}",
            params={"version": "99.0.0"}
        )

        assert response.status_code == 404
        assert "Version 99.0.0 not found" in response.json()["detail"]

    # Install-log tests - Commented out as they require authenticated_client fixture
    # which needs proper Auth0 mocking. These tests verify JWT auth for install-log endpoint.
    # TODO: Re-enable when Auth0 mocking is properly implemented

    # @patch('app.api.routes.mcp_registry.mcp_service.log_mcp_installation')
    # def test_log_mcp_installation_success(self, mock_log_install, authenticated_client: TestClient):
    #     """Test successful installation logging with JWT auth"""
    #     install_id = uuid4()
    #     mock_log_response = MCPInstallLogResponse(
    #         id=install_id,
    #         mcp_id=uuid4(),
    #         device_id=uuid4(),
    #         version="1.0.0",
    #         action="install",
    #         installed_at=datetime.utcnow(),
    #         message="Successfully installed Test MCP v1.0.0"
    #     )
    #     mock_log_install.return_value = mock_log_response

    #     request_data = {
    #         "mcp_id": str(mock_log_response.mcp_id),
    #         "device_id": str(mock_log_response.device_id),
    #         "version": "1.0.0",
    #         "action": "install"
    #     }

    #     response = authenticated_client.post(
    #         "/api/v1/mcp/registry/install-log",
    #         json=request_data
    #     )

    #     assert response.status_code == 200
    #     data = response.json()
    #     assert "Successfully installed" in data["message"]

    # def test_log_mcp_installation_invalid_action(self, authenticated_client: TestClient):
    #     """Test installation logging with invalid action"""
    #     request_data = {
    #         "mcp_id": str(uuid4()),
    #         "device_id": str(uuid4()),
    #         "version": "1.0.0",
    #         "action": "invalid_action"
    #     }

    #     response = authenticated_client.post(
    #         "/api/v1/mcp/registry/install-log",
    #         json=request_data
    #     )

    #     assert response.status_code == 400
    #     assert "Invalid action" in response.json()["detail"]

    # # JWT Authentication Tests for install-log
    # @patch('app.api.routes.mcp_registry.mcp_service.log_mcp_installation')
    # def test_install_log_with_valid_jwt(self, mock_log_install, authenticated_client: TestClient):
    #     """Test install-log endpoint with valid JWT auth"""
    #     install_id = uuid4()
    #     mock_log_response = MCPInstallLogResponse(
    #         id=install_id,
    #         mcp_id=uuid4(),
    #         device_id=uuid4(),
    #         version="1.0.0",
    #         action="install",
    #         installed_at=datetime.utcnow(),
    #         message="Successfully installed Test MCP v1.0.0"
    #     )
    #     mock_log_install.return_value = mock_log_response

    #     request_data = {
    #         "mcp_id": str(mock_log_response.mcp_id),
    #         "device_id": str(mock_log_response.device_id),
    #         "version": "1.0.0",
    #         "action": "install"
    #     }

    #     response = authenticated_client.post(
    #         "/api/v1/mcp/registry/install-log",
    #         json=request_data
    #     )

    #     assert response.status_code == 200
    #     data = response.json()
    #     assert "Successfully installed" in data["message"]
    #     mock_log_install.assert_called_once()

    def test_install_log_without_auth(self, client: TestClient):
        """Test install-log endpoint without authentication"""
        request_data = {
            "mcp_id": str(uuid4()),
            "device_id": str(uuid4()),
            "version": "1.0.0",
            "action": "install"
        }

        response = client.post(
            "/api/v1/mcp/registry/install-log",
            json=request_data
        )

        # Without auth, should get 400 Bad Request (no Authorization header)
        assert response.status_code == 400

    # @patch('app.api.routes.mcp_registry.mcp_service.log_mcp_installation')
    # def test_install_log_different_actions(self, mock_log_install, authenticated_client: TestClient):
    #     """Test install-log endpoint with different valid actions"""
    #     actions = ["install", "update", "uninstall"]

    #     for action in actions:
    #         install_id = uuid4()
    #         mock_log_response = MCPInstallLogResponse(
    #             id=install_id,
    #             mcp_id=uuid4(),
    #             device_id=uuid4(),
    #             version="1.0.0",
    #             action=action,
    #             installed_at=datetime.utcnow(),
    #             message=f"Successfully {action}ed Test MCP v1.0.0"
    #         )
    #         mock_log_install.return_value = mock_log_response

    #         request_data = {
    #             "mcp_id": str(mock_log_response.mcp_id),
    #             "device_id": str(mock_log_response.device_id),
    #             "version": "1.0.0",
    #             "action": action
    #         }

    #         response = authenticated_client.post(
    #             "/api/v1/mcp/registry/install-log",
    #             json=request_data
    #         )

    #         assert response.status_code == 200
    #         data = response.json()
    #         assert action in data["message"].lower() or data["action"] == action

    # @patch('app.api.routes.mcp_registry.mcp_service.log_mcp_installation')
    # def test_log_mcp_installation_mcp_not_found(self, mock_log_install, authenticated_client: TestClient):
    #     """Test installation logging for non-existent MCP"""
    #     mock_log_install.side_effect = ValueError("MCP not found")

    #     request_data = {
    #         "mcp_id": str(uuid4()),
    #         "device_id": str(uuid4()),
    #         "version": "1.0.0",
    #         "action": "install"
    #     }

    #     response = authenticated_client.post(
    #         "/api/v1/mcp/registry/install-log",
    #         json=request_data
    #     )

    #     assert response.status_code == 400
    #     assert "MCP not found" in response.json()["detail"]

    # end of install-log tests

    @patch('app.api.routes.mcp_registry.get_current_user')
    @patch('app.api.routes.mcp_registry.mcp_service.get_mcp_download_info')
    def test_get_mcp_version_download_success(self, mock_get_download, mock_auth,
                                              client: TestClient, mock_current_user):
        """Test version-specific download endpoint"""
        mock_auth.return_value = mock_current_user
        mock_download_response = MCPDownloadResponse(
            download_url="https://s3.amazonaws.com/rsinsight-mcp-releases-test/test-mcp-v1.5.0.exe?signature=def",
            checksum_sha256="def456",
            filename="test-mcp-v1.5.0.exe",
            size_bytes=1536000
        )
        mock_get_download.return_value = mock_download_response

        mcp_id = str(uuid4())
        version = "1.5.0"
        response = client.get(f"/api/v1/mcp/registry/download/{mcp_id}/{version}")

        assert response.status_code == 200
        data = response.json()
        assert data["filename"] == "test-mcp-v1.5.0.exe"

    def test_unauthorized_access(self, client: TestClient):
        """Test unauthorized access to install-log endpoint (requires auth)"""
        # Test install-log endpoint which requires JWT auth
        request_data = {
            "mcp_id": str(uuid4()),
            "device_id": str(uuid4()),
            "version": "1.0.0",
            "action": "install"
        }

        response = client.post("/api/v1/mcp/registry/install-log", json=request_data)
        # Without auth, should get 400 (no Authorization header provided)
        assert response.status_code == 400

    @patch('app.config.settings.github_actions_service_token', 'test-github-token-123')
    @patch('app.api.routes.mcp_registry.mcp_service.register_mcp')
    def test_register_mcp_success_new(self, mock_register, client: TestClient):
        """Test successful new MCP registration"""
        from app.models.mcp_registry import MCPRegistryRegisterResponse

        mock_register.return_value = MCPRegistryRegisterResponse(
            success=True,
            mcp_id=uuid4(),
            message="MCP 'test-mcp' registered successfully",
            action="created"
        )

        request_data = {
            "name": "test-mcp",
            "display_name": "Test MCP",
            "description": "Test MCP server",
            "category": "dev-tools",
            "author": "Test Author",
            "repo_url": "https://github.com/test/test-mcp",
            "version": "1.0.0",
            "s3_bucket": "rsinsight-mcp-releases-staging",
            "s3_key": "test-mcp/v1.0.0/test-mcp-v1.0.0.exe",
            "file_size": 1024000,
            "checksums": {
                "windows": "abc123",
                "macos": "def456",
                "linux": "ghi789"
            },
            "s3_bucket": "rsinsight-mcp-releases-test",
            "s3_key": "test-mcp/v1.0.0/test-mcp-v1.0.0.exe",
            "is_official": True
        }

        response = client.post(
            "/api/v1/mcp/registry/register",
            json=request_data,
            headers={"X-Service-Token": "test-github-token-123"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["action"] == "created"

    @patch('app.config.settings.github_actions_service_token', 'test-github-token-123')
    @patch('app.api.routes.mcp_registry.mcp_service.register_mcp')
    def test_register_mcp_invalid_version(self, mock_register, client: TestClient):
        """Test MCP registration with invalid version format"""
        from app.models.mcp_registry import MCPRegistryRegisterResponse

        mock_register.return_value = MCPRegistryRegisterResponse(
            success=False,
            error="Invalid version format",
            message="Version 'invalid' is not a valid semantic version",
            details={"provided_version": "invalid"}
        )

        request_data = {
            "name": "test-mcp",
            "display_name": "Test MCP",
            "description": "Test MCP server",
            "category": "dev-tools",
            "author": "Test Author",
            "repo_url": "https://github.com/test/test-mcp",
            "version": "invalid",
            "s3_bucket": "rsinsight-mcp-releases-staging",
            "s3_key": "test-mcp/v1.0.0/test-mcp-v1.0.0.exe",
            "file_size": 1024000,
            "checksums": {
                "windows": "abc123"
            },
            "s3_bucket": "rsinsight-mcp-releases-test",
            "s3_key": "test-mcp/vinvalid/test-mcp-vinvalid.exe"
        }

        response = client.post(
            "/api/v1/mcp/registry/register",
            json=request_data,
            headers={"X-Service-Token": "test-github-token-123"}
        )

        assert response.status_code == 400
        data = response.json()
        assert "Invalid version format" in data["detail"]["error"]

    @patch('app.config.settings.github_actions_service_token', 'test-github-token-123')
    @patch('app.api.routes.mcp_registry.mcp_service.register_mcp')
    def test_register_mcp_version_conflict(self, mock_register, client: TestClient):
        """Test MCP registration with version not newer than current"""
        from app.models.mcp_registry import MCPRegistryRegisterResponse

        mock_register.return_value = MCPRegistryRegisterResponse(
            success=False,
            error="Version not newer",
            message="Version 1.0.0 is not newer than current version 1.5.0",
            details={
                "current_version": "1.5.0",
                "provided_version": "1.0.0"
            }
        )

        request_data = {
            "name": "test-mcp",
            "display_name": "Test MCP",
            "description": "Test MCP server",
            "category": "dev-tools",
            "author": "Test Author",
            "repo_url": "https://github.com/test/test-mcp",
            "version": "1.0.0",
            "s3_bucket": "rsinsight-mcp-releases-staging",
            "s3_key": "test-mcp/v1.0.0/test-mcp-v1.0.0.exe",
            "file_size": 1024000,
            "checksums": {
                "windows": "abc123"
            },
            "s3_bucket": "rsinsight-mcp-releases-test",
            "s3_key": "test-mcp/v1.0.0/test-mcp-v1.0.0.exe"
        }

        response = client.post(
            "/api/v1/mcp/registry/register",
            json=request_data,
            headers={"X-Service-Token": "test-github-token-123"}
        )

        assert response.status_code == 409  # Conflict
        data = response.json()
        assert "Version not newer" in data["detail"]["error"]

    @patch('app.config.settings.github_actions_service_token', 'test-github-token-123')
    @patch('app.api.routes.mcp_registry.mcp_service.register_mcp')
    def test_register_mcp_server_error(self, mock_register, client: TestClient):
        """Test MCP registration with unexpected server error"""
        mock_register.side_effect = Exception("Database connection failed")

        request_data = {
            "name": "test-mcp",
            "display_name": "Test MCP",
            "description": "Test MCP server",
            "category": "dev-tools",
            "author": "Test Author",
            "repo_url": "https://github.com/test/test-mcp",
            "version": "1.0.0",
            "s3_bucket": "rsinsight-mcp-releases-staging",
            "s3_key": "test-mcp/v1.0.0/test-mcp-v1.0.0.exe",
            "file_size": 1024000,
            "checksums": {
                "windows": "abc123"
            },
            "s3_bucket": "rsinsight-mcp-releases-test",
            "s3_key": "test-mcp/v1.0.0/test-mcp-v1.0.0.exe"
        }

        response = client.post(
            "/api/v1/mcp/registry/register",
            json=request_data,
            headers={"X-Service-Token": "test-github-token-123"}
        )

        assert response.status_code == 500
        data = response.json()
        assert "Internal server error" in data["detail"]["error"]

    # GitHub Actions Service Token Authentication Tests
    @patch('app.config.settings.github_actions_service_token', 'test-github-token-123')
    @patch('app.api.routes.mcp_registry.mcp_service.register_mcp')
    def test_register_mcp_with_valid_service_token(self, mock_register, client: TestClient):
        """Test MCP registration with valid GitHub Actions service token"""
        from app.models.mcp_registry import MCPRegistryRegisterResponse

        mock_register.return_value = MCPRegistryRegisterResponse(
            success=True,
            mcp_id=uuid4(),
            message="MCP 'test-mcp' registered successfully",
            action="created"
        )

        request_data = {
            "name": "test-mcp",
            "display_name": "Test MCP",
            "description": "Test MCP server",
            "category": "dev-tools",
            "author": "Test Author",
            "repo_url": "https://github.com/test/test-mcp",
            "version": "1.0.0",
            "s3_bucket": "rsinsight-mcp-releases-staging",
            "s3_key": "test-mcp/v1.0.0/test-mcp-v1.0.0.exe",
            "file_size": 1024000,
            "checksums": {
                "windows": "abc123"
            },
            "s3_bucket": "rsinsight-mcp-releases-test",
            "s3_key": "test-mcp/v1.0.0/test-mcp-v1.0.0.exe"
        }

        response = client.post(
            "/api/v1/mcp/registry/register",
            json=request_data,
            headers={"X-Service-Token": "test-github-token-123"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "registered successfully" in data["message"]
        mock_register.assert_called_once()

    @patch('app.config.settings.github_actions_service_token', 'test-github-token-123')
    def test_register_mcp_with_invalid_service_token(self, client: TestClient):
        """Test MCP registration with invalid GitHub Actions service token"""
        request_data = {
            "name": "test-mcp",
            "display_name": "Test MCP",
            "description": "Test MCP server",
            "category": "dev-tools",
            "author": "Test Author",
            "repo_url": "https://github.com/test/test-mcp",
            "version": "1.0.0",
            "s3_bucket": "rsinsight-mcp-releases-staging",
            "s3_key": "test-mcp/v1.0.0/test-mcp-v1.0.0.exe",
            "file_size": 1024000,
            "checksums": {
                "windows": "abc123"
            },
            "s3_bucket": "rsinsight-mcp-releases-test",
            "s3_key": "test-mcp/v1.0.0/test-mcp-v1.0.0.exe"
        }

        response = client.post(
            "/api/v1/mcp/registry/register",
            json=request_data,
            headers={"X-Service-Token": "wrong-token"}
        )

        assert response.status_code == 401
        assert "Invalid service token" in response.json()["detail"]

    def test_register_mcp_without_service_token(self, client: TestClient):
        """Test MCP registration without GitHub Actions service token"""
        request_data = {
            "name": "test-mcp",
            "display_name": "Test MCP",
            "description": "Test MCP server",
            "category": "dev-tools",
            "author": "Test Author",
            "repo_url": "https://github.com/test/test-mcp",
            "version": "1.0.0",
            "s3_bucket": "rsinsight-mcp-releases-staging",
            "s3_key": "test-mcp/v1.0.0/test-mcp-v1.0.0.exe",
            "file_size": 1024000,
            "checksums": {
                "windows": "abc123"
            },
            "s3_bucket": "rsinsight-mcp-releases-test",
            "s3_key": "test-mcp/v1.0.0/test-mcp-v1.0.0.exe"
        }

        response = client.post("/api/v1/mcp/registry/register", json=request_data)

        assert response.status_code == 422
        assert "Field required" in response.json()["detail"][0]["msg"]

    @patch('app.config.settings.github_actions_service_token', '')
    def test_register_mcp_service_token_not_configured(self, client: TestClient):
        """Test MCP registration when GitHub Actions service token is not configured"""
        request_data = {
            "name": "test-mcp",
            "display_name": "Test MCP",
            "description": "Test MCP server",
            "category": "dev-tools",
            "author": "Test Author",
            "repo_url": "https://github.com/test/test-mcp",
            "version": "1.0.0",
            "s3_bucket": "rsinsight-mcp-releases-staging",
            "s3_key": "test-mcp/v1.0.0/test-mcp-v1.0.0.exe",
            "file_size": 1024000,
            "checksums": {
                "windows": "abc123"
            },
            "s3_bucket": "rsinsight-mcp-releases-test",
            "s3_key": "test-mcp/v1.0.0/test-mcp-v1.0.0.exe"
        }

        response = client.post(
            "/api/v1/mcp/registry/register",
            json=request_data,
            headers={"X-Service-Token": "any-token"}
        )

        assert response.status_code == 500
        assert "Service authentication not configured" in response.json()["detail"]

    # ==================== Version Compatibility Tests ====================

    @patch('app.config.settings.github_actions_service_token', 'test-github-token-123')
    @patch('app.api.routes.mcp_registry.mcp_service.register_mcp')
    def test_register_mcp_with_version_compat_fields(self, mock_register, client: TestClient):
        """Test MCP registration with Rocscience version compatibility fields"""
        from app.models.mcp_registry import MCPRegistryRegisterResponse

        mock_register.return_value = MCPRegistryRegisterResponse(
            success=True,
            mcp_id=uuid4(),
            message="MCP 'rs2-server' registered successfully",
            action="created"
        )

        request_data = {
            "name": "rs2-server",
            "display_name": "RS2 MCP Server",
            "description": "MCP server for RS2 integration",
            "category": "automation",
            "author": "RSInsight",
            "repo_url": "https://github.com/rsinsight/rs2-mcp",
            "version": "1.0.0",
            "s3_bucket": "rsinsight-mcp-releases-staging",
            "s3_key": "rs2-server/v1.0.0/rs2-server-v1.0.0.exe",
            "file_size": 2048000,
            "checksums": {"windows": "abc123"},
            "is_official": True,
            # Version compatibility fields
            "rocscience_app": "RS2",
            "required_app_version": "11.0.2.7",
            "rocscience_app_path": "C:\\Program Files\\Rocscience\\RS2\\RS2.exe"
        }

        response = client.post(
            "/api/v1/mcp/registry/register",
            json=request_data,
            headers={"X-Service-Token": "test-github-token-123"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["action"] == "created"

        # Verify the service was called with version compat fields
        mock_register.assert_called_once()
        call_args = mock_register.call_args[0][0]
        assert call_args.rocscience_app == "RS2"
        assert call_args.required_app_version == "11.0.2.7"
        assert call_args.rocscience_app_path == "C:\\Program Files\\Rocscience\\RS2\\RS2.exe"

    @patch('app.config.settings.github_actions_service_token', 'test-github-token-123')
    @patch('app.api.routes.mcp_registry.mcp_service.register_mcp')
    def test_register_mcp_without_version_compat_fields(self, mock_register, client: TestClient):
        """Test MCP registration without version compatibility fields (optional)"""
        from app.models.mcp_registry import MCPRegistryRegisterResponse

        mock_register.return_value = MCPRegistryRegisterResponse(
            success=True,
            mcp_id=uuid4(),
            message="MCP 'generic-mcp' registered successfully",
            action="created"
        )

        request_data = {
            "name": "generic-mcp",
            "display_name": "Generic MCP Server",
            "description": "Generic MCP without version requirements",
            "category": "dev-tools",
            "author": "Author",
            "repo_url": "https://github.com/test/generic-mcp",
            "version": "1.0.0",
            "s3_bucket": "rsinsight-mcp-releases-staging",
            "s3_key": "generic-mcp/v1.0.0/generic-mcp-v1.0.0.exe",
            "file_size": 1024000,
            "checksums": {"windows": "xyz789"}
            # No version compatibility fields
        }

        response = client.post(
            "/api/v1/mcp/registry/register",
            json=request_data,
            headers={"X-Service-Token": "test-github-token-123"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

        # Verify the service was called without version compat fields
        mock_register.assert_called_once()
        call_args = mock_register.call_args[0][0]
        assert call_args.rocscience_app is None
        assert call_args.required_app_version is None
        assert call_args.rocscience_app_path is None

    @patch('app.api.routes.mcp_registry.get_current_user')
    @patch('app.api.routes.mcp_registry.mcp_service.get_mcp_list')
    def test_get_mcp_list_includes_version_compat_fields(
        self, mock_get_list, mock_auth, client: TestClient, mock_current_user
    ):
        """Test that MCP list endpoint returns version compatibility fields"""
        mock_auth.return_value = mock_current_user

        # Create mock summary with version compat fields
        mock_summary = MCPRegistrySummary(
            id=uuid4(),
            name="rs2-server",
            display_name="RS2 MCP Server",
            description="MCP server for RS2",
            category="automation",
            author="RSInsight",
            latest_version="1.0.0",
            downloads_count=50,
            is_official=True,
            rocscience_app="RS2",
            required_app_version="11.0.2.7",
            rocscience_app_path="C:\\Program Files\\Rocscience\\RS2\\RS2.exe"
        )

        mock_list_response = MCPRegistryListResponse(
            mcps=[mock_summary],
            total=1,
            page=1,
            pages=1
        )
        mock_get_list.return_value = mock_list_response

        response = client.get("/api/v1/mcp/registry/list")

        assert response.status_code == 200
        data = response.json()
        assert len(data["mcps"]) == 1
        mcp = data["mcps"][0]
        assert mcp["rocscience_app"] == "RS2"
        assert mcp["required_app_version"] == "11.0.2.7"
        assert mcp["rocscience_app_path"] == "C:\\Program Files\\Rocscience\\RS2\\RS2.exe"