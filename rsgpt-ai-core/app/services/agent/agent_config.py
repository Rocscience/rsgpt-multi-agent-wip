"""Agent configuration utilities

This module provides:
- Model resolution and creation for different providers (OpenAI, Anthropic, xAI)
- ModelSettings configuration helpers
- Reasoning effort validation
"""

import logging
from dataclasses import dataclass
from typing import Any, Literal

from agents import ModelSettings, OpenAIChatCompletionsModel
from agents.extensions.models.litellm_model import LitellmModel
from openai import AsyncOpenAI
from openai.types.shared.reasoning import Reasoning

from app.config import settings
from app.services.agent._litellm_patches import apply_litellm_patches

logger = logging.getLogger(__name__)

# Apply runtime patches to LiteLLM. Currently fixes BerriAI/litellm#21331
# (parallel tool call index collision) for GPT-5.x models on the Responses
# API. Idempotent and version-gated — becomes a no-op once we bump
# litellm >= 1.82.0. See app/services/agent/_litellm_patches.py.
apply_litellm_patches()


# =============================================================================
# Type Aliases
# =============================================================================

ReasoningEffort = Literal["minimal", "low", "medium", "high"]

SUPPORTED_PROVIDERS = ["openai", "anthropic", "xai", "perplexity", "google"]


# =============================================================================
# Model Resolution
# =============================================================================


@dataclass
class ResolvedModel:
    """
    Result of resolving a model string.

    Contains the processed model object and metadata needed for configuration.
    """

    # LitellmModel for OpenAI/Anthropic, OpenAIChatCompletionsModel for xAI/Perplexity
    model: Any
    model_name: str  # Original model name for logging/hooks
    is_gpt5: bool
    is_anthropic: bool
    is_xai: bool
    is_google: bool
    is_perplexity: bool = False

    @property
    def supports_reasoning(self) -> bool:
        """Whether this model supports reasoning effort configuration"""
        return self.is_gpt5 or self.is_anthropic or self.is_xai or self.is_google

    @property
    def supports_tools(self) -> bool:
        """Whether this model supports tool calling"""
        # Perplexity does NOT support tool calling
        return not self.is_perplexity

    @property
    def supports_parallel_tool_calls(self) -> bool:
        """Whether this model supports parallel tool calls"""
        return not self.is_xai


def resolve_model(model_name: str) -> ResolvedModel:
    """
    Resolve a model string to a processed model with metadata.

    Handles:
    - Provider detection (OpenAI, Anthropic, xAI, Perplexity)
    - Model object creation with appropriate API clients
    - Metadata extraction for downstream configuration

    Args:
        model_name: Model identifier (e.g., "gpt-5", "anthropic/claude-sonnet-4-5")

    Returns:
        ResolvedModel with processed model and metadata

    Raises:
        ValueError: If provider is not supported or API key is missing
    """
    # Detect provider from model name
    is_gpt5 = model_name.startswith("gpt-5") or model_name.startswith("openai/gpt-5")
    is_anthropic = model_name.startswith("anthropic/")
    is_xai = model_name.startswith("xai/")
    is_google = model_name.startswith("google/")
    is_perplexity = model_name.startswith("perplexity/")

    # Create the appropriate model object
    processed_model = _create_model(model_name)

    return ResolvedModel(
        model=processed_model,
        model_name=model_name,
        is_gpt5=is_gpt5,
        is_anthropic=is_anthropic,
        is_xai=is_xai,
        is_google=is_google,
        is_perplexity=is_perplexity,
    )


