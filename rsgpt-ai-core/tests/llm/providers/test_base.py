"""Unit tests for base LLM classes"""

import pytest

from app.llm.providers.base import LLMResponse


class TestLLMResponse:
    """Test LLMResponse class"""

    def test_llm_response_initialization(self):
        """Test LLMResponse initialization"""
        response = LLMResponse(
            content="Test response",
            provider="openai",
            model="gpt-4",
            usage={"total_tokens": 100},
        )

        assert response.content == "Test response"
        assert response.provider == "openai"
        assert response.model == "gpt-4"
        assert response.usage == {"total_tokens": 100}

    def test_llm_response_default_usage(self):
        """Test LLMResponse with default usage"""
        response = LLMResponse(
            content="Test response", provider="openai", model="gpt-4"
        )

        assert response.usage == {}
