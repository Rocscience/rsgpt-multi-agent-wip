"""Tool initialization for agent workflows

Consolidates all tool initialization logic into a single class
to avoid redundant API calls and simplify the orchestration service.
"""

import logging
from dataclasses import dataclass
from typing import Any, Callable, List, Optional

from agents import Agent

from app.models.agent import AgentContext, AgentMode
from app.services.agent.tools.base_tools import search_knowledge, search_web
from app.services.agent.tools.device_tools import parse_device_tools_to_functions
from app.services.agent.tools.limited_tools import (
    create_limited_tools,
    get_ask_mode_tool_limits,
)
from app.services.streaming import connection_manager

logger = logging.getLogger(__name__)


@dataclass
class DeviceToolsResult:
    """Result of device tool initialization"""

    tools: List[Any]
    device_connected: bool = False


class ToolInitializer:
    """
    Consolidates tool initialization for agent workflows.

    Handles:
    - Base tools (always available, unlimited in agent mode)
    - Limited tools (ask mode with usage limits)
    - Device tools (if device connected, agent mode only)

    Note: MCP server support is currently disabled.
    """

    BASE_TOOLS = [search_knowledge, search_web]

    def get_base_tools(self) -> List[Any]:
        """
        Get base tools (always available, unlimited).

        Returns:
            List of base tools (search_knowledge, search_web)
        """
        logger.info("✓ Base tools ready (search_knowledge, search_web)")
        return list(self.BASE_TOOLS)

    def get_tools_for_mode(
        self,
        mode: AgentMode,
        agent_context: Optional[AgentContext] = None,
    ) -> List[Any]:
        """
        Get tools appropriate for the agent mode.

        For ASK mode:
        - Returns limited tools with usage tracking via is_enabled callbacks
        - Sets tool limits in agent_context for tracking
        - Limits: search_knowledge=4, search_web=3

        For AGENT mode:
        - Returns unlimited base tools
        - Device tools are added separately via add_device_tools_to_agent

        Args:
            mode: The agent operation mode (ASK or AGENT)
            agent_context: Optional context for setting tool limits

        Returns:
            List of tools appropriate for the mode
        """
        if mode == AgentMode.ASK:
            # Set tool limits in context for tracking
            if agent_context is not None:
                agent_context.tool_limits = get_ask_mode_tool_limits()
                logger.info(
                    f"✓ Ask mode tools ready with limits: {agent_context.tool_limits}"
                )
            else:
                logger.info(
                    "✓ Ask mode tools ready with limits (no context for tracking)"
                )

            return create_limited_tools()

        # Agent mode - unlimited base tools
        logger.info("✓ Agent mode base tools ready (unlimited)")
        return self.get_base_tools()

    async def initialize_device_tools(
        self,
        device_id: str,
        agent: Agent,
        update_callback: Optional[Callable] = None,
    ) -> DeviceToolsResult:
        """
        Initialize device tools with agent reference (single fetch).

        Args:
            device_id: The device identifier
            agent: The agent (for dynamic tool updates)
            update_callback: Callback for tool updates

        Returns:
            DeviceToolsResult with tools and connection status
        """
        if not connection_manager.is_device_connected(device_id):
            logger.warning(f"Device '{device_id}' requested but not connected")
            return DeviceToolsResult(tools=[], device_connected=False)

        try:
            logger.info(f"Loading tools for device {device_id}...")
            tools_response = await connection_manager.request_list_tools(
                device_id, timeout=30.0
            )

            if tools_response.get("error"):
                logger.error(
                    f"Error fetching device tools: {tools_response.get('error')}"
                )
                return DeviceToolsResult(tools=[], device_connected=True)

            json_tools = tools_response.get("tools", [])
            logger.info(f"Fetched {len(json_tools)} tools from device {device_id}")

            # Parse device tools WITH agent reference
            device_tools = parse_device_tools_to_functions(
                device_id=device_id,
                json_tools=json_tools,
                agent_ref=agent,
                update_callback=update_callback,
            )

            logger.info(
                f"✓ Added {len(device_tools)} device tools for '{device_id}' "
                f"with dynamic update capability"
            )
            return DeviceToolsResult(tools=device_tools, device_connected=True)

        except Exception as e:
            logger.error(f"Failed to load device tools: {e}", exc_info=True)
            return DeviceToolsResult(tools=[], device_connected=True)

    async def add_device_tools_to_agent(
        self,
        agent: Agent,
        device_id: str,
        update_callback: Optional[Callable] = None,
    ) -> DeviceToolsResult:
        """
        Initialize and add device tools to an existing agent (single API call).

        This is the main method to use after creating an agent with base tools.

        Args:
            agent: The agent to add tools to
            device_id: The device identifier
            update_callback: Callback for tool updates

        Returns:
            DeviceToolsResult with tools and connection status
        """
        result = await self.initialize_device_tools(
            device_id=device_id,
            agent=agent,
            update_callback=update_callback,
        )

        if result.tools:
            agent.tools = list(agent.tools) + result.tools
            logger.info(
                f"✓ Agent now has {len(agent.tools)} total tools "
                f"({len(result.tools)} device tools added)"
            )

        return result


# Singleton instance
tool_initializer = ToolInitializer()
