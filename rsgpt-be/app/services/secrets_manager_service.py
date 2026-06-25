"""
Shared service tokens management.

This module provides:
- EnvironmentSecretsManager: Reads tokens from environment variables
- SharedTokenService: High-level API for token operations

Environment Variables:
- MCP_SERVICE_TOKEN: Unified token for all MCP servers (RS2, RSPile, etc.)

Note: DESKTOP_SERVICE_TOKEN was removed in RSI-140 - Desktop uses JWT auth instead.
Note: MCP_RSPILE_SERVICE_TOKEN was removed Single unified MCP token for all servers.
"""

import logging
import os
from typing import Dict, Protocol
from functools import lru_cache

logger = logging.getLogger(__name__)


class SecretsManagerProtocol(Protocol):
    """Protocol defining the interface for secrets managers"""

    def get_shared_tokens(self) -> Dict[str, str]:
        """Get shared service tokens"""
        ...


class EnvironmentSecretsManager:
    """
    Environment-based secrets manager.

    Reads service tokens from environment variables. These can be set via:
    - Local .env file (development)
    - Container environment variables (staging/production)
    - AWS ECS task definitions with Secrets Manager integration
    """

    def __init__(self):
        """Initialize by reading tokens from environment variables"""
        # Read unified MCP token from environment variables
        # Note: Desktop uses JWT auth, no service token needed 
        # Note: Single unified MCP token for all servers 
        mcp_service_token = os.environ.get("MCP_SERVICE_TOKEN")

        # Validate that the required token is present
        if not mcp_service_token:
            logger.warning("⚠️  Missing MCP_SERVICE_TOKEN in environment")
            logger.warning("   Add this to your .env file or configure via container environment")

        self._tokens = {
            "mcp": mcp_service_token or ""
        }

        logger.info("🔧 EnvironmentSecretsManager initialized")
        logger.info(f"   MCP Service token: {'✓ loaded' if mcp_service_token else '✗ missing'}")

    @lru_cache(maxsize=1)
    def get_shared_tokens(self) -> Dict[str, str]:
        """
        Get shared service tokens.

        Returns:
            Dict with key: mcp (unified token for all MCP servers)
        """
        logger.debug("Fetching tokens from EnvironmentSecretsManager")
        return self._tokens.copy()


class SharedTokenService:
    """
    High-level service for managing shared service tokens.

    Abstracts the underlying storage mechanism.
    """

    def __init__(self, secrets_manager: SecretsManagerProtocol):
        """
        Initialize with a secrets manager implementation.

        Args:
            secrets_manager: Implementation of SecretsManagerProtocol
        """
        self.secrets_manager = secrets_manager
        self._tokens_cache = None

    def get_shared_tokens(self) -> Dict[str, str]:
        """
        Get shared service tokens.

        Returns:
            Dict with key:
            - mcp: Unified MCP service token for all MCP servers (RS2, RSPile, etc.)
        """
        if self._tokens_cache is None:
            self._tokens_cache = self.secrets_manager.get_shared_tokens()
            logger.info("✅ Shared service tokens loaded")

        return self._tokens_cache


# Singleton instance - will be created on first use
_token_service: SharedTokenService | None = None


def get_token_service() -> SharedTokenService:
    """
    Get singleton instance of SharedTokenService.

    Returns:
        SharedTokenService instance
    """
    global _token_service

    if _token_service is None:
        logger.info("Initializing EnvironmentSecretsManager")
        secrets_manager = EnvironmentSecretsManager()
        _token_service = SharedTokenService(secrets_manager)

    return _token_service