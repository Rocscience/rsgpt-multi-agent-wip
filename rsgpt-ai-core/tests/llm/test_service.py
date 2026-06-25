"""Unit tests for LLM Service"""

from unittest.mock import AsyncMock, patch

import pytest

from app.llm.providers.base import LLMResponse
from app.llm.service import LLMService


class TestLLMService:
    """Test high-level LLM service"""

    @pytest.fixture
    def llm_service_instance(self):
        """Create LLM service for testing"""
        return LLMService("openai")

    @pytest.mark.asyncio
    @patch("app.llm.service.LLMClientFactory.create_client")
    async def test_generate_with_default_provider(
        self, mock_create_client, llm_service_instance
    ):
        """Test generate with default provider"""
        mock_client = AsyncMock()
        mock_response = LLMResponse("Test response", "openai", "gpt-4")
        mock_client.generate.return_value = mock_response
        mock_create_client.return_value = mock_client

        result = await llm_service_instance.generate("Test prompt")

        assert result == mock_response
        mock_create_client.assert_called_once_with("openai")
        mock_client.generate.assert_called_once_with(
            "Test prompt", False, None, None, None, None, tools=None, messages=None
        )

    @pytest.mark.asyncio
    @patch("app.llm.service.LLMClientFactory.create_client")
    async def test_generate_with_specific_provider(
        self, mock_create_client, llm_service_instance
    ):
        """Test generate with specific provider"""
        mock_client = AsyncMock()
        mock_response = LLMResponse("Test response", "anthropic", "claude-3")
        mock_client.generate.return_value = mock_response
        mock_create_client.return_value = mock_client

        result = await llm_service_instance.generate(
            "Test prompt", provider="anthropic"
        )

        assert result == mock_response
        mock_create_client.assert_called_once_with("anthropic")
        mock_client.generate.assert_called_once_with(
            "Test prompt", False, None, None, None, None, tools=None, messages=None
        )

    @pytest.mark.asyncio
    @patch("app.llm.service.LLMClientFactory.create_client")
    async def test_generate_streaming(self, mock_create_client, llm_service_instance):
        """Test streaming generate"""
        mock_client = AsyncMock()

        async def mock_streaming_response():
            for chunk in ["Hello", " world", "!"]:
                yield chunk

        mock_client.generate.return_value = mock_streaming_response()
        mock_create_client.return_value = mock_client

        result = await llm_service_instance.generate("Test prompt", stream=True)

        chunks = []
        async for chunk in result:
            chunks.append(chunk)

        assert chunks == ["Hello", " world", "!"]
        mock_client.generate.assert_called_once_with(
            "Test prompt", True, None, None, None, None, tools=None, messages=None
        )

    @patch("app.llm.service.settings")
    def test_get_available_providers(self, mock_settings, llm_service_instance):
        """Test getting available providers"""
        mock_settings.openai_api_key = "test-key"
        mock_settings.anthropic_api_key = ""
        mock_settings.perplexity_api_key = "test-key"

        available = llm_service_instance.get_available_providers()

        assert available == {"openai": True, "anthropic": False, "perplexity": True}
