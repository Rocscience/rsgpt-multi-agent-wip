"""Integration tests for provider switching"""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.llm.providers.base import LLMResponse
from app.llm.service import LLMService


class TestProviderSwitching:
    """Integration tests for provider switching"""

    @pytest.mark.asyncio
    @patch("app.llm.factory.settings")
    @patch("app.llm.providers.openai_client.OpenAI")
    @patch("app.llm.providers.claude_client.AsyncAnthropic")
    @patch("app.llm.providers.perplexity_client.AsyncOpenAI")
    async def test_provider_switching_works(
        self, mock_perplexity_openai, mock_anthropic, mock_openai, mock_settings
    ):
        """Test that provider switching works correctly"""
        # Configure all API keys
        mock_settings.openai_api_key = "openai-key"
        mock_settings.anthropic_api_key = "anthropic-key"
        mock_settings.perplexity_api_key = "perplexity-key"

        # Mock OpenAI
        mock_openai_response = Mock()
        mock_openai_response.output_text = "OpenAI response"
        mock_openai_response.usage = Mock()
        mock_openai_response.usage.input_tokens = 10
        mock_openai_response.usage.output_tokens = 15
        mock_openai_response.usage.total_tokens = 25

        mock_openai_client = Mock()
        mock_openai_client.responses.create.return_value = mock_openai_response
        mock_openai.return_value = mock_openai_client

        # Mock Anthropic
        mock_anthropic_response = Mock()
        mock_anthropic_response.content = [Mock()]
        mock_anthropic_response.content[0].text = "Claude response"
        mock_anthropic_response.usage.input_tokens = 10
        mock_anthropic_response.usage.output_tokens = 15

        mock_anthropic_client = AsyncMock()
        mock_anthropic_client.messages.create.return_value = mock_anthropic_response
        mock_anthropic.return_value = mock_anthropic_client

        # Mock Perplexity (using OpenAI client structure)
        mock_perplexity_message = Mock()
        mock_perplexity_message.content = "Perplexity response"

        mock_perplexity_choice = Mock()
        mock_perplexity_choice.message = mock_perplexity_message

        mock_perplexity_usage = Mock()
        mock_perplexity_usage.prompt_tokens = 10
        mock_perplexity_usage.completion_tokens = 15
        mock_perplexity_usage.total_tokens = 30

        mock_perplexity_response = Mock()
        mock_perplexity_response.choices = [mock_perplexity_choice]
        mock_perplexity_response.usage = mock_perplexity_usage

        mock_perplexity_client = AsyncMock()
        mock_perplexity_client.chat.completions.create.return_value = (
            mock_perplexity_response
        )
        mock_perplexity_openai.return_value = mock_perplexity_client

        # Test service
        service = LLMService()

        # Test OpenAI
        result = await service.generate("Test prompt", provider="openai")
        assert result.content == "OpenAI response"
        assert result.provider == "openai"

        # Test Claude
        result = await service.generate("Test prompt", provider="anthropic")
        assert result.content == "Claude response"
        assert result.provider == "anthropic"

        # Test Perplexity
        result = await service.generate("Test prompt", provider="perplexity")
        assert result.content == "Perplexity response"
        assert result.provider == "perplexity"
