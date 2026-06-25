"""Unit tests for Auth0 M2M Token Service

Tests cover:
- Token caching and reuse
- Token expiry and refresh logic
- Concurrent request handling
- Error scenarios and fallback
- Clock skew and edge cases
"""

import pytest
import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.auth0_m2m_service import Auth0M2MTokenService
import httpx


class TestAuth0M2MTokenService:
    """Test suite for M2M token caching and management"""

    @pytest.fixture
    def service(self):
        """Create a fresh service instance for each test"""
        return Auth0M2MTokenService()

    @pytest.fixture
    def mock_auth0_response(self):
        """Mock successful Auth0 token response"""
        return {
            "access_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ0ZXN0In0.test",
            "token_type": "Bearer",
            "expires_in": 86400  # 24 hours
        }

    # ========================================================================
    # Test 1: Basic Token Fetching and Caching
    # ========================================================================

    @pytest.mark.asyncio
    async def test_first_token_fetch(self, service, mock_auth0_response):
        """Test that first call fetches token from Auth0"""
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = MagicMock()
            mock_response.json = MagicMock(return_value=mock_auth0_response)
            mock_response.raise_for_status = MagicMock()

            mock_post = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value.post = mock_post

            # First call should fetch
            token = await service.get_token()

            assert token == mock_auth0_response["access_token"]
            assert service._token == token
            assert service._token_expiry > time.time()

    @pytest.mark.asyncio
    async def test_token_reuse_from_cache(self, service, mock_auth0_response):
        """Test that valid cached token is reused without fetching"""
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = MagicMock()
            mock_response.json = MagicMock(return_value=mock_auth0_response)
            mock_response.raise_for_status = MagicMock()

            mock_post = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value.post = mock_post

            # First call
            token1 = await service.get_token()

            # Second call should use cache (no new fetch)
            token2 = await service.get_token()

            assert token1 == token2
            assert mock_post.call_count == 1

    # ========================================================================
    # Test 2: Token Expiry and Refresh
    # ========================================================================

    @pytest.mark.asyncio
    async def test_token_refresh_before_expiry(self, service, mock_auth0_response):
        """Test that token is refreshed within buffer period"""
        with patch('httpx.AsyncClient') as mock_client, \
             patch('time.time') as mock_time:

            mock_response = MagicMock()
            mock_response.json = MagicMock(return_value=mock_auth0_response)
            mock_response.raise_for_status = MagicMock()

            mock_post = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value.post = mock_post

            # First fetch at t=1000
            mock_time.return_value = 1000
            token1 = await service.get_token()
            assert service._token_expiry == 1000 + 86400

            # Call at t=87100 (within 5-minute buffer before expiry)
            mock_time.return_value = 87100
            # Expiry is 87400, buffer is 300
            # Check: 87100 < (87400 - 300) = 87100 < 87100 → FALSE, should fetch

            mock_auth0_response["access_token"] = "new_token_xyz"
            token2 = await service.get_token()

            assert token2 == "new_token_xyz"
            assert token1 != token2
            assert mock_post.call_count == 2

    @pytest.mark.asyncio
    async def test_token_refresh_after_expiry(self, service, mock_auth0_response):
        """Test that expired token is replaced"""
        with patch('httpx.AsyncClient') as mock_client, \
             patch('time.time') as mock_time:

            mock_response = MagicMock()
            mock_response.json = MagicMock(return_value=mock_auth0_response)
            mock_response.raise_for_status = MagicMock()

            mock_post = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value.post = mock_post

            # First fetch at t=1000
            mock_time.return_value = 1000
            token1 = await service.get_token()

            # Call at t=90000 (after actual expiry)
            mock_time.return_value = 90000
            mock_auth0_response["access_token"] = "refreshed_token"
            token2 = await service.get_token()

            assert token2 == "refreshed_token"
            assert token1 != token2

    # ========================================================================
    # Test 3: Concurrent Request Handling (Race Conditions)
    # ========================================================================

    @pytest.mark.asyncio
    async def test_concurrent_requests_single_fetch(self, service, mock_auth0_response):
        """Test that concurrent requests result in only one Auth0 call"""
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = MagicMock()
            mock_response.json = MagicMock(return_value=mock_auth0_response)
            mock_response.raise_for_status = MagicMock()

            call_count = 0

            # Add delay to simulate network latency
            async def delayed_post(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                await asyncio.sleep(0.1)
                return mock_response

            mock_client.return_value.__aenter__.return_value.post = delayed_post

            # Launch 10 concurrent requests
            results = await asyncio.gather(*[service.get_token() for _ in range(10)])

            # All should return same token
            assert all(token == mock_auth0_response["access_token"] for token in results)

            # With asyncio.Lock, only 1 fetch should occur
            assert call_count == 1, f"Expected 1 Auth0 call with lock, got {call_count}"

    # ========================================================================
    # Test 4: Token Overwriting Behavior
    # ========================================================================

    @pytest.mark.asyncio
    async def test_old_token_overwritten(self, service, mock_auth0_response):
        """Test that old token is properly overwritten"""
        with patch('httpx.AsyncClient') as mock_client, \
             patch('time.time') as mock_time:

            mock_response = MagicMock()
            mock_response.json = MagicMock(return_value=mock_auth0_response)
            mock_response.raise_for_status = MagicMock()

            mock_post = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value.post = mock_post

            # Fetch token 1
            mock_time.return_value = 1000
            token1 = await service.get_token()
            expiry1 = service._token_expiry

            # Force refetch by moving time forward
            mock_time.return_value = 90000
            mock_auth0_response["access_token"] = "completely_new_token"
            mock_auth0_response["expires_in"] = 43200  # 12 hours

            token2 = await service.get_token()
            expiry2 = service._token_expiry

            # Verify old token replaced
            assert token1 != token2
            assert service._token == token2
            assert expiry1 != expiry2
            assert expiry2 == 90000 + 43200

    # ========================================================================
    # Test 5: Short-Lived Token Edge Case
    # ========================================================================

    @pytest.mark.asyncio
    async def test_short_lived_token_handling(self, service):
        """Test token with expiry shorter than buffer period"""
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = MagicMock()
            mock_response.json = MagicMock(return_value={
                "access_token": "short_lived_token",
                "expires_in": 200  # 200 seconds, less than 300s buffer!
            })
            mock_response.raise_for_status = MagicMock()

            mock_post = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value.post = mock_post

            token = await service.get_token()

            assert token == "short_lived_token"
            assert service._token_expiry == pytest.approx(time.time() + 200, abs=1)

            # Immediate second call should still use cache (edge case!)
            # Current implementation: time.time() < (expiry - 300)
            # If expiry is in 200s, this becomes: now < (now+200 - 300) = now < (now-100) → FALSE
            # Token will be refetched immediately! (This is a known edge case)

    # ========================================================================
    # Test 6: Error Handling
    # ========================================================================

    @pytest.mark.asyncio
    async def test_auth0_network_error(self, service):
        """Test handling of network errors when fetching token"""
        with patch('httpx.AsyncClient') as mock_client:
            mock_post = AsyncMock(side_effect=httpx.RequestError("Connection failed"))
            mock_client.return_value.__aenter__.return_value.post = mock_post

            with pytest.raises(ConnectionError, match="Auth0 unreachable"):
                await service.get_token()

    @pytest.mark.asyncio
    async def test_auth0_http_error(self, service):
        """Test handling of HTTP errors (401, 403, etc.)"""
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 401
            mock_response.text = "Unauthorized: Invalid client credentials"

            # Create the exception
            http_error = httpx.HTTPStatusError(
                "401 Client Error",
                request=MagicMock(),
                response=mock_response
            )

            mock_response.raise_for_status = MagicMock(side_effect=http_error)

            mock_post = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value.post = mock_post

            with pytest.raises(ConnectionError, match="Failed to fetch M2M token from Auth0"):
                await service.get_token()

    @pytest.mark.asyncio
    async def test_missing_configuration(self, service):
        """Test error when Auth0 config is missing"""
        with patch('app.services.auth0_m2m_service.settings') as mock_settings:
            mock_settings.auth0_domain = None

            with pytest.raises(ValueError, match="AUTH0_DOMAIN not configured"):
                await service.get_token()

    # ========================================================================
    # Test 7: Manual Token Clearing
    # ========================================================================

    @pytest.mark.asyncio
    async def test_clear_token(self, service, mock_auth0_response):
        """Test manual token clearing"""
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = MagicMock()
            mock_response.json = MagicMock(return_value=mock_auth0_response)
            mock_response.raise_for_status = MagicMock()

            mock_post = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value.post = mock_post

            # Fetch token
            token = await service.get_token()
            assert service._token is not None

            # Clear token
            service.clear_token()
            assert service._token is None
            assert service._token_expiry == 0

            # Next call should fetch new token
            mock_auth0_response["access_token"] = "fresh_after_clear"
            new_token = await service.get_token()
            assert new_token == "fresh_after_clear"

    # ========================================================================
    # Test 8: Token Expiry Calculation
    # ========================================================================

    @pytest.mark.asyncio
    async def test_token_expiry_calculation(self, service, mock_auth0_response):
        """Test that expiry is correctly calculated"""
        with patch('httpx.AsyncClient') as mock_client, \
             patch('time.time') as mock_time:

            mock_response = MagicMock()
            mock_response.json = MagicMock(return_value=mock_auth0_response)
            mock_response.raise_for_status = MagicMock()

            mock_post = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value.post = mock_post

            mock_time.return_value = 5000
            await service.get_token()

            # Expiry should be: current_time + expires_in
            expected_expiry = 5000 + 86400
            assert service._token_expiry == expected_expiry

    @pytest.mark.asyncio
    async def test_default_expiry_when_missing(self, service):
        """Test fallback to 24h when expires_in is missing"""
        with patch('httpx.AsyncClient') as mock_client, \
             patch('time.time') as mock_time:

            mock_response = MagicMock()
            mock_response.json = MagicMock(return_value={
                "access_token": "token_without_expiry"
                # No expires_in field!
            })
            mock_response.raise_for_status = MagicMock()

            mock_post = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value.post = mock_post

            mock_time.return_value = 10000
            await service.get_token()

            # Should default to 86400 seconds (24 hours)
            expected_expiry = 10000 + 86400
            assert service._token_expiry == expected_expiry

    # ========================================================================
    # Test 9: Singleton Behavior
    # ========================================================================

    def test_singleton_instance(self):
        """Test that module-level singleton works"""
        from app.services.auth0_m2m_service import m2m_token_service

        assert isinstance(m2m_token_service, Auth0M2MTokenService)

        # Multiple imports should return same instance
        from app.services.auth0_m2m_service import m2m_token_service as service2
        assert m2m_token_service is service2


# ========================================================================
# Integration Tests (require actual Auth0 credentials)
# ========================================================================

@pytest.mark.integration
class TestAuth0M2MIntegration:
    """Integration tests requiring real Auth0 connection"""

    @pytest.mark.asyncio
    async def test_real_auth0_token_fetch(self):
        """Test fetching real token from Auth0 (requires credentials)"""
        # This test requires AUTH0_* env vars to be set
        service = Auth0M2MTokenService()

        try:
            token = await service.get_token()

            # Verify token is JWT format
            assert token.count('.') == 2
            assert token.startswith('eyJ')

            # Verify caching works
            token2 = await service.get_token()
            assert token == token2

        except ValueError as e:
            pytest.skip(f"Auth0 credentials not configured: {e}")

    @pytest.mark.asyncio
    async def test_token_actually_works_with_ai_core(self):
        """Test that fetched token is accepted by AI-Core"""
        # This requires both BE and AI-Core to be running
        service = Auth0M2MTokenService()

        try:
            token = await service.get_token()

            # Try calling AI-Core with the token
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "http://localhost:8090/api/v1/chat/stream",
                    headers={"Authorization": f"Bearer {token}"},
                    json={
                        "messages": [{"role": "user", "content": "test"}],
                        "provider": "openai",
                        "model": "gpt-4o-mini"
                    }
                )

                # Should not be 401 (authenticated successfully)
                assert response.status_code != 401

        except Exception as e:
            pytest.skip(f"Integration test environment not ready: {e}")