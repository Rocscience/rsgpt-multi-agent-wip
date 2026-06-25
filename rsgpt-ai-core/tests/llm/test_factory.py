"""Unit tests for LLM Client Factory"""

from unittest.mock import patch

import pytest

from app.llm.factory import LLMClientFactory
from app.llm.providers.claude_client import ClaudeClient
from app.llm.providers.openai_client import OpenAIClient
from app.llm.providers.perplexity_client import PerplexityClient


class TestLLMClientFactory:
    """Test LLM client factory"""

    @patch("app.llm.factory.settings")
    def test_create_openai_client(self, mock_settings):
        """Test creating OpenAI client"""
        mock_settings.openai_api_key = "test-openai-key"
        mock_settings.default_llm_provider = "openai"

        client = LLMClientFactory.create_client("openai")

        assert isinstance(client, OpenAIClient)
        assert client.api_key == "test-openai-key"

    @patch("app.llm.providers.claude_client.AsyncAnthropic")
    @patch("app.llm.factory.settings")
    def test_create_claude_client(self, mock_settings, mock_anthropic):
        """Test creating Claude client"""
        mock_settings.anthropic_api_key = "test-anthropic-key"

        client = LLMClientFactory.create_client("anthropic")

        assert isinstance(client, ClaudeClient)
        assert client.api_key == "test-anthropic-key"

    @patch("app.llm.factory.settings")
    def test_create_perplexity_client(self, mock_settings):
        """Test creating Perplexity client"""
        mock_settings.perplexity_api_key = "test-perplexity-key"

        client = LLMClientFactory.create_client("perplexity")

        assert isinstance(client, PerplexityClient)
        assert client.api_key == "test-perplexity-key"

    @patch("app.llm.factory.settings")
    def test_create_default_client(self, mock_settings):
        """Test creating client with default provider"""
        mock_settings.default_llm_provider = "openai"
        mock_settings.openai_api_key = "test-openai-key"

        client = LLMClientFactory.create_client()

        assert isinstance(client, OpenAIClient)

    @patch("app.llm.factory.settings")
    def test_create_client_missing_api_key(self, mock_settings):
        """Test error when API key is missing"""
        mock_settings.openai_api_key = ""

        with pytest.raises(ValueError, match="OpenAI API key is required"):
            LLMClientFactory.create_client("openai")

    def test_create_client_unsupported_provider(self):
        """Test error for unsupported provider"""
        with pytest.raises(ValueError, match="Unsupported provider"):
            LLMClientFactory.create_client("unsupported")
