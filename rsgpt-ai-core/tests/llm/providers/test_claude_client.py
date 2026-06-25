"""Unit tests for Claude client"""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.llm.providers.base import LLMResponse
from app.llm.providers.claude_client import ClaudeClient


class TestClaudeClient:
    """Test Claude client implementation"""

    @pytest.fixture
    @patch("app.llm.providers.claude_client.AsyncAnthropic")
    def claude_client(self, mock_anthropic):
        """Create Claude client for testing"""
        return ClaudeClient("test-api-key")

    @pytest.mark.asyncio
    @patch("app.llm.providers.claude_client.AsyncAnthropic")
    async def test_generate_non_streaming(self, mock_anthropic_class, claude_client):
        """Test non-streaming response generation"""
        # Mock the AsyncAnthropic response
        mock_response = Mock()
        mock_response.content = [Mock()]
        mock_response.content[0].text = "Test response from Claude"
        mock_response.usage.input_tokens = 10
        mock_response.usage.output_tokens = 15

        mock_client = AsyncMock()
        mock_client.messages.create.return_value = mock_response
        mock_anthropic_class.return_value = mock_client

        # Create new client to use mocked AsyncAnthropic
        client = ClaudeClient("test-key")
        result = await client.generate("Test prompt", stream=False)

        assert isinstance(result, LLMResponse)
        assert result.content == "Test response from Claude"
        assert result.provider == "anthropic"
        assert result.usage["total_tokens"] == 25

        # Verify the API was called correctly
        mock_client.messages.create.assert_called_once_with(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            messages=[{"role": "user", "content": "Test prompt"}],
        )

    @pytest.mark.asyncio
    @patch("app.llm.providers.claude_client.AsyncAnthropic")
    async def test_generate_streaming(self, mock_anthropic_class, claude_client):
        """Test streaming response generation"""

        # Mock async streaming context manager
        async def async_text_stream():
            for text in ["Hello", " world", "!"]:
                yield text

        # Create a proper async context manager mock
        class MockAsyncContextManager:
            def __init__(self):
                self.text_stream = async_text_stream()

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                return None

        mock_context_manager = MockAsyncContextManager()

        mock_client = AsyncMock()
        # Make stream method return the context manager directly, not as a coroutine
        mock_client.messages.stream = Mock(return_value=mock_context_manager)
        mock_anthropic_class.return_value = mock_client

        # Create new client to use mocked AsyncAnthropic
        client = ClaudeClient("test-key")
        result = await client.generate("Test prompt", stream=True)

        # Collect streaming results
        chunks = []
        async for chunk in result:
            chunks.append(chunk)

        assert chunks == ["Hello", " world", "!"]

        # Verify the API was called correctly
        mock_client.messages.stream.assert_called_once_with(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            messages=[{"role": "user", "content": "Test prompt"}],
        )

    @patch("app.llm.providers.claude_client.AsyncAnthropic")
    def test_provider_name(self, mock_anthropic_class):
        """Test provider name property"""
        client = ClaudeClient("test-key")
        assert client.provider_name == "anthropic"
