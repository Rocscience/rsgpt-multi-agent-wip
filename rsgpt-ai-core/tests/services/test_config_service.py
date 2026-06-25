"""Unit tests for config service"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from app.services.config import ConfigService, get_config_service


class TestConfigService:
    """Test config service functionality"""

    @pytest.fixture
    def sample_config(self):
        """Load actual configuration from config.yml"""
        config_path = Path(__file__).parent.parent.parent / "config.yml"
        with open(config_path) as f:
            return yaml.safe_load(f)

    @pytest.fixture
    def temp_config_file(self, sample_config):
        """Create a temporary config file"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            yaml.dump(sample_config, f)
            temp_path = f.name
        yield temp_path
        # Cleanup
        Path(temp_path).unlink()

    def test_initialization_with_path(self, temp_config_file):
        """Test config service initialization with custom path"""
        service = ConfigService(config_path=temp_config_file)
        assert service.config_path == Path(temp_config_file)
        assert service._config_data is not None

    def test_initialization_without_path(self):
        """Test config service initialization with default path"""
        service = ConfigService()
        assert service.config_path is not None
        assert service._config_data is not None

    def test_initialization_with_missing_file(self):
        """Test initialization with non-existent config file"""
        service = ConfigService(config_path="/non/existent/path.yml")
        assert service._config_data == {}

    def test_load_config_success(self, temp_config_file, sample_config):
        """Test successful config loading"""
        service = ConfigService(config_path=temp_config_file)
        assert service._config_data == sample_config

    def test_load_config_invalid_yaml(self):
        """Test loading invalid YAML"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            f.write("invalid: yaml: content:\n  - bad syntax")
            temp_path = f.name

        try:
            service = ConfigService(config_path=temp_path)
            assert service._config_data == {}
        finally:
            Path(temp_path).unlink()

    def test_get_context_store_config(self, temp_config_file):
        """Test getting context store config for a channel"""
        service = ConfigService(config_path=temp_config_file)
        config = service.get_context_store_config("documentation")

        assert config["type"] == "PineconeContextStore"
        assert config["namespace"] == "nov2025"
        assert config["index_name"] == "rocumentation-files"
        assert config["top_k"] == 30

    def test_get_context_store_config_merges_defaults(self, temp_config_file):
        """Test that config merges with defaults"""
        service = ConfigService(config_path=temp_config_file)
        config = service.get_context_store_config("documentation")

        # Should have channel-specific values
        assert config["top_k"] == 30
        # Should also have default values
        assert config["embedding_model"] == "text-embedding-3-large"
        assert config["similarity_threshold"] == 0.7

    def test_get_context_store_config_channel_overrides_defaults(
        self, temp_config_file
    ):
        """Test that channel config overrides defaults"""
        service = ConfigService(config_path=temp_config_file)
        config = service.get_context_store_config("documentation")

        # Channel has top_k=30, default is top_k=20
        # Channel value should win
        assert config["top_k"] == 30

    def test_get_context_store_config_missing_channel(self, temp_config_file):
        """Test getting config for non-existent channel"""
        service = ConfigService(config_path=temp_config_file)
        config = service.get_context_store_config("non_existent_channel")

        # Should return default config
        assert config["type"] == "PineconeContextStore"
        assert config["namespace"] == "default"
        assert config["top_k"] == 20

    def test_get_all_context_store_configs(self, temp_config_file):
        """Test getting all context store configs"""
        service = ConfigService(config_path=temp_config_file)
        all_configs = service.get_all_context_store_configs()

        assert "documentation" in all_configs
        assert "tech_support" in all_configs
        assert "diana" in all_configs
        assert "three_gsm" in all_configs
        assert "two_si" in all_configs
        assert "rockfield" in all_configs
        assert "aquanty" in all_configs
        assert len(all_configs) == 7

    def test_get_all_context_store_configs_includes_defaults(self, temp_config_file):
        """Test that all configs include default values"""
        service = ConfigService(config_path=temp_config_file)
        all_configs = service.get_all_context_store_configs()

        for channel, config in all_configs.items():
            assert "embedding_model" in config
            assert "similarity_threshold" in config

    def test_get_channel_namespace(self, temp_config_file):
        """Test getting channel namespace"""
        service = ConfigService(config_path=temp_config_file)
        namespace = service.get_channel_namespace("documentation")
        assert namespace == "nov2025"

    def test_get_channel_namespace_fallback(self, temp_config_file):
        """Test namespace fallback for missing channel"""
        service = ConfigService(config_path=temp_config_file)
        namespace = service.get_channel_namespace("missing_channel")
        # Should fallback to default namespace from _get_default_config
        assert namespace == "default"

    def test_get_channel_index_name(self, temp_config_file):
        """Test getting channel index name"""
        service = ConfigService(config_path=temp_config_file)
        index_name = service.get_channel_index_name("documentation")
        assert index_name == "rocumentation-files"

    def test_get_channel_index_name_fallback_to_env(self, temp_config_file):
        """Test index name fallback to environment variable"""
        with patch.dict("os.environ", {"PINECONE_INDEX_NAME": "test-index"}):
            service = ConfigService(config_path=temp_config_file)
            index_name = service.get_channel_index_name("missing_channel")
            assert index_name == "test-index"

    def test_get_channel_index_name_fallback_default(self, temp_config_file):
        """Test index name fallback to default"""
        with patch.dict("os.environ", {}, clear=True):
            service = ConfigService(config_path=temp_config_file)
            index_name = service.get_channel_index_name("missing_channel")
            assert index_name == "rsgpt-ai-core"

    def test_get_channel_top_k(self, temp_config_file):
        """Test getting channel top_k"""
        service = ConfigService(config_path=temp_config_file)
        top_k = service.get_channel_top_k("documentation")
        assert top_k == 30

    def test_get_channel_top_k_fallback(self, temp_config_file):
        """Test top_k fallback for missing channel"""
        service = ConfigService(config_path=temp_config_file)
        top_k = service.get_channel_top_k("missing_channel")
        assert top_k == 20

    def test_is_channel_encrypted_true(self, temp_config_file):
        """Test is_channel_encrypted returns True for encrypted channel"""
        service = ConfigService(config_path=temp_config_file)
        is_encrypted = service.is_channel_encrypted("tech_support")
        assert is_encrypted is True

    def test_is_channel_encrypted_false(self, temp_config_file):
        """Test is_channel_encrypted returns False for non-encrypted channel"""
        service = ConfigService(config_path=temp_config_file)
        is_encrypted = service.is_channel_encrypted("documentation")
        assert is_encrypted is False

    def test_is_channel_encrypted_missing_channel(self, temp_config_file):
        """Test is_channel_encrypted returns False for missing channel"""
        service = ConfigService(config_path=temp_config_file)
        is_encrypted = service.is_channel_encrypted("non_existent_channel")
        assert is_encrypted is False

    def test_get_default_config(self, temp_config_file):
        """Test getting default configuration"""
        service = ConfigService(config_path=temp_config_file)
        defaults = service.get_default_config()

        assert defaults["top_k"] == 20
        assert defaults["embedding_model"] == "text-embedding-3-large"
        assert defaults["similarity_threshold"] == 0.7

    def test_get_default_config_no_file(self):
        """Test getting defaults when no config file exists"""
        service = ConfigService(config_path="/non/existent/path.yml")
        defaults = service.get_default_config()

        # Should return hardcoded defaults
        assert "top_k" in defaults
        assert "embedding_model" in defaults
        assert "similarity_threshold" in defaults

    def test_get_available_channels(self, temp_config_file):
        """Test getting list of available channels"""
        service = ConfigService(config_path=temp_config_file)
        channels = service.get_available_channels()

        assert "documentation" in channels
        assert "tech_support" in channels
        assert "diana" in channels
        assert "three_gsm" in channels
        assert "two_si" in channels
        assert "rockfield" in channels
        assert "aquanty" in channels
        assert len(channels) == 7

    def test_get_available_channels_empty_config(self):
        """Test getting channels from empty config"""
        service = ConfigService(config_path="/non/existent/path.yml")
        channels = service.get_available_channels()
        assert channels == []

    def test_reload_config(self, temp_config_file, sample_config):
        """Test reloading configuration"""
        service = ConfigService(config_path=temp_config_file)
        original_config = service._config_data.copy()

        # Modify the file
        modified_config = sample_config.copy()
        modified_config["context_stores"]["new_channel"] = {
            "type": "PineconeContextStore",
            "namespace": "NewChannel",
            "top_k": 25,
        }

        with open(temp_config_file, "w") as f:
            yaml.dump(modified_config, f)

        # Reload
        service.reload_config()

        # Should have new channel
        assert "new_channel" in service._config_data["context_stores"]
        assert service._config_data != original_config

    @patch("app.services.config.config_service.logger")
    def test_load_config_logs_success(self, mock_logger, temp_config_file):
        """Test that successful load logs info message"""
        service = ConfigService(config_path=temp_config_file)
        mock_logger.info.assert_called()

    @patch("app.services.config.config_service.logger")
    def test_load_config_logs_warning_missing_file(self, mock_logger):
        """Test that missing file logs warning"""
        service = ConfigService(config_path="/non/existent/path.yml")
        mock_logger.warning.assert_called()

    @patch("app.services.config.config_service.logger")
    def test_get_context_store_config_logs_warning_missing_channel(
        self, mock_logger, temp_config_file
    ):
        """Test that missing channel logs warning"""
        service = ConfigService(config_path=temp_config_file)
        service.get_context_store_config("non_existent")
        mock_logger.warning.assert_called()

    @patch("app.services.config.config_service.logger")
    def test_reload_logs_info(self, mock_logger, temp_config_file):
        """Test that reload logs info message"""
        service = ConfigService(config_path=temp_config_file)
        mock_logger.info.reset_mock()
        service.reload_config()
        mock_logger.info.assert_called()


class TestGetConfigService:
    """Test config service singleton getter"""

    def test_get_config_service_returns_instance(self):
        """Test that get_config_service returns a ConfigService instance"""
        service = get_config_service()
        assert isinstance(service, ConfigService)

    def test_get_config_service_returns_same_instance(self):
        """Test that get_config_service returns the same instance"""
        service1 = get_config_service()
        service2 = get_config_service()
        assert service1 is service2

    @patch("app.services.config.config_service._config_service", None)
    def test_get_config_service_creates_instance_if_none(self):
        """Test that get_config_service creates instance if none exists"""
        service = get_config_service()
        assert service is not None
        assert isinstance(service, ConfigService)
