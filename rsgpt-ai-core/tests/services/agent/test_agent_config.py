"""Unit tests for agent configuration utilities"""

from unittest.mock import MagicMock, patch

import pytest
from agents import ModelSettings
from agents.extensions.models.litellm_model import LitellmModel

from app.services.agent.agent_config import (
    SUPPORTED_PROVIDERS,
    ResolvedModel,
    build_run_config,
    create_context_hooks,
    create_model_settings,
    resolve_model,
    validate_reasoning_effort,
)


class TestSupportedProviders:
    """Test supported providers"""

    def test_supported_providers(self):
        """Test supported providers list"""
        assert "openai" in SUPPORTED_PROVIDERS
        assert "anthropic" in SUPPORTED_PROVIDERS
        assert "xai" in SUPPORTED_PROVIDERS
        assert "perplexity" in SUPPORTED_PROVIDERS
        assert "google" in SUPPORTED_PROVIDERS


class TestResolveModel:
    """Test resolve_model function"""

    def test_resolve_openai_model(self):
        """Test resolving OpenAI model from string"""
        result = resolve_model("gpt-4o")

        assert isinstance(result.model, LitellmModel)
        assert result.model_name == "gpt-4o"
        assert result.is_gpt5 is False
        assert result.is_anthropic is False
        assert result.is_xai is False
        assert result.supports_reasoning is False

    def test_resolve_openai_with_prefix(self):
        """Test resolving OpenAI model with provider prefix"""
        result = resolve_model("openai/gpt-4o")

        assert isinstance(result.model, LitellmModel)
        assert result.model_name == "openai/gpt-4o"

    def test_resolve_gpt5_model(self):
        """Test resolving GPT-5 model detects reasoning support"""
        result = resolve_model("gpt-5")

        assert isinstance(result.model, LitellmModel)
        assert result.is_gpt5 is True
        assert result.supports_reasoning is True

    def test_resolve_gpt5_with_prefix(self):
        """Test resolving GPT-5 with openai prefix"""
        result = resolve_model("openai/gpt-5")

        assert isinstance(result.model, LitellmModel)
        assert result.is_gpt5 is True
        assert result.supports_reasoning is True

    def test_resolve_anthropic_model(self):
        """Test resolving Anthropic model creates LitellmModel with Anthropic-specific settings"""
        with patch(
            "app.services.agent.agent_config.LitellmModel"
        ) as mock_litellm, patch(
            "app.services.agent.agent_config.settings"
        ) as mock_settings:
            mock_settings.anthropic_api_key = "test-key"
            mock_model_instance = MagicMock()
            mock_litellm.return_value = mock_model_instance

            result = resolve_model("anthropic/claude-sonnet-4-5")

            mock_litellm.assert_called_once_with(
                model="anthropic/claude-sonnet-4-5",
                api_key="test-key",
                enable_deferred_tools=True,
                enable_cache_control=True,
                anthropic_beta_headers=["advanced-tool-use-2025-11-20"],
            )
            assert result.model == mock_model_instance
            assert result.is_anthropic is True
            assert result.supports_reasoning is True

    def test_resolve_anthropic_missing_api_key(self):
        """Test resolving Anthropic model without API key raises error"""
        with patch("app.services.agent.agent_config.settings") as mock_settings:
            mock_settings.anthropic_api_key = None

            with pytest.raises(ValueError, match="Anthropic API key not configured"):
                resolve_model("anthropic/claude-sonnet-4-5")

    def test_resolve_xai_model(self):
        """Test resolving xAI model creates LitellmModel"""
        with patch(
            "app.services.agent.agent_config.LitellmModel"
        ) as mock_litellm_model, patch(
            "app.services.agent.agent_config.settings"
        ) as mock_settings:
            mock_settings.xai_api_key = "test-xai-key"
            mock_model_instance = MagicMock()
            mock_litellm_model.return_value = mock_model_instance

            result = resolve_model("xai/grok-2")

            mock_litellm_model.assert_called_once_with(
                model="xai/grok-2", api_key="test-xai-key"
            )
            assert result.model == mock_model_instance
            assert result.is_xai is True
            assert result.supports_reasoning is True

    def test_resolve_xai_missing_api_key(self):
        """Test resolving xAI model without API key raises error"""
        with patch("app.services.agent.agent_config.settings") as mock_settings:
            mock_settings.xai_api_key = None

            with pytest.raises(ValueError, match="xAI API key not configured"):
                resolve_model("xai/grok-2")

    def test_resolve_perplexity_model(self):
        """Test resolving Perplexity model creates OpenAIChatCompletionsModel"""
        with patch(
            "app.services.agent.agent_config.OpenAIChatCompletionsModel"
        ) as mock_openai_model, patch(
            "app.services.agent.agent_config.AsyncOpenAI"
        ) as mock_async_client, patch(
            "app.services.agent.agent_config.settings"
        ) as mock_settings:
            mock_settings.perplexity_api_key = "test-perplexity-key"
            mock_client_instance = MagicMock()
            mock_async_client.return_value = mock_client_instance
            mock_model_instance = MagicMock()
            mock_openai_model.return_value = mock_model_instance

            result = resolve_model("perplexity/sonar-pro")

            mock_async_client.assert_called_once_with(
                api_key="test-perplexity-key",
                base_url="https://api.perplexity.ai",
            )
            mock_openai_model.assert_called_once_with(
                model="sonar-pro", openai_client=mock_client_instance
            )
            assert result.model == mock_model_instance
            assert result.is_perplexity is True
            assert result.supports_tools is False  # Perplexity does NOT support tools

    def test_resolve_perplexity_missing_api_key(self):
        """Test resolving Perplexity model without API key raises error"""
        with patch("app.services.agent.agent_config.settings") as mock_settings:
            mock_settings.perplexity_api_key = None

            with pytest.raises(ValueError, match="Perplexity API key not configured"):
                resolve_model("perplexity/sonar-pro")

    def test_resolve_unsupported_provider(self):
        """Test resolving model with unsupported provider raises error"""
        with pytest.raises(ValueError, match="Provider 'cohere' is not supported"):
            resolve_model("cohere/command-r-plus")

    def test_resolve_case_insensitive_provider(self):
        """Test provider matching is case insensitive"""
        result = resolve_model("OPENAI/gpt-4o")
        assert isinstance(result.model, LitellmModel)


