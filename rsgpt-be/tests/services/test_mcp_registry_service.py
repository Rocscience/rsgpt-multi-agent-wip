"""Tests for MCP Registry service layer"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from uuid import uuid4
from datetime import datetime

from app.services.mcp_registry_service import MCPRegistryService
from app.models.mcp_registry import (
    MCPRegistryListRequest,
    MCPRegistryListResponse,
    MCPRegistrySummary,
    MCPRegistryDetailResponse,
    MCPVersionInfo,
    MCPDownloadResponse,
    MCPInstallLogRequest,
    MCPInstallLogResponse,
    MCPRegistryCreate,
    MCPRegistryUpdate,
    MCPRegistryRegisterRequest,
    MCPRegistryRegisterResponse
)
from app.db_models.mcp_registry import MCPRegistryORM, MCPVersionsORM
from app.db_models.mcp_install_logs import MCPInstallLogsORM


@pytest.fixture
def mcp_service():
    """Fixture for MCP Registry service"""
    return MCPRegistryService()


@pytest.fixture
def mock_mcp_orm():
    """Fixture for mock MCP Registry ORM object"""
    mcp = Mock(spec=MCPRegistryORM)
    mcp.id = uuid4()
    mcp.name = "test-mcp"
    mcp.display_name = "Test MCP"
    mcp.description = "Test description"
    mcp.category = "dev-tools"
    mcp.author = "Test Author"
    mcp.repo_url = "https://github.com/test/test"
    mcp.latest_version = "1.0.0"
    mcp.s3_bucket = "rsinsight-mcp-releases-staging"
    mcp.s3_key = "test-mcp/v1.0.0/test-mcp-v1.0.0.exe"
    mcp.checksum_sha256 = "abc123"
    mcp.min_app_version = "0.1.0"
    mcp.release_date = datetime.utcnow()
    mcp.downloads_count = 100
    mcp.is_official = True
    mcp.is_active = True
    mcp.extra_metadata = {"key": "value"}
    mcp.file_size = 2048000  # 2MB
    mcp.created_at = datetime.utcnow()
    mcp.updated_at = datetime.utcnow()
    mcp.s3_bucket = "rsinsight-mcp-releases-test"
    mcp.s3_key = "test-mcp/v1.0.0/test-mcp-v1.0.0.exe"
    # Rocscience version compatibility fields
    mcp.rocscience_app = None
    mcp.required_app_version = None
    mcp.rocscience_app_path = None
    return mcp


@pytest.fixture
def mock_mcp_orm_with_version_compat():
    """Fixture for mock MCP Registry ORM object with version compatibility fields"""
    mcp = Mock(spec=MCPRegistryORM)
    mcp.id = uuid4()
    mcp.name = "rs2-server"
    mcp.display_name = "RS2 MCP Server"
    mcp.description = "MCP server for RS2"
    mcp.category = "automation"
    mcp.author = "RSInsight"
    mcp.repo_url = "https://github.com/rsinsight/rs2-mcp"
    mcp.latest_version = "1.0.0"
    mcp.s3_bucket = "rsinsight-mcp-releases-staging"
    mcp.s3_key = "rs2-server/v1.0.0/rs2-server-v1.0.0.exe"
    mcp.checksum_sha256 = "abc123"
    mcp.min_app_version = "0.1.0"
    mcp.release_date = datetime.utcnow()
    mcp.downloads_count = 50
    mcp.is_official = True
    mcp.is_active = True
    mcp.extra_metadata = {"key": "value"}
    mcp.file_size = 2048000
    mcp.created_at = datetime.utcnow()
    mcp.updated_at = datetime.utcnow()
    # Rocscience version compatibility fields
    mcp.rocscience_app = "RS2"
    mcp.required_app_version = "11.0.2.7"
    mcp.rocscience_app_path = "C:\\Program Files\\Rocscience\\RS2\\RS2.exe"
    return mcp


@pytest.fixture
def mock_version_orm():
    """Fixture for mock MCP Version ORM object"""
    version = Mock(spec=MCPVersionsORM)
    version.version = "1.0.0"
    version.release_date = datetime.utcnow()
    version.release_notes = "Initial release"
    version.checksum_sha256 = "xyz789"
    version.s3_bucket = "rsinsight-mcp-releases-test"
    version.s3_key = "test-mcp/v1.0.0/test-mcp-v1.0.0.exe"
    version.file_size = 1024000
    return version


class TestMCPRegistryService:
    """Test class for MCP Registry service"""

    @patch('app.services.mcp_registry_service.mcp_db.get_mcp_registry_list')
    def test_get_mcp_list(self, mock_get_list, mcp_service, mock_mcp_orm):
        """Test getting MCP list"""
        # Setup mock
        mock_get_list.return_value = ([mock_mcp_orm], 1)

        # Create request
        request = MCPRegistryListRequest(
            page=1,
            limit=20,
            category="dev-tools"
        )

        # Call service
        response = mcp_service.get_mcp_list(request)

        # Assertions
        assert isinstance(response, MCPRegistryListResponse)
        assert len(response.mcps) == 1
        assert response.total == 1
        assert response.page == 1
        assert response.pages == 1

        # Verify mock called with correct params
        mock_get_list.assert_called_once_with(
            page=1,
            limit=20,
            category="dev-tools",
            search=None,
            official_only=False,
            active_only=True
        )

    @patch('app.services.mcp_registry_service.mcp_db.get_mcp_registry_list')
    def test_get_mcp_list_pagination(self, mock_get_list, mcp_service, mock_mcp_orm):
        """Test MCP list pagination calculation"""
        # Setup mock for multiple pages
        mock_get_list.return_value = ([mock_mcp_orm] * 10, 55)

        request = MCPRegistryListRequest(page=2, limit=10)
        response = mcp_service.get_mcp_list(request)

        assert response.total == 55
        assert response.pages == 6  # ceil(55/10)
        assert response.page == 2

    @patch('app.services.mcp_registry_service.mcp_db.get_mcp_versions')
    @patch('app.services.mcp_registry_service.mcp_db.get_mcp_registry_by_id')
    def test_get_mcp_details(self, mock_get_by_id, mock_get_versions,
                             mcp_service, mock_mcp_orm, mock_version_orm):
        """Test getting MCP details"""
        # Setup mocks
        mock_get_by_id.return_value = mock_mcp_orm
        mock_get_versions.return_value = [mock_version_orm]

        # Call service
        response = mcp_service.get_mcp_details(mock_mcp_orm.id)

        # Assertions
        assert isinstance(response, MCPRegistryDetailResponse)
        assert response.id == mock_mcp_orm.id
        assert response.name == "test-mcp"
        assert len(response.versions) == 1
        assert response.metadata == {"key": "value"}

    @patch('app.services.mcp_registry_service.mcp_db.get_mcp_registry_by_id')
    def test_get_mcp_details_not_found(self, mock_get_by_id, mcp_service):
        """Test getting details for non-existent MCP"""
        mock_get_by_id.return_value = None

        response = mcp_service.get_mcp_details(uuid4())
        assert response is None

    @patch('app.services.mcp_registry_service.get_s3_service')
    @patch('app.services.mcp_registry_service.mcp_db.get_mcp_registry_by_id')
    def test_get_mcp_download_info_latest(self, mock_get_by_id, mock_get_s3,
                                          mcp_service, mock_mcp_orm):
        """Test getting download info for latest version"""
        mock_get_by_id.return_value = mock_mcp_orm

        # Mock S3 service to return presigned URL
        mock_s3 = Mock()
        mock_s3.generate_presigned_url.return_value = (
            "https://s3.amazonaws.com/presigned-url",
            datetime.utcnow()
        )
        mock_get_s3.return_value = mock_s3

        response = mcp_service.get_mcp_download_info(mock_mcp_orm.id)

        assert isinstance(response, MCPDownloadResponse)
        assert response.download_url == "https://s3.amazonaws.com/presigned-url"
        assert response.checksum_sha256 == mock_mcp_orm.checksum_sha256
        assert "test-mcp-v1.0.0.exe" in response.filename

    @patch('app.services.mcp_registry_service.get_s3_service')
    @patch('app.services.mcp_registry_service.mcp_db.get_mcp_version')
    @patch('app.services.mcp_registry_service.mcp_db.get_mcp_registry_by_id')
    def test_get_mcp_download_info_specific_version(self, mock_get_by_id, mock_get_version, mock_get_s3,
                                                    mcp_service, mock_mcp_orm, mock_version_orm):
        """Test getting download info for specific version"""
        mock_version_orm.version = "2.0.0"
        mock_get_by_id.return_value = mock_mcp_orm
        mock_get_version.return_value = mock_version_orm

        # Mock S3 service
        mock_s3 = Mock()
        mock_s3.generate_presigned_url.return_value = (
            "https://s3.amazonaws.com/presigned-url-v2",
            datetime.utcnow()
        )
        mock_get_s3.return_value = mock_s3

        response = mcp_service.get_mcp_download_info(mock_mcp_orm.id, "2.0.0")

        assert response.download_url == "https://s3.amazonaws.com/presigned-url-v2"
        assert response.checksum_sha256 == mock_version_orm.checksum_sha256
        assert "test-mcp-v2.0.0.exe" in response.filename

    @patch('app.services.mcp_registry_service.mcp_db.get_mcp_version')
    @patch('app.services.mcp_registry_service.mcp_db.get_mcp_registry_by_id')
    def test_get_mcp_download_info_version_not_found(self, mock_get_by_id, mock_get_version,
                                                     mcp_service, mock_mcp_orm):
        """Test download info for non-existent version"""
        mock_get_by_id.return_value = mock_mcp_orm
        mock_get_version.return_value = None

        response = mcp_service.get_mcp_download_info(mock_mcp_orm.id, "99.0.0")
        assert response is None

    @patch('app.services.mcp_registry_service.mcp_db.create_install_log')
    @patch('app.services.mcp_registry_service.mcp_db.get_mcp_registry_by_id')
    def test_log_mcp_installation(self, mock_get_by_id, mock_create_log,
                                  mcp_service, mock_mcp_orm):
        """Test logging MCP installation"""
        # Setup mocks
        mock_get_by_id.return_value = mock_mcp_orm

        mock_log = Mock(spec=MCPInstallLogsORM)
        mock_log.id = uuid4()
        mock_log.mcp_id = mock_mcp_orm.id
        mock_log.device_id = uuid4()
        mock_log.version = "1.0.0"
        mock_log.action = "install"
        mock_log.installed_at = datetime.utcnow()
        mock_create_log.return_value = mock_log

        # Create request
        install_request = MCPInstallLogRequest(
            mcp_id=mock_mcp_orm.id,
            device_id=mock_log.device_id,
            version="1.0.0",
            action="install"
        )

        # Call service
        response = mcp_service.log_mcp_installation(install_request)

        # Assertions
        assert isinstance(response, MCPInstallLogResponse)
        assert response.mcp_id == mock_mcp_orm.id
        assert "Successfully installed Test MCP" in response.message

    @patch('app.services.mcp_registry_service.mcp_db.get_mcp_registry_by_id')
    def test_log_mcp_installation_mcp_not_found(self, mock_get_by_id, mcp_service):
        """Test logging installation for non-existent MCP"""
        mock_get_by_id.return_value = None

        install_request = MCPInstallLogRequest(
            mcp_id=uuid4(),
            device_id=uuid4(),
            version="1.0.0",
            action="install"
        )

        with pytest.raises(ValueError, match="MCP not found"):
            mcp_service.log_mcp_installation(install_request)

    @patch('app.services.mcp_registry_service.mcp_db.create_mcp_version')
    @patch('app.services.mcp_registry_service.mcp_db.create_mcp_registry')
    @patch('app.services.mcp_registry_service.mcp_db.get_mcp_registry_by_name')
    def test_create_mcp_registry(self, mock_get_by_name, mock_create, mock_create_version,
                                 mcp_service, mock_mcp_orm):
        """Test creating new MCP registry entry"""
        # Setup mocks
        mock_get_by_name.return_value = None  # No existing MCP
        mock_create.return_value = mock_mcp_orm

        # Create data
        mcp_data = MCPRegistryCreate(
            name="new-mcp",
            display_name="New MCP",
            description="New MCP description",
            category="dev-tools",
            author="Author",
            repo_url="https://github.com/test/new",
            latest_version="1.0.0",
            s3_bucket="rsinsight-mcp-releases-staging",
            s3_key="new-mcp/v1.0.0/new-mcp-v1.0.0.exe",
            is_official=False,
            is_active=True
        )

        # Mock get_mcp_details to return a response
        with patch.object(mcp_service, 'get_mcp_details') as mock_get_details:
            mock_response = MCPRegistryDetailResponse(
                id=mock_mcp_orm.id,
                name=mock_mcp_orm.name,
                display_name=mock_mcp_orm.display_name,
                description=mock_mcp_orm.description,
                category=mock_mcp_orm.category,
                author=mock_mcp_orm.author,
                repo_url=mock_mcp_orm.repo_url,
                latest_version=mock_mcp_orm.latest_version,
                checksum_sha256=mock_mcp_orm.checksum_sha256,
                min_app_version=mock_mcp_orm.min_app_version,
                release_date=mock_mcp_orm.release_date,
                downloads_count=mock_mcp_orm.downloads_count,
                is_official=mock_mcp_orm.is_official,
                is_active=mock_mcp_orm.is_active,
                metadata={},
                versions=[],
                created_at=mock_mcp_orm.created_at,
                updated_at=mock_mcp_orm.updated_at
            )
            mock_get_details.return_value = mock_response

            # Call service
            response = mcp_service.create_mcp_registry(mcp_data)

            # Assertions
            assert response is not None
            mock_create.assert_called_once()
            mock_create_version.assert_called_once()

    @patch('app.services.mcp_registry_service.mcp_db.get_mcp_registry_by_name')
    def test_create_mcp_registry_duplicate_name(self, mock_get_by_name, mcp_service):
        """Test creating MCP with duplicate name"""
        mock_get_by_name.return_value = Mock()  # Existing MCP

        mcp_data = MCPRegistryCreate(
            name="existing-mcp",
            display_name="Existing MCP",
            description="Description",
            category="dev-tools",
            author="Author",
            repo_url="https://github.com/test/existing",
            latest_version="1.0.0",
            s3_bucket="rsinsight-mcp-releases-staging",
            s3_key="existing-mcp/v1.0.0/existing-mcp-v1.0.0.exe",
            is_official=False,
            is_active=True
        )

        with pytest.raises(ValueError, match="already exists"):
            mcp_service.create_mcp_registry(mcp_data)

    @patch('app.services.mcp_registry_service.mcp_db.update_mcp_registry')
    @patch('app.services.mcp_registry_service.mcp_db.create_mcp_version')
    @patch('app.services.mcp_registry_service.mcp_db.get_mcp_registry_by_id')
    def test_update_mcp_registry_with_new_version(self, mock_get_by_id, mock_create_version,
                                                  mock_update, mcp_service, mock_mcp_orm):
        """Test updating MCP with new version"""
        mock_get_by_id.return_value = mock_mcp_orm
        mock_update.return_value = mock_mcp_orm

        update_data = MCPRegistryUpdate(
            latest_version="2.0.0",
            s3_key="test-mcp/v2.0.0/test-mcp-v2.0.0.exe",
            checksum_sha256="new123"
        )

        with patch.object(mcp_service, 'get_mcp_details') as mock_get_details:
            mock_get_details.return_value = Mock()

            response = mcp_service.update_mcp_registry(mock_mcp_orm.id, update_data)

            # Verify new version was created
            mock_create_version.assert_called_once()
            mock_update.assert_called_once()

    @patch('app.services.mcp_registry_service.mcp_db.get_mcp_categories')
    def test_get_mcp_categories(self, mock_get_categories, mcp_service):
        """Test getting MCP categories"""
        mock_get_categories.return_value = ["dev-tools", "data-analysis", "automation"]

        categories = mcp_service.get_mcp_categories()

        assert len(categories) == 3
        assert "dev-tools" in categories

    @patch('app.services.mcp_registry_service.mcp_db.get_device_install_logs')
    def test_get_device_installations(self, mock_get_logs, mcp_service):
        """Test getting device installations"""
        # Create mock logs
        mock_logs = []
        mcp_id = uuid4()
        for i in range(3):
            log = Mock()
            log.mcp_id = mcp_id if i < 2 else uuid4()  # Two for same MCP
            log.version = f"{i+1}.0.0"
            log.installed_at = datetime.utcnow()
            log.action = "install" if i < 2 else "update"
            mock_logs.append(log)

        mock_get_logs.return_value = mock_logs

        device_id = uuid4()
        installations = mcp_service.get_device_installations(device_id)

        assert len(installations) >= 2  # Should have unique MCPs
        mock_get_logs.assert_called_once_with(device_id)

    @patch('app.services.mcp_registry_service.mcp_db.create_mcp_version')
    @patch('app.services.mcp_registry_service.mcp_db.create_mcp_registry')
    @patch('app.services.mcp_registry_service.mcp_db.get_mcp_registry_by_name')
    def test_register_mcp_new(self, mock_get_by_name, mock_create, mock_create_version,
                              mcp_service, mock_mcp_orm):
        """Test registering a new MCP via register endpoint"""
        # Setup mocks - MCP doesn't exist
        mock_get_by_name.return_value = None
        mock_mcp_orm.id = uuid4()
        mock_create.return_value = mock_mcp_orm

        # Create registration request
        request = MCPRegistryRegisterRequest(
            name="new-registered-mcp",
            display_name="New Registered MCP",
            description="MCP registered via API",
            category="dev-tools",
            author="Test Author",
            repo_url="https://github.com/test/new",
            version="1.0.0",
            min_app_version="0.1.0",
            s3_bucket="rsinsight-mcp-releases-staging",
            s3_key="new-registered-mcp/v1.0.0/new-registered-mcp-v1.0.0.exe",
            file_size=1024000,
            checksums={
                "windows": "win123",
                "macos": "mac456",
                "linux": "linux789"
            },
            release_notes="Initial release",
            metadata={"test": "data"},
            is_official=False
        )

        # Call service
        response = mcp_service.register_mcp(request)

        # Assertions
        assert isinstance(response, MCPRegistryRegisterResponse)
        assert response.success is True
        assert response.action == "created"
        assert response.mcp_id == mock_mcp_orm.id
        assert "registered successfully" in response.message

        # Verify DB calls
        mock_get_by_name.assert_called_once_with("new-registered-mcp")
        mock_create.assert_called_once()
        mock_create_version.assert_called_once()

    @patch('app.services.mcp_registry_service.mcp_db.create_mcp_version')
    @patch('app.services.mcp_registry_service.mcp_db.update_mcp_registry')
    @patch('app.services.mcp_registry_service.mcp_db.get_mcp_registry_by_name')
    def test_register_mcp_update_newer_version(self, mock_get_by_name, mock_update,
                                               mock_create_version, mcp_service, mock_mcp_orm):
        """Test updating existing MCP to newer version"""
        # Setup mocks - MCP exists with older version
        mock_mcp_orm.latest_version = "1.0.0"
        mock_get_by_name.return_value = mock_mcp_orm
        mock_update.return_value = mock_mcp_orm

        # Create registration request with newer version
        request = MCPRegistryRegisterRequest(
            name="test-mcp",
            display_name="Test MCP Updated",
            description="Updated MCP",
            category="dev-tools",
            author="Test Author",
            repo_url="https://github.com/test/test",
            version="2.0.0",  # Newer version
            min_app_version="0.1.0",
            s3_bucket="rsinsight-mcp-releases-staging",
            s3_key="test-mcp/v2.0.0/test-mcp-v2.0.0.exe",
            file_size=1536000,
            checksums={
                "windows": "win789",
                "macos": "mac789",
                "linux": "linux789"
            },
            release_notes="Version 2.0 release",
            is_official=False
        )

        # Call service
        response = mcp_service.register_mcp(request)

        # Assertions
        assert response.success is True
        assert response.action == "updated"
        assert response.mcp_id == mock_mcp_orm.id
        assert "updated to version 2.0.0" in response.message

        # Verify update was called
        mock_update.assert_called_once()
        mock_create_version.assert_called_once()

    @patch('app.services.mcp_registry_service.mcp_db.get_mcp_registry_by_name')
    def test_register_mcp_version_not_newer(self, mock_get_by_name, mcp_service, mock_mcp_orm):
        """Test rejecting registration with older version"""
        # Setup mocks - MCP exists with newer version
        mock_mcp_orm.latest_version = "2.0.0"
        mock_get_by_name.return_value = mock_mcp_orm

        # Create registration request with older version
        request = MCPRegistryRegisterRequest(
            name="test-mcp",
            display_name="Test MCP",
            description="Test MCP",
            category="dev-tools",
            author="Test Author",
            repo_url="https://github.com/test/test",
            version="1.5.0",  # Older than 2.0.0
            min_app_version="0.1.0",
            s3_bucket="rsinsight-mcp-releases-staging",
            s3_key="test-mcp/v1.5.0/test-mcp-v1.5.0.exe",
            file_size=1024000,
            checksums={
                "windows": "old123",
                "macos": "old456",
                "linux": "old789"
            },
            is_official=False
        )

        # Call service
        response = mcp_service.register_mcp(request)

        # Assertions
        assert response.success is False
        assert response.action is None
        assert response.error == "Version not newer"
        assert "1.5.0 is not newer than current version 2.0.0" in response.message
        assert response.details["current_version"] == "2.0.0"
        assert response.details["provided_version"] == "1.5.0"

    @patch('app.services.mcp_registry_service.mcp_db.get_mcp_registry_by_name')
    def test_register_mcp_invalid_version_format(self, mock_get_by_name, mcp_service):
        """Test rejecting registration with invalid version format"""
        # Create request with invalid version
        request = MCPRegistryRegisterRequest(
            name="test-mcp",
            display_name="Test MCP",
            description="Test MCP",
            category="dev-tools",
            author="Test Author",
            repo_url="https://github.com/test/test",
            version="invalid-version",  # Invalid format
            min_app_version="0.1.0",
            s3_bucket="rsinsight-mcp-releases-staging",
            s3_key="test-mcp/invalid/test-mcp-invalid.exe",
            file_size=1024000,
            checksums={
                "windows": "abc123"
            },
            is_official=False
        )

        # Call service
        response = mcp_service.register_mcp(request)

        # Assertions
        assert response.success is False
        assert response.error == "Invalid version format"
        assert "not a valid semantic version" in response.message

    @patch('app.services.mcp_registry_service.mcp_db.create_mcp_registry')
    @patch('app.services.mcp_registry_service.mcp_db.get_mcp_registry_by_name')
    def test_register_mcp_multi_platform_support(self, mock_get_by_name, mock_create,
                                                 mcp_service):
        """Test multi-platform download URLs and checksums storage"""
        mock_get_by_name.return_value = None

        # Mock the created MCP with proper ID
        created_mcp = Mock()
        created_mcp.id = uuid4()
        mock_create.return_value = created_mcp

        # Create request with multiple platforms
        request = MCPRegistryRegisterRequest(
            name="multi-platform-mcp",
            display_name="Multi Platform MCP",
            description="MCP with multi-platform support",
            category="dev-tools",
            author="Test Author",
            repo_url="https://github.com/test/multi",
            version="1.0.0",
            min_app_version="0.1.0",
            s3_bucket="rsinsight-mcp-releases-staging",
            s3_key="multi-platform-mcp/v1.0.0/multi-platform-mcp-v1.0.0.exe",
            file_size=2048000,
            checksums={
                "windows": "win123",
                "macos": "mac456",
                "linux": "linux789",
                "darwin-arm64": "m1abc"
            },
            is_official=False
        )

        # Mock create_mcp_version to not fail
        with patch('app.services.mcp_registry_service.mcp_db.create_mcp_version'):
            response = mcp_service.register_mcp(request)

        # Assertions
        assert response.success is True
        assert response.action == "created"

        # Verify the extra_metadata contains platform data
        create_call_args = mock_create.call_args[0][0]
        assert "checksums" in create_call_args.extra_metadata
        assert "platforms" in create_call_args.extra_metadata
        assert len(create_call_args.extra_metadata["platforms"]) == 4
        # Verify S3 fields are set correctly
        assert create_call_args.s3_bucket == "rsinsight-mcp-releases-staging"
        assert "multi-platform-mcp/v1.0.0" in create_call_args.s3_key

    # ==================== Version Compatibility Tests ====================

    @patch('app.services.mcp_registry_service.mcp_db.get_mcp_registry_list')
    def test_get_mcp_list_includes_version_compat_fields(
        self, mock_get_list, mcp_service, mock_mcp_orm_with_version_compat
    ):
        """Test that MCP list response includes version compatibility fields"""
        mock_get_list.return_value = ([mock_mcp_orm_with_version_compat], 1)

        request = MCPRegistryListRequest(page=1, limit=20)
        response = mcp_service.get_mcp_list(request)

        assert len(response.mcps) == 1
        mcp_summary = response.mcps[0]
        assert mcp_summary.rocscience_app == "RS2"
        assert mcp_summary.required_app_version == "11.0.2.7"
        assert mcp_summary.rocscience_app_path == "C:\\Program Files\\Rocscience\\RS2\\RS2.exe"

    @patch('app.services.mcp_registry_service.mcp_db.get_mcp_registry_list')
    def test_get_mcp_list_handles_null_version_compat_fields(
        self, mock_get_list, mcp_service, mock_mcp_orm
    ):
        """Test that MCP list response handles null version compatibility fields"""
        mock_get_list.return_value = ([mock_mcp_orm], 1)

        request = MCPRegistryListRequest(page=1, limit=20)
        response = mcp_service.get_mcp_list(request)

        assert len(response.mcps) == 1
        mcp_summary = response.mcps[0]
        assert mcp_summary.rocscience_app is None
        assert mcp_summary.required_app_version is None
        assert mcp_summary.rocscience_app_path is None

    @patch('app.services.mcp_registry_service.mcp_db.create_mcp_version')
    @patch('app.services.mcp_registry_service.mcp_db.create_mcp_registry')
    @patch('app.services.mcp_registry_service.mcp_db.get_mcp_registry_by_name')
    def test_register_mcp_new_with_version_compat_fields(
        self, mock_get_by_name, mock_create, mock_create_version, mcp_service
    ):
        """Test registering a new MCP with version compatibility fields"""
        mock_get_by_name.return_value = None

        created_mcp = Mock()
        created_mcp.id = uuid4()
        mock_create.return_value = created_mcp

        request = MCPRegistryRegisterRequest(
            name="rs2-server",
            display_name="RS2 MCP Server",
            description="MCP server for RS2 integration",
            category="automation",
            author="RSInsight",
            repo_url="https://github.com/rsinsight/rs2-mcp",
            version="1.0.0",
            min_app_version="0.1.0",
            s3_bucket="rsinsight-mcp-releases-staging",
            s3_key="rs2-server/v1.0.0/rs2-server-v1.0.0.exe",
            file_size=2048000,
            checksums={"windows": "abc123"},
            is_official=True,
            # Version compatibility fields
            rocscience_app="RS2",
            required_app_version="11.0.2.7",
            rocscience_app_path="C:\\Program Files\\Rocscience\\RS2\\RS2.exe"
        )

        response = mcp_service.register_mcp(request)

        assert response.success is True
        assert response.action == "created"

        # Verify version compat fields were passed to create
        create_call_args = mock_create.call_args[0][0]
        assert create_call_args.rocscience_app == "RS2"
        assert create_call_args.required_app_version == "11.0.2.7"
        assert create_call_args.rocscience_app_path == "C:\\Program Files\\Rocscience\\RS2\\RS2.exe"

    @patch('app.services.mcp_registry_service.mcp_db.create_mcp_version')
    @patch('app.services.mcp_registry_service.mcp_db.update_mcp_registry')
    @patch('app.services.mcp_registry_service.mcp_db.get_mcp_registry_by_name')
    def test_register_mcp_update_with_version_compat_fields(
        self, mock_get_by_name, mock_update, mock_create_version,
        mcp_service, mock_mcp_orm_with_version_compat
    ):
        """Test updating existing MCP with new version compatibility fields"""
        mock_mcp_orm_with_version_compat.latest_version = "1.0.0"
        mock_get_by_name.return_value = mock_mcp_orm_with_version_compat
        mock_update.return_value = mock_mcp_orm_with_version_compat

        request = MCPRegistryRegisterRequest(
            name="rs2-server",
            display_name="RS2 MCP Server",
            description="MCP server for RS2 integration",
            category="automation",
            author="RSInsight",
            repo_url="https://github.com/rsinsight/rs2-mcp",
            version="2.0.0",  # Newer version
            min_app_version="0.1.0",
            s3_bucket="rsinsight-mcp-releases-staging",
            s3_key="rs2-server/v2.0.0/rs2-server-v2.0.0.exe",
            file_size=2048000,
            checksums={"windows": "def456"},
            is_official=True,
            # Updated version compatibility - requires newer RS2
            rocscience_app="RS2",
            required_app_version="11.0.3.0",
            rocscience_app_path="C:\\Program Files\\Rocscience\\RS2\\RS2.exe"
        )

        response = mcp_service.register_mcp(request)

        assert response.success is True
        assert response.action == "updated"

        # Verify version compat fields were passed to update
        update_call_args = mock_update.call_args[0][1]
        assert update_call_args.rocscience_app == "RS2"
        assert update_call_args.required_app_version == "11.0.3.0"
        assert update_call_args.rocscience_app_path == "C:\\Program Files\\Rocscience\\RS2\\RS2.exe"

    @patch('app.services.mcp_registry_service.mcp_db.create_mcp_version')
    @patch('app.services.mcp_registry_service.mcp_db.create_mcp_registry')
    @patch('app.services.mcp_registry_service.mcp_db.get_mcp_registry_by_name')
    def test_register_mcp_without_version_compat_fields(
        self, mock_get_by_name, mock_create, mock_create_version, mcp_service
    ):
        """Test registering MCP without version compatibility fields (optional)"""
        mock_get_by_name.return_value = None

        created_mcp = Mock()
        created_mcp.id = uuid4()
        mock_create.return_value = created_mcp

        request = MCPRegistryRegisterRequest(
            name="generic-mcp",
            display_name="Generic MCP Server",
            description="Generic MCP without version requirements",
            category="dev-tools",
            author="Author",
            repo_url="https://github.com/test/generic-mcp",
            version="1.0.0",
            s3_bucket="rsinsight-mcp-releases-staging",
            s3_key="generic-mcp/v1.0.0/generic-mcp-v1.0.0.exe",
            file_size=1024000,
            checksums={"windows": "xyz789"},
            is_official=False
            # No version compatibility fields
        )

        response = mcp_service.register_mcp(request)

        assert response.success is True
        assert response.action == "created"

        # Verify version compat fields are None
        create_call_args = mock_create.call_args[0][0]
        assert create_call_args.rocscience_app is None
        assert create_call_args.required_app_version is None
        assert create_call_args.rocscience_app_path is None