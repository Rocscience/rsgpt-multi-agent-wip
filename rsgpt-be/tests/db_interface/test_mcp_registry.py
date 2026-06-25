"""Tests for MCP Registry database interface"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from uuid import uuid4
from datetime import datetime

from app.db_interface import mcp_registry as mcp_db
from app.db_models.mcp_registry import MCPRegistryORM, MCPVersionsORM
from app.db_models.mcp_install_logs import MCPInstallLogsORM
from app.models.mcp_registry import (
    MCPRegistryCreate,
    MCPRegistryUpdate,
    MCPInstallLogRequest
)


@pytest.fixture
def sample_mcp_data():
    """Fixture for sample MCP registry data"""
    return MCPRegistryCreate(
        name="test-mcp-server",
        display_name="Test MCP Server",
        description="A test MCP server for unit testing",
        category="dev-tools",
        author="Test Author",
        repo_url="https://github.com/test/test-mcp",
        latest_version="1.0.0",
        min_app_version="0.1.0",
        s3_bucket="rsinsight-mcp-releases-staging",
        s3_key="test-mcp-server/v1.0.0/test-mcp-server-v1.0.0.exe",
        checksum_sha256="abcdef1234567890",
        release_date=datetime.utcnow(),
        is_official=False,
        is_active=True,
        extra_metadata={"test": "data"}
    )


@pytest.fixture
def sample_mcp_data_with_version_compat():
    """Fixture for sample MCP registry data with version compatibility fields"""
    return MCPRegistryCreate(
        name="rs2-server",
        display_name="RS2 MCP Server",
        description="MCP server for RS2 integration",
        category="automation",
        author="RSInsight",
        repo_url="https://github.com/rsinsight/rs2-mcp",
        latest_version="1.0.0",
        min_app_version="0.1.0",
        s3_bucket="rsinsight-mcp-releases-staging",
        s3_key="rs2-server/v1.0.0/rs2-server-v1.0.0.exe",
        checksum_sha256="abcdef1234567890",
        release_date=datetime.utcnow(),
        is_official=True,
        is_active=True,
        extra_metadata={"test": "data"},
        # Version compatibility fields
        rocscience_app="RS2",
        required_app_version="11.0.2.7",
        rocscience_app_path="C:\\Program Files\\Rocscience\\RS2\\RS2.exe"
    )


@pytest.fixture
def sample_mcp_orm():
    """Fixture for sample MCP ORM object"""
    return MCPRegistryORM(
        id=uuid4(),
        name="test-mcp-server",
        display_name="Test MCP Server",
        description="A test MCP server",
        category="dev-tools",
        author="Test Author",
        repo_url="https://github.com/test/test-mcp",
        latest_version="1.0.0",
        min_app_version="0.1.0",
        s3_bucket="rsinsight-mcp-releases-staging",
        s3_key="test-mcp-server/v1.0.0/test-mcp-server-v1.0.0.exe",
        checksum_sha256="abcdef1234567890",
        downloads_count=0,
        is_official=False,
        is_active=True,
        extra_metadata={"test": "data"}
    )


@pytest.fixture
def sample_device_id():
    """Fixture for sample device ID"""
    return uuid4()


class TestMCPRegistryDBInterface:
    """Test class for MCP Registry database operations"""

    def test_create_mcp_registry(self, sample_mcp_data):
        """Test creating an MCP registry entry"""
        with patch('app.db_interface.mcp_registry.Session') as mock_session_class:
            mock_session = mock_session_class.return_value.__enter__.return_value
            mock_session.add = Mock()
            mock_session.commit = Mock()
            mock_session.refresh = Mock()

            # Act
            result = mcp_db.create_mcp_registry(sample_mcp_data)

            # Assert
            mock_session.add.assert_called_once()
            mock_session.commit.assert_called_once()
            mock_session.refresh.assert_called_once()

            added_mcp = mock_session.add.call_args[0][0]
            assert isinstance(added_mcp, MCPRegistryORM)
            assert added_mcp.name == sample_mcp_data.name
            assert added_mcp.display_name == sample_mcp_data.display_name

    def test_get_mcp_registry_by_id(self, sample_mcp_orm):
        """Test getting MCP registry by ID"""
        with patch('app.db_interface.mcp_registry.Session') as mock_session_class:
            mock_session = mock_session_class.return_value.__enter__.return_value
            mock_query = Mock()
            mock_session.query.return_value = mock_query
            mock_query.filter.return_value = mock_query
            mock_query.first.return_value = sample_mcp_orm

            # Act
            result = mcp_db.get_mcp_registry_by_id(sample_mcp_orm.id)

            # Assert
            assert result == sample_mcp_orm
            mock_session.query.assert_called_once()

    def test_get_mcp_registry_by_name(self, sample_mcp_orm):
        """Test getting MCP registry by name"""
        with patch('app.db_interface.mcp_registry.Session') as mock_session_class:
            mock_session = mock_session_class.return_value.__enter__.return_value
            mock_query = Mock()
            mock_session.query.return_value = mock_query
            mock_query.filter.return_value = mock_query
            mock_query.first.return_value = sample_mcp_orm

            # Act
            result = mcp_db.get_mcp_registry_by_name(sample_mcp_orm.name)

            # Assert
            assert result == sample_mcp_orm

    def test_get_mcp_registry_list(self, sample_mcp_orm):
        """Test getting paginated MCP registry list"""
        with patch('app.db_interface.mcp_registry.Session') as mock_session_class:
            mock_session = mock_session_class.return_value.__enter__.return_value
            mock_query = Mock()
            mock_session.query.return_value = mock_query
            mock_query.filter.return_value = mock_query
            mock_query.order_by.return_value = mock_query
            mock_query.offset.return_value = mock_query
            mock_query.limit.return_value = mock_query
            mock_query.all.return_value = [sample_mcp_orm]
            mock_query.count.return_value = 1

            # Act
            mcps, total = mcp_db.get_mcp_registry_list(page=1, limit=10)

            # Assert
            assert len(mcps) == 1
            assert total == 1
            assert mcps[0] == sample_mcp_orm

    def test_get_mcp_registry_list_with_filters(self, sample_mcp_orm):
        """Test getting MCP list with filters"""
        with patch('app.db_interface.mcp_registry.Session') as mock_session_class:
            mock_session = mock_session_class.return_value.__enter__.return_value
            mock_query = Mock()
            mock_session.query.return_value = mock_query
            mock_query.filter.return_value = mock_query
            mock_query.order_by.return_value = mock_query
            mock_query.offset.return_value = mock_query
            mock_query.limit.return_value = mock_query
            mock_query.all.return_value = [sample_mcp_orm]
            mock_query.count.return_value = 1

            # Act
            mcps, total = mcp_db.get_mcp_registry_list(
                page=1,
                limit=10,
                category="dev-tools",
                official_only=False
            )

            # Assert
            assert len(mcps) == 1
            assert total == 1

    def test_get_mcp_registry_list_with_search(self, sample_mcp_orm):
        """Test getting MCP list with search query"""
        with patch('app.db_interface.mcp_registry.Session') as mock_session_class:
            mock_session = mock_session_class.return_value.__enter__.return_value
            mock_query = Mock()
            mock_session.query.return_value = mock_query
            mock_query.filter.return_value = mock_query
            mock_query.order_by.return_value = mock_query
            mock_query.offset.return_value = mock_query
            mock_query.limit.return_value = mock_query
            mock_query.all.return_value = [sample_mcp_orm]
            mock_query.count.return_value = 1

            # Act
            mcps, total = mcp_db.get_mcp_registry_list(
                page=1,
                limit=10,
                search="test"
            )

            # Assert
            assert len(mcps) == 1
            assert total == 1

    def test_update_mcp_registry(self, sample_mcp_orm):
        """Test updating MCP registry entry"""
        update_data = MCPRegistryUpdate(
            latest_version="1.1.0",
            s3_key="test-mcp-server/v1.1.0/test-mcp-server-v1.1.0.exe"
        )

        with patch('app.db_interface.mcp_registry.Session') as mock_session_class:
            mock_session = mock_session_class.return_value.__enter__.return_value
            mock_query = Mock()
            mock_session.query.return_value = mock_query
            mock_query.filter.return_value = mock_query
            mock_query.first.return_value = sample_mcp_orm
            mock_session.commit = Mock()
            mock_session.refresh = Mock()

            # Act
            result = mcp_db.update_mcp_registry(sample_mcp_orm.id, update_data)

            # Assert
            mock_session.commit.assert_called_once()
            mock_session.refresh.assert_called_once()

    def test_create_mcp_version(self, sample_mcp_orm):
        """Test creating MCP version entry"""
        with patch('app.db_interface.mcp_registry.Session') as mock_session_class:
            mock_session = mock_session_class.return_value.__enter__.return_value
            mock_session.add = Mock()
            mock_session.commit = Mock()
            mock_session.refresh = Mock()

            # Act
            result = mcp_db.create_mcp_version(
                mcp_id=sample_mcp_orm.id,
                version="1.1.0",
                s3_bucket="rsinsight-mcp-releases-staging",
                s3_key="test-mcp-server/v1.1.0/test-mcp-server-v1.1.0.exe",
                checksum_sha256="newchecksum",
                release_notes="Bug fixes"
            )

            # Assert
            mock_session.add.assert_called_once()
            mock_session.commit.assert_called_once()

            added_version = mock_session.add.call_args[0][0]
            assert isinstance(added_version, MCPVersionsORM)
            assert added_version.mcp_id == sample_mcp_orm.id
            assert added_version.version == "1.1.0"

    def test_get_mcp_versions(self, sample_mcp_orm):
        """Test getting all versions for an MCP"""
        mock_version = MCPVersionsORM(
            id=uuid4(),
            mcp_id=sample_mcp_orm.id,
            version="1.0.0",
            s3_bucket="rsinsight-mcp-releases-staging",
            s3_key="test-mcp-server/v1.0.0/test-mcp-server-v1.0.0.exe",
            checksum_sha256="checksum"
        )

        with patch('app.db_interface.mcp_registry.Session') as mock_session_class:
            mock_session = mock_session_class.return_value.__enter__.return_value
            mock_query = Mock()
            mock_session.query.return_value = mock_query
            mock_query.filter.return_value = mock_query
            mock_query.order_by.return_value = mock_query
            mock_query.all.return_value = [mock_version]

            # Act
            result = mcp_db.get_mcp_versions(sample_mcp_orm.id)

            # Assert
            assert len(result) == 1
            assert result[0] == mock_version

    def test_get_mcp_version(self, sample_mcp_orm):
        """Test getting a specific version"""
        mock_version = MCPVersionsORM(
            id=uuid4(),
            mcp_id=sample_mcp_orm.id,
            version="1.0.0",
            s3_bucket="rsinsight-mcp-releases-staging",
            s3_key="test-mcp-server/v1.0.0/test-mcp-server-v1.0.0.exe",
            checksum_sha256="checksum"
        )

        with patch('app.db_interface.mcp_registry.Session') as mock_session_class:
            mock_session = mock_session_class.return_value.__enter__.return_value
            mock_query = Mock()
            mock_session.query.return_value = mock_query
            mock_query.filter.return_value = mock_query
            mock_query.first.return_value = mock_version

            # Act
            result = mcp_db.get_mcp_version(sample_mcp_orm.id, "1.0.0")

            # Assert
            assert result == mock_version

    def test_create_install_log(self, sample_mcp_orm, sample_device_id):
        """Test creating install log entry"""
        install_data = MCPInstallLogRequest(
            mcp_id=sample_mcp_orm.id,
            device_id=sample_device_id,
            version="1.0.0",
            action="install"
        )

        with patch('app.db_interface.mcp_registry.Session') as mock_session_class:
            mock_session = mock_session_class.return_value.__enter__.return_value
            mock_session.add = Mock()
            mock_session.commit = Mock()
            mock_session.refresh = Mock()

            # Act
            result = mcp_db.create_install_log(install_data)

            # Assert
            mock_session.add.assert_called_once()
            mock_session.commit.assert_called_once()

            added_log = mock_session.add.call_args[0][0]
            assert isinstance(added_log, MCPInstallLogsORM)
            assert added_log.mcp_id == sample_mcp_orm.id
            assert added_log.device_id == sample_device_id

    def test_create_install_log_update_action(self, sample_mcp_orm, sample_device_id):
        """Test creating install log with update action"""
        install_data = MCPInstallLogRequest(
            mcp_id=sample_mcp_orm.id,
            device_id=sample_device_id,
            version="1.1.0",
            action="update"
        )

        with patch('app.db_interface.mcp_registry.Session') as mock_session_class:
            mock_session = mock_session_class.return_value.__enter__.return_value
            mock_session.add = Mock()
            mock_session.commit = Mock()
            mock_session.refresh = Mock()

            # Act
            result = mcp_db.create_install_log(install_data)

            # Assert
            mock_session.add.assert_called_once()
            added_log = mock_session.add.call_args[0][0]
            assert added_log.action == "update"

    def test_get_device_install_logs(self, sample_mcp_orm, sample_device_id):
        """Test getting install logs for a device"""
        # Create mock log using Mock instead of ORM instantiation
        mock_log = Mock(spec=MCPInstallLogsORM)
        mock_log.id = uuid4()
        mock_log.mcp_id = sample_mcp_orm.id
        mock_log.device_id = sample_device_id
        mock_log.version = "1.0.0"
        mock_log.action = "install"
        mock_log.installed_at = datetime.utcnow()

        with patch('app.db_interface.mcp_registry.Session') as mock_session_class:
            mock_session = mock_session_class.return_value.__enter__.return_value
            mock_query = Mock()
            mock_session.query.return_value = mock_query
            mock_query.filter.return_value = mock_query
            mock_query.order_by.return_value = mock_query
            mock_query.all.return_value = [mock_log]

            # Act
            result = mcp_db.get_device_install_logs(sample_device_id)

            # Assert
            assert len(result) == 1
            assert result[0] == mock_log

    def test_get_mcp_categories(self):
        """Test getting list of MCP categories"""
        with patch('app.db_interface.mcp_registry.Session') as mock_session_class:
            mock_session = mock_session_class.return_value.__enter__.return_value
            mock_query = Mock()
            mock_session.query.return_value = mock_query
            mock_query.filter.return_value = mock_query
            mock_query.distinct.return_value = mock_query
            mock_query.all.return_value = [("dev-tools",), ("data-analysis",)]

            # Act
            result = mcp_db.get_mcp_categories()

            # Assert
            assert len(result) == 2
            assert "dev-tools" in result
            assert "data-analysis" in result

    # ==================== Version Compatibility Tests ====================

    def test_create_mcp_registry_with_version_compat_fields(self, sample_mcp_data_with_version_compat):
        """Test creating MCP registry entry with version compatibility fields"""
        with patch('app.db_interface.mcp_registry.Session') as mock_session_class:
            mock_session = mock_session_class.return_value.__enter__.return_value
            mock_session.add = Mock()
            mock_session.commit = Mock()
            mock_session.refresh = Mock()

            # Act
            result = mcp_db.create_mcp_registry(sample_mcp_data_with_version_compat)

            # Assert
            mock_session.add.assert_called_once()
            mock_session.commit.assert_called_once()
            mock_session.refresh.assert_called_once()

            added_mcp = mock_session.add.call_args[0][0]
            assert isinstance(added_mcp, MCPRegistryORM)
            assert added_mcp.name == "rs2-server"
            assert added_mcp.rocscience_app == "RS2"
            assert added_mcp.required_app_version == "11.0.2.7"
            assert added_mcp.rocscience_app_path == "C:\\Program Files\\Rocscience\\RS2\\RS2.exe"

    def test_create_mcp_registry_without_version_compat_fields(self, sample_mcp_data):
        """Test creating MCP registry entry without version compatibility fields"""
        with patch('app.db_interface.mcp_registry.Session') as mock_session_class:
            mock_session = mock_session_class.return_value.__enter__.return_value
            mock_session.add = Mock()
            mock_session.commit = Mock()
            mock_session.refresh = Mock()

            # Act
            result = mcp_db.create_mcp_registry(sample_mcp_data)

            # Assert
            mock_session.add.assert_called_once()

            added_mcp = mock_session.add.call_args[0][0]
            assert isinstance(added_mcp, MCPRegistryORM)
            assert added_mcp.rocscience_app is None
            assert added_mcp.required_app_version is None
            assert added_mcp.rocscience_app_path is None

    def test_update_mcp_registry_with_version_compat_fields(self, sample_mcp_orm):
        """Test updating MCP registry entry with version compatibility fields"""
        update_data = MCPRegistryUpdate(
            latest_version="2.0.0",
            rocscience_app="RS2",
            required_app_version="11.0.3.0",
            rocscience_app_path="C:\\Program Files\\Rocscience\\RS2\\RS2.exe"
        )

        with patch('app.db_interface.mcp_registry.Session') as mock_session_class:
            mock_session = mock_session_class.return_value.__enter__.return_value
            mock_query = Mock()
            mock_session.query.return_value = mock_query
            mock_query.filter.return_value = mock_query
            mock_query.first.return_value = sample_mcp_orm
            mock_session.commit = Mock()
            mock_session.refresh = Mock()

            # Act
            result = mcp_db.update_mcp_registry(sample_mcp_orm.id, update_data)

            # Assert
            mock_session.commit.assert_called_once()
            mock_session.refresh.assert_called_once()

            # Verify the version compat fields were set on the ORM object
            assert sample_mcp_orm.rocscience_app == "RS2"
            assert sample_mcp_orm.required_app_version == "11.0.3.0"
            assert sample_mcp_orm.rocscience_app_path == "C:\\Program Files\\Rocscience\\RS2\\RS2.exe"
