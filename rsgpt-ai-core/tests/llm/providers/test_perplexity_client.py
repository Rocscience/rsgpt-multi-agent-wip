"""Unit tests for Perplexity client"""

import json
from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.llm.providers.base import LLMResponse
from app.llm.providers.perplexity_client import PerplexityClient


class TestPerplexityClient:
    """Test Perplexity client implementation"""

    @pytest.mark.asyncio
    @patch("app.llm.providers.perplexity_client.AsyncOpenAI")
    async def test_generate_non_streaming(self, mock_openai_class):
        """Test non-streaming response generation"""
        # Mock OpenAI response object
        mock_message = Mock()
        mock_message.content = "Test response from Perplexity"

        mock_choice = Mock()
        mock_choice.message = mock_message

        mock_usage = Mock()
        mock_usage.prompt_tokens = 10
        mock_usage.completion_tokens = 20
        mock_usage.total_tokens = 30

        mock_response = Mock()
        mock_response.choices = [mock_choice]
        mock_response.usage = mock_usage

        # Mock the OpenAI client
        mock_client = AsyncMock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_class.return_value = mock_client

        # Create client after patch is applied
        perplexity_client = PerplexityClient("test-api-key")

        result = await perplexity_client.generate("Test prompt", stream=False)

        assert isinstance(result, LLMResponse)
        assert result.content == "Test response from Perplexity"
        assert result.provider == "perplexity"
        assert result.model == "sonar-pro"
        assert result.usage["prompt_tokens"] == 10
        assert result.usage["completion_tokens"] == 20
        assert result.usage["total_tokens"] == 30

        # Verify the API was called correctly
        mock_client.chat.completions.create.assert_called_once_with(
            model="sonar-pro",
            messages=[{"role": "user", "content": "Test prompt"}],
            stream=False,
            extra_body={"enable_search_classifier": True},
        )

    @pytest.mark.asyncio
    @patch("app.llm.providers.perplexity_client.AsyncOpenAI")
    async def test_generate_streaming(self, mock_openai_class):
        """Test streaming response generation"""
        # Mock streaming chunks
        mock_chunks = []

        # First chunk
        delta1 = Mock()
        delta1.content = "Hello"
        choice1 = Mock()
        choice1.delta = delta1
        chunk1 = Mock()
        chunk1.choices = [choice1]
        mock_chunks.append(chunk1)

        # Second chunk
        delta2 = Mock()
        delta2.content = " world"
        choice2 = Mock()
        choice2.delta = delta2
        chunk2 = Mock()
        chunk2.choices = [choice2]
        mock_chunks.append(chunk2)

        # Third chunk
        delta3 = Mock()
        delta3.content = "!"
        choice3 = Mock()
        choice3.delta = delta3
        chunk3 = Mock()
        chunk3.choices = [choice3]
        mock_chunks.append(chunk3)

        # Mock async iterator
        async def mock_async_iter():
            for chunk in mock_chunks:
                yield chunk

        mock_completion = AsyncMock()
        mock_completion.__aiter__ = lambda self: mock_async_iter()

        # Mock the OpenAI client
        mock_client = AsyncMock()
        mock_client.chat.completions.create.return_value = mock_completion
        mock_openai_class.return_value = mock_client

        # Create client after patch is applied
        perplexity_client = PerplexityClient("test-api-key")

        result = await perplexity_client.generate("Test prompt", stream=True)

        # Collect streaming results
        chunks = []
        async for chunk in result:
            chunks.append(chunk)

        assert chunks == ["Hello", " world", "!"]

        # Verify the API was called correctly
        mock_client.chat.completions.create.assert_called_once_with(
            model="sonar-pro",
            messages=[{"role": "user", "content": "Test prompt"}],
            stream=True,
            extra_body={"enable_search_classifier": True},
        )

    @patch("app.llm.providers.perplexity_client.AsyncOpenAI")
    def test_provider_name(self, mock_openai_class):
        """Test provider name property"""
        perplexity_client = PerplexityClient("test-api-key")
        assert perplexity_client.provider_name == "perplexity"
