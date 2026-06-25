"""Main RSInsight Agent - handles all workflows in one agent"""

import logging
from typing import Any, List

from agents import Agent, AgentHooks

from app.models.agent import AgentContext, AgentMode
from app.services.agent.agent_config import (
    create_model_settings,
    resolve_model,
    validate_reasoning_effort,
)
from app.services.agent.instructions import (
    ASK_MODE_INSTRUCTIONS,
    MAIN_AGENT_INSTRUCTIONS,
    build_instructions,
)

logger = logging.getLogger(__name__)

# Mode-specific configuration
MODE_CONFIG = {
    AgentMode.ASK: {
        "name": "RSInsight Ask",
        "instructions": ASK_MODE_INSTRUCTIONS,
        "max_turns": 15,
        "parallel_tool_calls": True,
    },
    AgentMode.AGENT: {
        "name": "RSInsight Agent",
        "instructions": MAIN_AGENT_INSTRUCTIONS,
        "max_turns": 150,
        "parallel_tool_calls": True,
    },
}


def get_mode_config(mode: AgentMode) -> dict:
    """Get configuration for the specified mode."""
    return MODE_CONFIG.get(mode, MODE_CONFIG[AgentMode.AGENT])


def create_main_agent(
    model: str,
    tools: List[Any],
    mode: AgentMode = AgentMode.AGENT,
    mcp_servers: List[Any] | None = None,
    reasoning_effort: str | None = None,
    hooks: AgentHooks[AgentContext] | None = None,
    agent_context: AgentContext | None = None,
) -> Agent[AgentContext]:
    """
    Create the RSInsight agent configured for the specified mode.

    Uses SDK types directly - no wrapper abstractions.

    Args:
        model: Model name (e.g., "gpt-5", "anthropic/claude-sonnet-4-5", "perplexity/sonar-pro")
        tools: Tools to provide (base only for ask mode, all for agent mode)
        mode: Agent operation mode (ask or agent)
        mcp_servers: Optional list of MCP servers (e.g., RSLog MCP)
        reasoning_effort: Optional reasoning effort ("low", "medium", "high")
        hooks: Optional AgentHooks for context management (created externally)
        agent_context: Optional agent context with device connection status

    Returns:
        Agent[AgentContext] configured for the specified mode

    Note:
        Perplexity models do NOT support tool calling - tools will be disabled.
    """
    config = get_mode_config(mode)

    # Resolve model and get metadata
    resolved = resolve_model(model)

    # Validate reasoning effort for this model
    validated_reasoning = validate_reasoning_effort(reasoning_effort, resolved)

    # Handle models that don't support tools (e.g., Perplexity)
    effective_tools = tools if resolved.supports_tools else []
    effective_mcp_servers = mcp_servers if resolved.supports_tools else []

    if not resolved.supports_tools:
        logger.warning(
            f"Model '{model}' does not support tools - running without tools"
        )

    logger.info(
        f"Creating {config['name']} with model '{model}', {len(effective_tools)} tools, "
        f"mode={mode.value}, max_turns={config['max_turns']}"
    )

    # Log tool names for debugging (only if tools are enabled)
    if effective_tools:
        tool_names = [
            getattr(t, "name", getattr(t, "__name__", str(t))) for t in effective_tools
        ]
        logger.info(f"Available tools: {', '.join(tool_names)}")

    # Build instructions with context injection and mode-specific customization
    # For ASK mode: injects tool limits dynamically
    # For AGENT mode: injects device status and model-specific guidance
    base_instructions = config["instructions"]
    instructions = build_instructions(
        base_instructions, agent_context, mode=mode, model_name=model
    )

    if hooks:
        logger.info("Agent created with context manager hooks")

    # Create agent using SDK types directly
    return Agent[AgentContext](
        name=config["name"],
        instructions=instructions,
        tools=effective_tools,
        model=resolved.model,
        model_settings=create_model_settings(
            parallel_tool_calls=config["parallel_tool_calls"]
            and resolved.supports_tools
            and resolved.supports_parallel_tool_calls,
            reasoning_effort=validated_reasoning,
            is_xai_model=resolved.is_xai,
            is_anthropic_model=resolved.is_anthropic,
            is_google_model=resolved.is_google,
            include_usage=True,
        ),
        hooks=hooks,
        mcp_servers=effective_mcp_servers or [],
    )