def _create_model(model_name: str) -> Any:
    """
    Create the appropriate model object for the Agent SDK.

    All models use LiteLLM for consistent Chat Completions format, which
    enables seamless model switching within a single conversation.

    Args:
        model_name: Model identifier (e.g., "gpt-5", "anthropic/claude-sonnet-4-5")

    Returns:
        LitellmModel for all providers (ensures cross-model compatibility)

    Raises:
        ValueError: If provider is not supported or API key is missing
    """
    # Check if this is a provider/model format (contains "/")
    if "/" in model_name:
        provider = model_name.split("/")[0].lower()

        if provider not in SUPPORTED_PROVIDERS:
            raise ValueError(
                f"Provider '{provider}' is not supported. "
                f"Supported providers: {', '.join(SUPPORTED_PROVIDERS)}"
            )

        # OpenAI with prefix - use LiteLLM for consistency
        if provider == "openai":
            return _create_openai_model(model_name)

        # Anthropic - use LiteLLM
        if provider == "anthropic":
            return _create_anthropic_model(model_name)

        # xAI - use OpenAI client with xAI base URL
        if provider == "xai":
            return _create_xai_model(model_name)

        # Google - use LiteLLM with gemini/ prefix
        if provider == "google":
            return _create_google_model(model_name)

        # Perplexity - use OpenAI client with Perplexity base URL (NO TOOLS)
        if provider == "perplexity":
            return _create_perplexity_model(model_name)

    # No prefix = OpenAI, use LiteLLM for cross-model compatibility
    return _create_openai_model(model_name)


def _create_openai_model(model_name: str) -> LitellmModel:
    """
    Create a LitellmModel for OpenAI.

    Using LiteLLM instead of the native Responses API ensures consistent
    Chat Completions format across all providers, enabling seamless
    model switching within conversations.
    """
    api_key = settings.openai_api_key
    if not api_key:
        raise ValueError(
            "OpenAI API key not configured. Set OPENAI_API_KEY in environment."
        )

    # Strip provider prefix if present (e.g., "openai/gpt-5" -> "gpt-5")
    if "/" in model_name:
        base_model = model_name.split("/")[-1]
    else:
        base_model = model_name

    # Route OpenAI through the Responses API (via LiteLLM) so we can receive
    # reasoning_content/summaries from GPT-5.x models. Note: LiteLLM versions
    # below 1.82.0 contain a bug (BerriAI/litellm#21331) where the Responses
    # → ChatCompletions streaming bridge hardcodes index=0 for all parallel
    # tool call chunks, causing parallel calls to be merged into one
    # tool_call with concatenated JSON arguments. We patch around it at
    # runtime in app/services/agent/_litellm_patches.py until we bump
    # the LiteLLM dependency past 1.82.0.
    litellm_model = f"openai/responses/{base_model}"

    logger.info(f"Creating LiteLLM model for OpenAI: {litellm_model}")
    return LitellmModel(model=litellm_model, api_key=api_key)


def _create_anthropic_model(model_name: str) -> LitellmModel:
    """Create a LitellmModel for Anthropic."""
    api_key = settings.anthropic_api_key
    if not api_key:
        raise ValueError(
            "Anthropic API key not configured. Set ANTHROPIC_API_KEY in environment."
        )

    anthropic_beta_headers = ["advanced-tool-use-2025-11-20"]


    logger.info(f"Creating LiteLLM model for: {model_name}")
    return LitellmModel(
        model=model_name,
        api_key=api_key,
        enable_deferred_tools=True,
        enable_cache_control=True,
        anthropic_beta_headers=anthropic_beta_headers,
    )


def _create_xai_model(model_name: str) -> LitellmModel:
    """Create a LiteLLM model for xAI."""
    api_key = settings.xai_api_key
    if not api_key:
        raise ValueError("xAI API key not configured. Set XAI_API_KEY in environment.")

    logger.info(f"Creating LiteLLM model for xAI: {model_name}")

    return LitellmModel(model=model_name, api_key=api_key)


def _create_google_model(model_name: str) -> LitellmModel:
    """Create a LitellmModel for Google Gemini."""
    import os

    api_key = settings.google_api_key
    if not api_key:
        raise ValueError(
            "Google API key not configured. Set GOOGLE_API_KEY in environment."
        )

    # LiteLLM reads GEMINI_API_KEY env var for Google AI Studio routing.
    # Without this, it may fall back to Vertex AI (which requires GCP credentials).
    os.environ["GEMINI_API_KEY"] = api_key

    # Convert "google/gemini-3-flash-preview" -> "gemini/gemini-3-flash-preview"
    # LiteLLM uses the "gemini/" prefix for Google AI Studio models
    base_model = model_name.split("/", 1)[-1] if "/" in model_name else model_name
    litellm_model = f"gemini/{base_model}"

    logger.info(f"Creating LiteLLM model for Google: {litellm_model}")
    # Disable explicit cache_control for Gemini: LiteLLM v1.80+ has built-in
    # Gemini context caching that conflicts with our SDK markers, and Gemini 2.5+
    # has implicit caching (automatic server-side) that works without any markers.
    # Setting enable_cache_control=False prevents both our SDK markers AND
    # LiteLLM's context caching pipeline from triggering.
    return LitellmModel(model=litellm_model, api_key=api_key, enable_cache_control=False)


