"""Unit tests for OpenAI client"""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.llm.providers.base import LLMResponse
from app.llm.providers.openai_client import (
    OpenAIClient,
    _convert_chat_messages_to_responses_input,
)


class TestConvertChatMessagesToResponsesInput:
    def test_converts_tool_role_to_function_call_output(self):
        messages = [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Run task"},
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "call_abc",
                        "type": "function",
                        "function": {
                            "name": "grep_files",
                            "arguments": '{"pattern": "foo"}',
                        },
                    }
                ],
            },
            {"role": "tool", "tool_call_id": "call_abc", "content": "match found"},
        ]

        converted = _convert_chat_messages_to_responses_input(messages)

        assert converted[0] == {"role": "system", "content": "You are helpful."}
        assert converted[1] == {"role": "user", "content": "Run task"}
        assert converted[2] == {
            "type": "function_call",
            "call_id": "call_abc",
            "name": "grep_files",
            "arguments": '{"pattern": "foo"}',
        }
        assert converted[3] == {
            "type": "function_call_output",
            "call_id": "call_abc",
            "output": "match found",
        }

    def test_passes_through_responses_items(self):
        messages = [
            {
                "type": "function_call_output",
                "call_id": "call_xyz",
                "output": "done",
            }
        ]
        assert _convert_chat_messages_to_responses_input(messages) == messages

    def test_converts_parallel_tool_calls(self):
        messages = [
            {"role": "user", "content": "list tutorials"},
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "call_a",
                        "type": "function",
                        "function": {"name": "fetch_url", "arguments": '{"url": "x"}'},
                    },
                    {
                        "id": "call_b",
                        "type": "function",
                        "function": {"name": "rs3_list_tutorials", "arguments": "{}"},
                    },
                ],
            },
            {"role": "tool", "tool_call_id": "call_a", "content": "page"},
            {"role": "tool", "tool_call_id": "call_b", "content": "[]"},
        ]

        converted = _convert_chat_messages_to_responses_input(messages)

        assert converted == [
            {"role": "user", "content": "list tutorials"},
            {
                "type": "function_call",
                "call_id": "call_a",
                "name": "fetch_url",
                "arguments": '{"url": "x"}',
            },
            {
                "type": "function_call",
                "call_id": "call_b",
                "name": "rs3_list_tutorials",
                "arguments": "{}",
            },
            {"type": "function_call_output", "call_id": "call_a", "output": "page"},
            {"type": "function_call_output", "call_id": "call_b", "output": "[]"},
        ]


class TestOpenAIClient:
    """Test OpenAI client implementation"""

    @pytest.fixture
    def openai_client(self):
        """Create OpenAI client for testing"""
        return OpenAIClient("test-api-key")

    @pytest.mark.asyncio
    @patch("app.llm.providers.openai_client.OpenAI")
    async def test_generate_non_streaming(self, mock_openai_class, openai_client):
        """Test non-streaming response generation"""
        # Mock the OpenAI responses API response
        mock_response = Mock()
        mock_response.output_text = "Test response from OpenAI"
        mock_response.usage = Mock()
        mock_response.usage.input_tokens = 10
        mock_response.usage.output_tokens = 15
        mock_response.usage.total_tokens = 25

        mock_client = Mock()
        mock_client.responses.create.return_value = mock_response
        mock_openai_class.return_value = mock_client

        # Create new client to use mocked OpenAI
        client = OpenAIClient("test-key")
        result = await client.generate("Test prompt", stream=False)

        assert isinstance(result, LLMResponse)
        assert result.content == "Test response from OpenAI"
        assert result.provider == "openai"
        assert result.usage["total_tokens"] == 25

        # Verify the API was called correctly (using default model gpt-5)
        mock_client.responses.create.assert_called_once_with(
            model="gpt-5",
            input=[{"role": "user", "content": "Test prompt"}],
            stream=False,
        )

    @pytest.mark.asyncio
    @patch("app.llm.providers.openai_client.OpenAI")
    async def test_generate_non_streaming_converts_tool_messages(
        self, mock_openai_class, openai_client
    ):
        """Multi-turn tool loops must be converted before calling Responses API."""
        mock_response = Mock()
        mock_response.output_text = "done"
        mock_response.usage = Mock()
        mock_response.usage.input_tokens = 10
        mock_response.usage.output_tokens = 5
        mock_response.usage.total_tokens = 15
        mock_response.output = []

        mock_client = Mock()
        mock_client.responses.create.return_value = mock_response
        mock_openai_class.return_value = mock_client

        client = OpenAIClient("test-key")
        messages = [
            {"role": "user", "content": "hello"},
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {"name": "list_dir", "arguments": "{}"},
                    }
                ],
            },
            {"role": "tool", "tool_call_id": "call_1", "content": "[]"},
        ]
        await client.generate("ignored", stream=False, messages=messages)

        call_kwargs = mock_client.responses.create.call_args.kwargs
        assert call_kwargs["input"] == [
            {"role": "user", "content": "hello"},
            {
                "type": "function_call",
                "call_id": "call_1",
                "name": "list_dir",
                "arguments": "{}",
            },
            {
                "type": "function_call_output",
                "call_id": "call_1",
                "output": "[]",
            },
        ]

    @pytest.mark.asyncio
    @patch("app.llm.providers.openai_client.AsyncOpenAI")
    async def test_generate_streaming(self, mock_async_openai_class, openai_client):
        """Test streaming response generation"""
        # Mock streaming events for responses API
        mock_events = []
        for text in ["Hello", " world", "!"]:
            event = Mock()
            event.type = "response.output_text.delta"
            event.delta = text
            mock_events.append(event)

        # Create async iterator for streaming
        async def async_event_iter():
            for event in mock_events:
                yield event

        # Mock the async client
        mock_async_client = AsyncMock()
        mock_async_client.responses.create.return_value = async_event_iter()
        mock_async_openai_class.return_value = mock_async_client

        # Create new client to use mocked AsyncOpenAI
        client = OpenAIClient("test-key")
        result = await client.generate("Test prompt", stream=True)

        # Collect streaming results
        chunks = []
        async for chunk in result:
            chunks.append(chunk)

        assert chunks == ["Hello", " world", "!"]

        # Verify the API was called correctly (using default model gpt-5)
        mock_async_client.responses.create.assert_called_once_with(
            model="gpt-5",
            input=[{"role": "user", "content": "Test prompt"}],
            stream=True,
        )

    def test_provider_name(self, openai_client):
        """Test provider name property"""
        assert openai_client.provider_name == "openai"