class TestResolvedModel:
    """Test ResolvedModel dataclass"""

    def test_supports_reasoning_gpt5(self):
        """Test supports_reasoning for GPT-5"""
        model = ResolvedModel(
            model="gpt-5",
            model_name="gpt-5",
            is_gpt5=True,
            is_anthropic=False,
            is_xai=False,
            is_google=False,
        )
        assert model.supports_reasoning is True

    def test_supports_reasoning_anthropic(self):
        """Test supports_reasoning for Anthropic"""
        model = ResolvedModel(
            model="mock",
            model_name="anthropic/claude-sonnet-4-5",
            is_gpt5=False,
            is_anthropic=True,
            is_xai=False,
            is_google=False,
        )
        assert model.supports_reasoning is True

    def test_supports_reasoning_xai(self):
        """Test supports_reasoning for xAI"""
        model = ResolvedModel(
            model="mock",
            model_name="xai/grok-2",
            is_gpt5=False,
            is_anthropic=False,
            is_xai=True,
            is_google=False,
        )
        assert model.supports_reasoning is True

    def test_supports_reasoning_regular_openai(self):
        """Test supports_reasoning for regular OpenAI (not GPT-5)"""
        model = ResolvedModel(
            model="gpt-4o",
            model_name="gpt-4o",
            is_gpt5=False,
            is_anthropic=False,
            is_xai=False,
            is_google=False,
        )
        assert model.supports_reasoning is False

    def test_supports_tools_regular_models(self):
        """Test supports_tools is True for regular models"""
        model = ResolvedModel(
            model="gpt-5",
            model_name="gpt-5",
            is_gpt5=True,
            is_anthropic=False,
            is_xai=False,
            is_google=False,
            is_perplexity=False,
        )
        assert model.supports_tools is True

    def test_supports_tools_perplexity(self):
        """Test supports_tools is False for Perplexity"""
        model = ResolvedModel(
            model="mock",
            model_name="perplexity/sonar-pro",
            is_gpt5=False,
            is_anthropic=False,
            is_xai=False,
            is_google=False,
            is_perplexity=True,
        )
        assert model.supports_tools is False