def _create_perplexity_model(model_name: str) -> OpenAIChatCompletionsModel:
    """
    Create an OpenAI-compatible model for Perplexity.

    NOTE: Perplexity does NOT support tool calling. The agent will run
    without tools when using a Perplexity model.
    """
    api_key = settings.perplexity_api_key
    if not api_key:
        raise ValueError(
            "Perplexity API key not configured. Set PERPLEXITY_API_KEY in environment."
        )

    logger.info(f"Creating OpenAI client model for Perplexity: {model_name}")
    logger.warning(
        "Perplexity models do NOT support tool calling - agent will run without tools"
    )

    perplexity_client = AsyncOpenAI(
        api_key=api_key,
        base_url="https://api.perplexity.ai",
    )

    # Strip provider prefix (e.g., "perplexity/sonar-pro" -> "sonar-pro")
    perplexity_model_name = (
        model_name.split("/", 1)[-1] if "/" in model_name else model_name
    )

    return OpenAIChatCompletionsModel(
        model=perplexity_model_name, openai_client=perplexity_client
    )


# =============================================================================
# Model Name Extraction
# =============================================================================


def get_model_name_for_hooks(resolved_model: ResolvedModel) -> str:
    """
    Extract the model name string for use in hooks/logging.

    Args:
        resolved_model: The resolved model from resolve_model()

    Returns:
        Model name string suitable for hooks
    """
    model = resolved_model.model

    if isinstance(model, str):
        return model
    elif hasattr(model, "model"):
        # OpenAIChatCompletionsModel and LitellmModel have 'model' attribute
        return model.model
    else:
        return getattr(model, "model_name", str(model))


# =============================================================================
# Reasoning Effort
# =============================================================================


def validate_reasoning_effort(
    reasoning_effort: str | None,
    resolved_model: ResolvedModel,
) -> ReasoningEffort | None:
    """
    Validate and return reasoning effort if supported by the model.

    Args:
        reasoning_effort: Requested reasoning effort level
        resolved_model: The resolved model to check support

    Returns:
        Validated reasoning effort or None if not supported/invalid
    """
    if not reasoning_effort:
        return None

    if not resolved_model.supports_reasoning:
        logger.info(
            f"Model '{resolved_model.model_name}' does not support reasoning effort"
        )
        return None

    valid_efforts: set[str] = {"none", "low", "medium", "high"}
    if reasoning_effort not in valid_efforts:
        logger.warning(
            f"Invalid reasoning effort '{reasoning_effort}', must be one of {valid_efforts}"
        )
        return None

    # Log Anthropic-specific info
    if resolved_model.is_anthropic:
        budget_map = {"low": 1024, "medium": 2048, "high": 4096}
        budget = budget_map.get(reasoning_effort, 2048)
        logger.info(
            f"Using reasoning effort '{reasoning_effort}' "
            f"(thinking budget: {budget} tokens) for Anthropic model"
        )
    else:
        logger.info(
            f"Using reasoning effort '{reasoning_effort}' for {resolved_model.model_name}"
        )

    return reasoning_effort  # type: ignore[return-value]


# =============================================================================
# Model Settings
# =============================================================================


