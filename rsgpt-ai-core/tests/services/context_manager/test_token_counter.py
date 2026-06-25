"""Unit tests for TokenCounter functionality"""

from unittest.mock import patch

import pytest

from app.services.context_manager.token_counter import (
    TokenCounter,
    num_tokens_for_tools,
    num_tokens_from_messages,
    num_tokens_from_string,
)


class TestTokenCounter:
    """Test cases for TokenCounter class"""

    def test_supported_models(self):
        """Test that supported models are correctly defined"""
        expected_models = {
            "gpt-5.1-2025-11-13",
            "gpt-5.2-2025-12-11",
            "claude-sonnet-4-5-20250929",
            "claude-haiku-4-5-20251001",
            "claude-opus-4-5-20251101",
            "grok-4-1-fast-reasoning",
            "grok-4-1-fast-non-reasoning",
            "sonar-reasoning",
            "gemini-3-flash-preview",
        }
        # Import the pre-computed mappings
        from app.services.context_manager.token_counter import _SUPPORTED_MODELS

        assert set(_SUPPORTED_MODELS.keys()) == expected_models

    def test_get_encoding_for_supported_model(self):
        """Test getting encoding for supported models"""
        # Test GPT-5
        encoding = TokenCounter.get_encoding_for_model("gpt-5.1-2025-11-13")
        assert encoding is not None
        assert hasattr(encoding, "encode")

        # Test Claude
        encoding = TokenCounter.get_encoding_for_model("claude-sonnet-4-5-20250929")
        assert encoding is not None

        # Test with provider prefix
        encoding = TokenCounter.get_encoding_for_model("openai/gpt-5.1-2025-11-13")
        assert encoding is not None

    def test_get_encoding_for_unsupported_model(self):
        """Test that unsupported models raise ValueError"""
        with pytest.raises(ValueError, match="not supported for context management"):
            TokenCounter.get_encoding_for_model("gpt-4")

        with pytest.raises(ValueError, match="not supported for context management"):
            TokenCounter.get_encoding_for_model("unsupported-model")

    def test_count_tokens_basic(self):
        """Test basic token counting"""
        text = "Hello world"
        tokens = TokenCounter.count_tokens(text, "gpt-5.1-2025-11-13")
        assert isinstance(tokens, int)
        assert tokens > 0

    def test_count_tokens_empty_string(self):
        """Test token counting with empty string"""
        tokens = TokenCounter.count_tokens("", "gpt-5.1-2025-11-13")
        assert tokens == 0

    def test_count_tokens_requires_model(self):
        """Test that model_name is required"""
        with pytest.raises(ValueError, match="model_name is required"):
            TokenCounter.count_tokens("test", "")

        with pytest.raises(ValueError, match="model_name is required"):
            TokenCounter.count_tokens("test", None)

    def test_count_tokens_in_messages(self):
        """Test counting tokens in message list"""
        messages = [
            {"role": "system", "content": "You are helpful"},
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
        ]

        tokens = TokenCounter.count_tokens_in_messages(messages, "gpt-5.1-2025-11-13")
        assert isinstance(tokens, int)
        assert tokens > 0

    def test_count_tokens_in_messages_empty(self):
        """Test counting tokens in empty message list"""
        tokens = TokenCounter.count_tokens_in_messages([], "gpt-5.1-2025-11-13")
        assert tokens == 0

    def test_count_tokens_for_tools(self):
        """Test counting tokens for tools/functions"""
        functions = [
            {
                "function": {
                    "name": "search_knowledge",
                    "description": "Search knowledge base",
                    "parameters": {
                        "properties": {
                            "query": {"type": "string", "description": "Search query"},
                            "limit": {
                                "type": "integer",
                                "description": "Max results",
                                "enum": [5, 10],
                            },
                        }
                    },
                }
            }
        ]

        messages = [{"role": "user", "content": "Search for something"}]
        tokens = TokenCounter.count_tokens_for_tools(
            functions, messages, "gpt-5.1-2025-11-13"
        )
        assert isinstance(tokens, int)
        assert tokens > 0

    def test_estimate_max_tokens(self):
        """Test max token estimation for supported models"""
        # Test GPT-5
        max_tokens = TokenCounter.estimate_max_tokens("gpt-5.1-2025-11-13")
        assert max_tokens == 350000

        # Test Claude models
        max_tokens = TokenCounter.estimate_max_tokens("claude-sonnet-4-5-20250929")
        assert max_tokens == 200000

        # Test xAI model
        max_tokens = TokenCounter.estimate_max_tokens("grok-4-1-fast-reasoning")
        assert max_tokens == 350000


class TestConvenienceFunctions:
    """Test cases for convenience functions"""

    def test_num_tokens_from_string(self):
        """Test num_tokens_from_string convenience function"""
        tokens = num_tokens_from_string("Hello world", "gpt-5.1-2025-11-13")
        assert isinstance(tokens, int)
        assert tokens > 0

    def test_num_tokens_from_messages(self):
        """Test num_tokens_from_messages convenience function"""
        messages = [{"role": "user", "content": "Hello"}]
        tokens = num_tokens_from_messages(messages, "gpt-5.1-2025-11-13")
        assert isinstance(tokens, int)
        assert tokens > 0

    def test_num_tokens_for_tools(self):
        """Test num_tokens_for_tools convenience function"""
        functions = [{"function": {"name": "test", "description": "test function"}}]
        messages = [{"role": "user", "content": "Test"}]
        tokens = num_tokens_for_tools(functions, messages, "gpt-5.1-2025-11-13")
        assert isinstance(tokens, int)
        assert tokens > 0

    def test_convenience_functions_require_model(self):
        """Test that convenience functions require model name"""
        with pytest.raises(ValueError):
            num_tokens_from_string("test", "")

        with pytest.raises(ValueError):
            num_tokens_from_messages([{"role": "user", "content": "test"}], "")

        # num_tokens_for_tools should gracefully handle unsupported models with fallback
        # (try-catch functionality now provides graceful degradation)
        result = num_tokens_for_tools(
            [], [{"role": "user", "content": "test"}], "unsupported-model"
        )
        assert isinstance(result, int)
        assert result > 0  # Should return a conservative estimate