class TestValidateReasoningEffort:
    """Test validate_reasoning_effort function"""

    def test_validate_none_reasoning(self):
        """Test validating None reasoning effort returns None"""
        model = ResolvedModel(
            model="gpt-5",
            model_name="gpt-5",
            is_gpt5=True,
            is_anthropic=False,
            is_xai=False,
            is_google=False,
        )
        result = validate_reasoning_effort(None, model)
        assert result is None

    def test_validate_unsupported_model(self):
        """Test validating reasoning for unsupported model returns None"""
        model = ResolvedModel(
            model="gpt-4o",
            model_name="gpt-4o",
            is_gpt5=False,
            is_anthropic=False,
            is_xai=False,
            is_google=False,
        )
        result = validate_reasoning_effort("high", model)
        assert result is None

    def test_validate_invalid_effort(self):
        """Test validating invalid reasoning effort returns None"""
        model = ResolvedModel(
            model="gpt-5",
            model_name="gpt-5",
            is_gpt5=True,
            is_anthropic=False,
            is_xai=False,
            is_google=False,
        )
        result = validate_reasoning_effort("invalid", model)
        assert result is None

    def test_validate_valid_effort_gpt5(self):
        """Test validating valid reasoning effort for GPT-5"""
        model = ResolvedModel(
            model="gpt-5",
            model_name="gpt-5",
            is_gpt5=True,
            is_anthropic=False,
            is_xai=False,
            is_google=False,
        )
        for effort in ["none", "low", "medium", "high"]:
            result = validate_reasoning_effort(effort, model)
            assert result == effort

    def test_validate_valid_effort_anthropic(self):
        """Test validating valid reasoning effort for Anthropic"""
        model = ResolvedModel(
            model="mock",
            model_name="anthropic/claude-sonnet-4-5",
            is_gpt5=False,
            is_anthropic=True,
            is_xai=False,
            is_google=False,
        )
        result = validate_reasoning_effort("medium", model)
        assert result == "medium"


class TestCreateModelSettings:
    """Test create_model_settings function"""

    def test_create_default_settings(self):
        """Test creating default model settings"""
        settings = create_model_settings()

        assert isinstance(settings, ModelSettings)
        assert settings.store is True
        assert settings.include_usage is True

    def test_create_settings_with_parallel_tools(self):
        """Test creating settings with parallel tool calls"""
        settings = create_model_settings(parallel_tool_calls=True)

        assert settings.parallel_tool_calls is True

    def test_create_settings_with_reasoning(self):
        """Test creating settings with reasoning effort"""
        settings = create_model_settings(reasoning_effort="high")

        assert settings.reasoning is not None
        assert settings.reasoning.effort == "high"
        assert settings.reasoning.summary == "auto"

    def test_create_settings_xai_no_reasoning(self):
        """Test xAI models don't get reasoning config"""
        settings = create_model_settings(
            reasoning_effort="high",
            is_xai_model=True,
        )

        # xAI models should not have reasoning configured
        assert settings.reasoning is None

    def test_create_settings_custom_values(self):
        """Test creating settings with all custom values"""
        settings = create_model_settings(
            parallel_tool_calls=True,
            store=False,
            reasoning_effort="medium",
            reasoning_summary="detailed",
            include_usage=False,
        )

        assert settings.parallel_tool_calls is True
        assert settings.store is False
        assert settings.include_usage is False
        assert settings.reasoning.effort == "medium"
        assert settings.reasoning.summary == "detailed"


class TestCreateContextHooks:
    """Test create_context_hooks function"""

    def test_returns_none_without_session_id(self):
        """Test that None is returned when session_id is None"""
        result = create_context_hooks(
            session_id=None,
            model="gpt-5",
            emit_sse_callback=None,
        )
        assert result is None

    def test_returns_none_with_empty_session_id(self):
        """Test that None is returned when session_id is empty string"""
        result = create_context_hooks(
            session_id="",
            model="gpt-5",
            emit_sse_callback=None,
        )
        assert result is None

    @patch("app.services.context_manager.create_context_manager_hooks")
    def test_creates_hooks_with_session_id(self, mock_create_hooks):
        """Test that hooks are created when session_id is provided"""
        mock_hooks = MagicMock()
        mock_create_hooks.return_value = mock_hooks

        result = create_context_hooks(
            session_id="test-session-123",
            model="gpt-5",
            emit_sse_callback=lambda x, y: None,
        )

        assert result == mock_hooks
        mock_create_hooks.assert_called_once()


class TestBuildRunConfig:
    """Test build_run_config function"""

    def test_returns_none_without_hooks(self):
        """Test that None is returned when hooks is None"""
        result = build_run_config(None)
        assert result is None

    def test_returns_none_without_call_model_input_filter(self):
        """Test that None is returned when hooks don't have call_model_input_filter"""
        mock_hooks = MagicMock(spec=[])  # No attributes
        result = build_run_config(mock_hooks)
        assert result is None

    def test_creates_run_config_with_hooks(self):
        """Test that RunConfig is created with hooks.call_model_input_filter"""
        mock_hooks = MagicMock()
        mock_hooks.call_model_input_filter = MagicMock()

        result = build_run_config(mock_hooks)

        assert result is not None
        assert result.call_model_input_filter == mock_hooks.call_model_input_filter