def create_model_settings(
    parallel_tool_calls: bool = False,
    store: bool = True,
    reasoning_effort: ReasoningEffort | None = None,
    reasoning_summary: Literal["auto", "concise", "detailed"] = "auto",
    include_usage: bool = True,
    is_xai_model: bool = False,
    is_anthropic_model: bool = False,
    is_google_model: bool = False,
) -> ModelSettings:
    """
    Create standardized ModelSettings for agents.

    Args:
        parallel_tool_calls: Whether agent can make parallel tool calls
        store: Whether to store the conversation for tracing
        reasoning_effort: Reasoning effort level ("low", "medium", "high")
                         - For GPT-5: SDK passes dict {effort, summary} to get reasoning_content
                         - For Anthropic: SDK passes just effort (LiteLLM translates to thinking)
                         - For Google: SDK passes effort (LiteLLM translates to thinking_level)
                         - For xAI: Not supported (reasoning built into model)
        reasoning_summary: Reasoning summary mode ("auto", "concise", "detailed") - GPT-5 only
        include_usage: Whether to include usage metrics (token counts)
        is_xai_model: Whether this is an xAI model
        is_anthropic_model: Whether this is an Anthropic model
        is_google_model: Whether this is a Google Gemini model

    Returns:
        Configured ModelSettings instance
    """
    settings_dict: dict[str, Any] = {
        "store": store,
        "include_usage": include_usage,
    }

    # Only include parallel_tool_calls if explicitly enabled
    if parallel_tool_calls:
        settings_dict["parallel_tool_calls"] = parallel_tool_calls

    # Handle reasoning based on provider
    if reasoning_effort is not None:
        if is_xai_model:
            # xAI reasoning models have reasoning built-in, no config needed
            pass
        elif is_anthropic_model:
            # Anthropic: only pass effort (no summary) - LiteLLM translates to thinking budget
            settings_dict["reasoning"] = Reasoning(effort=reasoning_effort)
            logger.info(f"Anthropic: using Reasoning(effort='{reasoning_effort}')")
        elif is_google_model:
            # Google: only pass effort - LiteLLM translates to thinking_level
            settings_dict["reasoning"] = Reasoning(effort=reasoning_effort)
            logger.info(f"Google: using Reasoning(effort='{reasoning_effort}')")
        else:
            # GPT-5/OpenAI: pass both effort + summary to get reasoning_content
            settings_dict["reasoning"] = Reasoning(
                effort=reasoning_effort,
                summary=reasoning_summary,
            )
            logger.info(
                f"OpenAI: using Reasoning(effort='{reasoning_effort}', \
                summary='{reasoning_summary}')"
            )

    return ModelSettings(**settings_dict)  # type: ignore[arg-type]


# =============================================================================
# Context Hooks & RunConfig
# =============================================================================


def create_context_hooks(
    session_id: str | None,
    model: str,
    session=None,
    emit_sse_callback=None,
    initial_token_count: int = 0,
):
    """
    Create context manager hooks for an agent run.

    Args:
        session_id: Session ID for the chat session (None = no hooks)
        model: Model name for token counting
        session: SDK session for persisting pruned history (optional)
        emit_sse_callback: Callback to emit SSE events
        initial_token_count: Initial token count (can be loaded from DB)

    Returns:
        ContextManagerHooks instance or None if session_id not provided
    """
    from app.services.context_manager import create_context_manager_hooks

    if not session_id:
        logger.info("No session_id provided - context hooks not created")
        return None

    # Resolve model to get the actual model name for token counting
    resolved = resolve_model(model)
    model_name = get_model_name_for_hooks(resolved)

    hooks = create_context_manager_hooks(
        session_id=session_id,
        session=session,
        model_name=model_name,
        emit_sse_callback=emit_sse_callback,
        initial_token_count=initial_token_count,
    )

    logger.info(
        f"Created context hooks for session {session_id} with model {model_name}"
        + (" (session attached)" if session else "")
    )
    return hooks


def build_run_config(hooks):
    """
    Build RunConfig with call_model_input_filter for context management.

    Args:
        hooks: ContextManagerHooks instance (or None)

    Returns:
        RunConfig with call_model_input_filter, or None if no hooks
    """
    from agents.run import RunConfig

    if not hooks:
        return None

    if not hasattr(hooks, "call_model_input_filter"):
        logger.warning("Hooks don't have call_model_input_filter")
        return None

    run_config = RunConfig(call_model_input_filter=hooks.call_model_input_filter)
    logger.info("✓ Built RunConfig with call_model_input_filter")
    return run_config
