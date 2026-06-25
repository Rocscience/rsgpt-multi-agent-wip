"""Configuration service for loading and managing YAML configurations"""

import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional, Union

import yaml

logger = logging.getLogger(__name__)


class ConfigService:
    """Service for loading and accessing YAML configuration"""

    def __init__(self, config_path: Optional[Union[str, Path]] = None):
        """
        Initialize config service with YAML file path.

        Args:
            config_path: Path to YAML config file. Defaults to config.yml in project root.
        """
        if config_path is None:
            # Default to config.yml in project root
            # Path: app/services/config/config_service.py -> need 4 parents to get to root
            project_root = Path(__file__).parent.parent.parent.parent
            self.config_path = project_root / "config.yml"
        else:
            self.config_path = Path(config_path)

        self._config_data: Dict[str, Any] = {}
        self._load_config()

    def _load_config(self):
        """Load configuration from YAML file"""
        try:
            if not self.config_path.exists():
                logger.warning(f"Config file not found: {self.config_path}")
                self._config_data = {}
                return

            with open(self.config_path, "r", encoding="utf-8") as file:
                self._config_data = yaml.safe_load(file) or {}
                logger.info(f"Loaded configuration from: {self.config_path}")

        except yaml.YAMLError as e:
            logger.error(f"Error parsing YAML config: {e}")
            self._config_data = {}
        except Exception as e:
            logger.error(f"Error loading config file: {e}")
            self._config_data = {}

    def get_context_store_config(self, channel: str) -> Dict[str, Any]:
        """
        Get context store configuration for a specific channel.

        Args:
            channel: Channel name (e.g., 'documentation', 'tech_support')

        Returns:
            Dictionary with channel configuration
        """
        context_stores = (
            self._config_data.get("context_stores", {}) if self._config_data else {}
        )
        channel_config = (
            context_stores.get(channel, {}) if isinstance(context_stores, dict) else {}
        )

        if not channel_config:
            logger.warning(f"No configuration found for channel: {channel}")
            return self._get_default_config()

        # Merge with defaults
        defaults = self._config_data.get("defaults", {})
        merged_config = {**defaults, **channel_config}

        logger.debug(f"Config for channel {channel}: {merged_config}")
        return merged_config

    def get_all_context_store_configs(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all context store configurations.

        Returns:
            Dictionary mapping channel names to their configurations
        """
        context_stores = self._config_data.get("context_stores", {})
        defaults = self._config_data.get("defaults", {})

        # Merge each channel config with defaults
        merged_configs = {}
        for channel, config in context_stores.items():
            merged_configs[channel] = {**defaults, **config}

        return merged_configs

    def get_channel_namespace(self, channel: str) -> str:
        """
        Get Pinecone namespace for a specific channel.

        Args:
            channel: Channel name

        Returns:
            Namespace string for the channel
        """
        config = self.get_context_store_config(channel)
        return config.get("namespace", channel)

    def get_channel_index_name(self, channel: str) -> str:
        """
        Get Pinecone index name for a specific channel.

        Args:
            channel: Channel name

        Returns:
            Index name for the channel
        """
        config = self.get_context_store_config(channel)
        # Fall back to environment variable if not in config
        return config.get(
            "index_name", os.getenv("PINECONE_INDEX_NAME", "rsgpt-ai-core")
        )

    def get_channel_top_k(self, channel: str) -> int:
        """
        Get top_k value for a specific channel.

        Args:
            channel: Channel name

        Returns:
            Top k value for the channel
        """
        config = self.get_context_store_config(channel)
        return config.get("top_k", 20)

    def is_channel_encrypted(self, channel: str) -> bool:
        """
        Check if a channel uses encrypted text data.

        Args:
            channel: Channel name

        Returns:
            True if channel data is encrypted, False otherwise
        """
        config = self.get_context_store_config(channel)
        return config.get("encrypted", False)

    def get_default_config(self) -> Dict[str, Any]:
        """Get default configuration values"""
        return self._config_data.get(
            "defaults",
            {
                "top_k": 20,
                "embedding_model": "text-embedding-3-large",
                "similarity_threshold": 0.7,
            },
        )

    def _get_default_config(self) -> Dict[str, Any]:
        """Get minimal default config for missing channels"""
        return {
            "type": "PineconeContextStore",
            "namespace": "default",
            "index_name": os.getenv("PINECONE_INDEX_NAME", "rsgpt-ai-core"),
            "top_k": 20,
        }

    def reload_config(self):
        """Reload configuration from file"""
        self._load_config()
        logger.info("Configuration reloaded")

    def get_available_channels(self) -> list[str]:
        """Get list of all configured channels"""
        return list(self._config_data.get("context_stores", {}).keys())


# Global instance
_config_service = None


def get_config_service() -> ConfigService:
    """Get the global config service instance"""
    global _config_service
    if _config_service is None:
        _config_service = ConfigService()
    return _config_service
