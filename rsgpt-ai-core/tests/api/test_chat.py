"""Tests for chat API endpoints"""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.llm.providers.base import LLMResponse
from app.main import app
from app.models.chat import ChatMessage, ChatRequest, ReasoningEffort
from app.llm.providers.openai_client import _convert_chat_messages_to_responses_input

# Test token for BE service (must match conftest.py)
TEST_BE_TOKEN = "test-be-service-token-12345"


class TestChatMessageModels:
    """Chat message parsing must preserve tool loops for MCP inner agents."""

    def test_assistant_tool_calls_survive_request_round_trip(self):
        request = ChatRequest(
            messages=[
                ChatMessage(role="user", content="hi"),
                ChatMessage(
                    role="assistant",
                    content="",
                    tool_calls=[
                        {
                            "id": "call_a",
                            "type": "function",
                            "function": {"name": "fetch_url", "arguments": "{}"},
                        },
                        {
                            "id": "call_b",
                            "type": "function",
                            "function": {
                                "name": "rs3_list_tutorials",
                                "arguments": "{}",
                            },
                        },
                    ],
                ),
                ChatMessage(role="tool", tool_call_id="call_a", content="page"),
                ChatMessage(role="tool", tool_call_id="call_b", content="[]"),
            ]
        )

        dumped = [
            {k: v for k, v in msg.model_dump().items() if v is not None}
            for msg in request.messages
        ]

        assert dumped[1]["tool_calls"][0]["id"] == "call_a"
        assert dumped[1]["tool_calls"][1]["function"]["name"] == "rs3_list_tutorials"

        converted = _convert_chat_messages_to_responses_input(dumped)
        assert converted[1]["call_id"] == "call_a"
        assert converted[2]["call_id"] == "call_b"
        assert converted[3]["call_id"] == "call_a"
        assert converted[4]["call_id"] == "call_b"


class TestChatAPI:
    """Test chat API endpoints"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)

    def test_chat_info(self, client):
        """Test chat info endpoint"""
        response = client.get("/api/v1/chat/")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["service"] == "rsgpt-ai-core-chat"
        assert "available_providers" in data

    @patch("app.llm.factory.LLMClientFactory.create_client")
    @patch("app.api.routes.chat.llm_service.generate")
    def test_chat_completion_with_reasoning_effort(
        self, mock_generate, mock_create_client, client
    ):
        """Test chat completion with reasoning effort parameter"""
        # Mock the client creation to avoid API key validation
        mock_create_client.return_value = None

        mock_response = LLMResponse(
            content="Thoughtful response",
            provider="openai",
            model="o1-mini",
            usage={"total_tokens": 50},
        )
        mock_generate.return_value = mock_response

        request_data = {
            "messages": [{"role": "user", "content": "Solve this complex problem"}],
            "provider": "openai",
            "model": "o1-mini",
            "reasoning_effort": "high",
        }
        headers = {"X-Service-Token": TEST_BE_TOKEN}

        response = client.post(
            "/api/v1/chat/stream", json=request_data, headers=headers
        )

        assert response.status_code == 200
        # Verify that reasoning_effort was passed to the LLM service
        mock_generate.assert_called_once()
        call_kwargs = mock_generate.call_args.kwargs
        assert call_kwargs["reasoning_effort"] == "high"

    @patch("app.llm.factory.LLMClientFactory.create_client")
    @patch("app.api.routes.chat.llm_service.generate")
    def test_chat_completion_streaming(self, mock_generate, mock_create_client, client):
        """Test streaming chat completion"""
        # Mock the client creation to avoid API key validation
        mock_create_client.return_value = None

        # Mock streaming response
        async def mock_stream():
            for chunk in ["Hello", " there", "!"]:
                yield chunk

        mock_generate.return_value = mock_stream()

        request_data = {
            "messages": [{"role": "user", "content": "Hello"}],
            "provider": "openai",
        }
        headers = {"X-Service-Token": TEST_BE_TOKEN}

        response = client.post(
            "/api/v1/chat/stream", json=request_data, headers=headers
        )

        assert response.status_code == 200
        assert response.headers["content-type"] == "text/event-stream; charset=utf-8"

        # Check that it returns streaming content
        content = response.content.decode()
        assert "Hello" in content
        assert "there" in content
        assert "!" in content

    def test_chat_completion_validation_error_empty_messages(self, client):
        """Test validation error for empty messages"""
        # Send request with empty messages
        request_data = {
            "messages": [],  # Empty messages should fail validation
            "provider": "openai",
        }
        headers = {"X-Service-Token": TEST_BE_TOKEN}

        response = client.post(
            "/api/v1/chat/stream", json=request_data, headers=headers
        )

        assert response.status_code == 422  # Validation error

    def test_chat_completion_invalid_provider(self, client):
        """Test error for invalid provider"""
        # Send request with invalid provider
        request_data = {
            "messages": [{"role": "user", "content": "Hello"}],
            "provider": "invalid_provider",
        }
        headers = {"X-Service-Token": TEST_BE_TOKEN}

        response = client.post(
            "/api/v1/chat/stream", json=request_data, headers=headers
        )

        assert response.status_code == 400  # Bad request for invalid provider

    @patch("app.llm.factory.LLMClientFactory.create_client")
    @patch("app.api.routes.chat.llm_service.generate")
    def test_chat_completion_with_parameters(
        self, mock_generate, mock_create_client, client
    ):
        """Test chat completion with additional parameters"""
        # Mock the client creation to avoid API key validation
        mock_create_client.return_value = None

        mock_response = LLMResponse(
            content="Response with parameters",
            provider="anthropic",
            model="claude-3-haiku",
            usage={"total_tokens": 30},
        )
        mock_generate.return_value = mock_response

        request_data = {
            "messages": [{"role": "user", "content": "Test with parameters"}],
            "provider": "anthropic",
            "model": "claude-3-haiku",
            "max_tokens": 100,
            "temperature": 0.7,
        }
        headers = {"X-Service-Token": TEST_BE_TOKEN}

        response = client.post(
            "/api/v1/chat/stream", json=request_data, headers=headers
        )

        assert response.status_code == 200

        # Verify parameters were passed correctly
        mock_generate.assert_called_once()
        call_kwargs = mock_generate.call_args.kwargs
        assert call_kwargs["max_tokens"] == 100
        assert call_kwargs["temperature"] == 0.7
        assert call_kwargs["provider"] == "anthropic"
        assert call_kwargs["model"] == "claude-3-haiku"
