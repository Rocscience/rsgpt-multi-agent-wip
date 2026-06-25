"""Auth0 Machine-to-Machine (M2M) Token Service

This service handles fetching and caching M2M access tokens for service-to-service
communication between rsgpt-be and rsgpt-ai-core using Auth0 Client Credentials Grant.
"""

import asyncio
import logging
import time
from typing import Optional
import httpx
from app.config import settings

logger = logging.getLogger(__name__)


class Auth0M2MTokenService:
    """Service for managing Auth0 M2M access tokens with caching and auto-refresh"""

    def __init__(self):
        self._token: Optional[str] = None
        self._token_expiry: float = 0
        self._buffer_seconds = 300  # Refresh 5 minutes before expiry
        self._fetch_lock = asyncio.Lock()  # Prevent concurrent fetches

    async def get_token(self) -> str:
        """
        Get a valid M2M access token, fetching a new one if needed.

        Uses in-memory caching with automatic refresh before expiry.
        Thread-safe for async usage with lock to prevent concurrent fetches.

        Returns:
            str: Valid JWT access token for ai-core API

        Raises:
            ConnectionError: If token fetch fails or Auth0 is unreachable
            ValueError: If Auth0 credentials are not configured
        """
        # Fast path: check cache without lock
        if self._token and time.time() < (self._token_expiry - self._buffer_seconds):
            logger.debug("Using cached M2M token")
            return self._token

        # Slow path: acquire lock before fetching
        async with self._fetch_lock:
            # Double-check after acquiring lock (another coroutine may have fetched)
            if self._token and time.time() < (self._token_expiry - self._buffer_seconds):
                logger.debug("Token refreshed by concurrent request, using cached")
                return self._token

            # Fetch new token
            logger.info("Fetching new M2M token from Auth0")
            return await self._fetch_token()

    async def _fetch_token(self) -> str:
        """
        Fetch a new M2M token from Auth0 using Client Credentials Grant.

        Returns:
            str: New JWT access token

        Raises:
            ValueError: If required Auth0 configuration is missing
            ConnectionError: If Auth0 request fails
        """
        # Validate configuration
        if not settings.auth0_domain:
            raise ValueError("AUTH0_DOMAIN not configured")
        if not settings.auth0_client_id:
            raise ValueError("AUTH0_CLIENT_ID not configured (M2M app client ID)")
        if not settings.auth0_client_secret:
            raise ValueError("AUTH0_CLIENT_SECRET not configured (M2M app client secret)")
        if not settings.auth0_ai_core_audience:
            raise ValueError("AUTH0_AI_CORE_AUDIENCE not configured")

        # Prepare request to Auth0 token endpoint
        url = f"https://{settings.auth0_domain}/oauth/token"
        payload = {
            "client_id": settings.auth0_client_id,
            "client_secret": settings.auth0_client_secret,
            "audience": settings.auth0_ai_core_audience,
            "grant_type": "client_credentials"
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()

                data = response.json()

                # Extract token and expiry
                self._token = data["access_token"]
                expires_in = data.get("expires_in", 86400)  # Default 24 hours
                self._token_expiry = time.time() + expires_in

                logger.info(
                    f"✓ M2M token fetched successfully (expires in {expires_in}s, "
                    f"will refresh in {expires_in - self._buffer_seconds}s)"
                )

                return self._token

        except httpx.HTTPStatusError as e:
            error_detail = e.response.text
            logger.error(
                f"Auth0 token request failed: {e.response.status_code} - {error_detail}"
            )
            raise ConnectionError(
                f"Failed to fetch M2M token from Auth0: {e.response.status_code}"
            )
        except httpx.RequestError as e:
            logger.error(f"Network error connecting to Auth0: {e}")
            raise ConnectionError(f"Auth0 unreachable: {e}")
        except Exception as e:
            logger.error(f"Unexpected error fetching M2M token: {e}", exc_info=True)
            raise ConnectionError(f"M2M token fetch error: {e}")

    def clear_token(self):
        """Clear cached token (useful for testing or forced refresh)"""
        logger.info("Clearing cached M2M token")
        self._token = None
        self._token_expiry = 0


# Singleton instance
m2m_token_service = Auth0M2MTokenService()
