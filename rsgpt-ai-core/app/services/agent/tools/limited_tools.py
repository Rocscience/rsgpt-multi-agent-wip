"""Tool wrappers with usage limits for ask mode.

This module provides wrapped versions of base tools that:
1. Track usage counts in AgentContext
2. Use is_enabled callback to disable tools when limits are reached

This prevents the LLM from exceeding max_turns by limiting tool calls.
"""

import logging
from typing import Any, List, Optional

from agents import FunctionTool, RunContextWrapper
from agents.agent import AgentBase

from app.models.agent import AgentContext
from app.services.agent.tools.base_tools import search_knowledge, search_web

logger = logging.getLogger(__name__)

# Ask mode tool limits (per response, not cumulative)
ASK_MODE_LIMITS = {
    "search_knowledge": 8,  # Max knowledge base searches per response
    "search_web": 7,  # Max web searches per response
}


def _check_tool_enabled(
    ctx: RunContextWrapper[AgentContext], agent: AgentBase, tool_name: str
) -> bool:
    """
    Check if a tool is still enabled based on usage limits.

    Args:
        ctx: Run context containing AgentContext
        agent: The agent (unused but required by is_enabled signature)
        tool_name: Name of the tool to check

    Returns:
        True if tool is under its usage limit, False otherwise
    """
    context = ctx.context
    if context is None:
        return True

    is_enabled = context.is_tool_enabled(tool_name)

    if not is_enabled:
        logger.info(
            f"Tool '{tool_name}' disabled - {context.get_tool_usage_status(tool_name)}"
        )

    return is_enabled


def _wrap_tool_with_tracking(
    original_tool: FunctionTool, tool_name: str
) -> FunctionTool:
    """
    Wrap a FunctionTool to track usage and enforce limits.

    Args:
        original_tool: The original FunctionTool to wrap
        tool_name: Name of the tool for tracking

    Returns:
        New FunctionTool with usage tracking and is_enabled callback
    """
    original_invoke = original_tool.on_invoke_tool

    async def tracked_invoke(ctx: RunContextWrapper[AgentContext], args: str) -> Any:
        """Invoke the tool and track usage."""
        context = ctx.context
        if context is not None:
            context.increment_tool_usage(tool_name)
            logger.info(
                f"Tool '{tool_name}' called - {context.get_tool_usage_status(tool_name)}"
            )

        return await original_invoke(ctx, args)  # type: ignore[arg-type]

    def is_enabled_callback(
        ctx: RunContextWrapper[AgentContext], agent: AgentBase
    ) -> bool:
        return _check_tool_enabled(ctx, agent, tool_name)

    return FunctionTool(
        name=original_tool.name,
        description=original_tool.description,
        params_json_schema=original_tool.params_json_schema,
        on_invoke_tool=tracked_invoke,
        strict_json_schema=original_tool.strict_json_schema,
        is_enabled=is_enabled_callback,
    )


def create_limited_tools(limits: Optional[dict] = None) -> List[FunctionTool]:
    """
    Create base tools with usage limits for ask mode.

    Args:
        limits: Optional dict of tool_name -> max_calls.
                Defaults to ASK_MODE_LIMITS if not provided.

    Returns:
        List of FunctionTools with is_enabled callbacks for limit enforcement
    """
    if limits is None:
        limits = ASK_MODE_LIMITS

    logger.info(f"Creating limited tools with limits: {limits}")

    # The @function_tool decorator creates FunctionTool instances
    # We need to wrap them with tracking
    limited_tools = []

    # Wrap search_knowledge
    if "search_knowledge" in limits or limits is ASK_MODE_LIMITS:
        wrapped_knowledge = _wrap_tool_with_tracking(
            search_knowledge, "search_knowledge"
        )
        limited_tools.append(wrapped_knowledge)
        logger.info(
            f"✓ search_knowledge wrapped with limit: {limits.get('search_knowledge', 'unlimited')}"
        )

    # Wrap search_web
    if "search_web" in limits or limits is ASK_MODE_LIMITS:
        wrapped_web = _wrap_tool_with_tracking(search_web, "search_web")
        limited_tools.append(wrapped_web)
        logger.info(
            f"✓ search_web wrapped with limit: {limits.get('search_web', 'unlimited')}"
        )

    return limited_tools


def get_ask_mode_tool_limits() -> dict:
    """Get the default tool limits for ask mode."""
    return ASK_MODE_LIMITS.copy()
