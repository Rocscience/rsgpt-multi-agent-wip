"""Tests for limited tools functionality in ask mode."""

from unittest.mock import MagicMock, patch

import pytest

from app.models.agent import AgentContext, AgentMode
from app.models.channels import UserPermission
from app.services.agent.tools.limited_tools import (
    ASK_MODE_LIMITS,
    _check_tool_enabled,
    _wrap_tool_with_tracking,
    create_limited_tools,
    get_ask_mode_tool_limits,
)
from app.services.agent.tools.tool_initializer import tool_initializer


class TestAgentContextToolTracking:
    """Test tool usage tracking in AgentContext."""

    def test_increment_tool_usage_from_zero(self):
        """Test incrementing tool usage from zero."""
        context = AgentContext()
        count = context.increment_tool_usage("search_knowledge")
        assert count == 1
        assert context.tool_usage["search_knowledge"] == 1

    def test_increment_tool_usage_multiple_times(self):
        """Test incrementing tool usage multiple times."""
        context = AgentContext()
        context.increment_tool_usage("search_web")
        context.increment_tool_usage("search_web")
        count = context.increment_tool_usage("search_web")
        assert count == 3
        assert context.tool_usage["search_web"] == 3

    def test_increment_different_tools(self):
        """Test incrementing different tools independently."""
        context = AgentContext()
        context.increment_tool_usage("search_knowledge")
        context.increment_tool_usage("search_knowledge")
        context.increment_tool_usage("search_web")

        assert context.tool_usage["search_knowledge"] == 2
        assert context.tool_usage["search_web"] == 1

    def test_is_tool_enabled_under_limit(self):
        """Test tool is enabled when under limit."""
        context = AgentContext()
        context.tool_limits = {"search_knowledge": 4}
        context.tool_usage = {"search_knowledge": 2}

        assert context.is_tool_enabled("search_knowledge") is True

    def test_is_tool_enabled_at_limit(self):
        """Test tool is disabled when at limit."""
        context = AgentContext()
        context.tool_limits = {"search_knowledge": 4}
        context.tool_usage = {"search_knowledge": 4}

        assert context.is_tool_enabled("search_knowledge") is False

    def test_is_tool_enabled_over_limit(self):
        """Test tool is disabled when over limit."""
        context = AgentContext()
        context.tool_limits = {"search_knowledge": 4}
        context.tool_usage = {"search_knowledge": 5}

        assert context.is_tool_enabled("search_knowledge") is False

    def test_is_tool_enabled_no_limit_set(self):
        """Test tool is enabled when no limit is set."""
        context = AgentContext()
        context.tool_limits = {}
        context.tool_usage = {"search_knowledge": 100}

        assert context.is_tool_enabled("search_knowledge") is True

    def test_is_tool_enabled_no_usage_yet(self):
        """Test tool is enabled when not used yet."""
        context = AgentContext()
        context.tool_limits = {"search_knowledge": 4}

        assert context.is_tool_enabled("search_knowledge") is True

    def test_get_tool_usage_status_with_limit(self):
        """Test getting tool usage status with limit."""
        context = AgentContext()
        context.tool_limits = {"search_knowledge": 4}
        context.tool_usage = {"search_knowledge": 2}

        status = context.get_tool_usage_status("search_knowledge")
        assert status == "search_knowledge: 2/4 calls"

    def test_get_tool_usage_status_unlimited(self):
        """Test getting tool usage status without limit."""
        context = AgentContext()
        context.tool_usage = {"search_knowledge": 5}

        status = context.get_tool_usage_status("search_knowledge")
        assert status == "search_knowledge: 5 calls (unlimited)"


class TestAskModeLimits:
    """Test ask mode tool limits."""

    def test_default_limits(self):
        """Test default ask mode limits."""
        assert ASK_MODE_LIMITS["search_knowledge"] == 8
        assert ASK_MODE_LIMITS["search_web"] == 7

    def test_get_ask_mode_tool_limits_returns_copy(self):
        """Test that get_ask_mode_tool_limits returns a copy."""
        limits1 = get_ask_mode_tool_limits()
        limits2 = get_ask_mode_tool_limits()

        # Modify one copy
        limits1["search_knowledge"] = 100

        # Other copy should be unchanged
        assert limits2["search_knowledge"] == 8


class TestCreateLimitedTools:
    """Test creating limited tools."""

    def test_create_limited_tools_returns_two_tools(self):
        """Test that create_limited_tools returns search_knowledge and search_web."""
        tools = create_limited_tools()
        assert len(tools) == 2

        tool_names = [tool.name for tool in tools]
        assert "search_knowledge" in tool_names
        assert "search_web" in tool_names

    def test_limited_tools_have_is_enabled_callback(self):
        """Test that limited tools have is_enabled callbacks."""
        tools = create_limited_tools()

        for tool in tools:
            # is_enabled should be a callable, not a bool
            assert callable(tool.is_enabled)


class TestCheckToolEnabled:
    """Test _check_tool_enabled function."""

    def test_check_tool_enabled_returns_true_under_limit(self):
        """Test returns True when under limit."""
        context = AgentContext()
        context.tool_limits = {"search_knowledge": 4}
        context.tool_usage = {"search_knowledge": 2}

        mock_ctx = MagicMock()
        mock_ctx.context = context
        mock_agent = MagicMock()

        result = _check_tool_enabled(mock_ctx, mock_agent, "search_knowledge")
        assert result is True

    def test_check_tool_enabled_returns_false_at_limit(self):
        """Test returns False when at limit."""
        context = AgentContext()
        context.tool_limits = {"search_knowledge": 4}
        context.tool_usage = {"search_knowledge": 4}

        mock_ctx = MagicMock()
        mock_ctx.context = context
        mock_agent = MagicMock()

        result = _check_tool_enabled(mock_ctx, mock_agent, "search_knowledge")
        assert result is False

    def test_check_tool_enabled_returns_true_with_none_context(self):
        """Test returns True when context is None."""
        mock_ctx = MagicMock()
        mock_ctx.context = None
        mock_agent = MagicMock()

        result = _check_tool_enabled(mock_ctx, mock_agent, "search_knowledge")
        assert result is True


class TestToolInitializerModes:
    """Test ToolInitializer.get_tools_for_mode."""

    def test_get_tools_for_ask_mode_returns_limited_tools(self):
        """Test ask mode returns limited tools."""
        context = AgentContext()
        tools = tool_initializer.get_tools_for_mode(AgentMode.ASK, context)

        assert len(tools) == 2
        # Check that limits were set in context
        assert context.tool_limits == get_ask_mode_tool_limits()

    def test_get_tools_for_agent_mode_returns_unlimited_tools(self):
        """Test agent mode returns unlimited base tools."""
        context = AgentContext()
        tools = tool_initializer.get_tools_for_mode(AgentMode.AGENT, context)

        assert len(tools) == 2
        # Context should not have limits set (or empty)
        assert context.tool_limits == {} or context.tool_limits is None

    def test_get_tools_for_ask_mode_without_context(self):
        """Test ask mode works without context."""
        tools = tool_initializer.get_tools_for_mode(AgentMode.ASK, None)
        assert len(tools) == 2

    def test_ask_mode_tools_have_different_is_enabled_than_agent(self):
        """Test ask mode tools have is_enabled callbacks, agent mode doesn't."""
        ask_tools = tool_initializer.get_tools_for_mode(AgentMode.ASK)
        agent_tools = tool_initializer.get_tools_for_mode(AgentMode.AGENT)

        # Ask mode tools should have callable is_enabled
        for tool in ask_tools:
            assert callable(tool.is_enabled)

        # Agent mode tools should have is_enabled as True (default)
        for tool in agent_tools:
            assert tool.is_enabled is True or (
                callable(tool.is_enabled) and tool.is_enabled is True
            )


class TestWrapToolWithTracking:
    """Test _wrap_tool_with_tracking function."""

    def test_wrapped_tool_preserves_name(self):
        """Test wrapped tool preserves original name."""
        # Import the original tool
        from app.services.agent.tools.base_tools import search_knowledge

        wrapped = _wrap_tool_with_tracking(search_knowledge, "search_knowledge")
        assert wrapped.name == "search_knowledge"

    def test_wrapped_tool_preserves_description(self):
        """Test wrapped tool preserves original description."""
        from app.services.agent.tools.base_tools import search_knowledge

        wrapped = _wrap_tool_with_tracking(search_knowledge, "search_knowledge")
        assert wrapped.description == search_knowledge.description

    def test_wrapped_tool_has_is_enabled_callback(self):
        """Test wrapped tool has is_enabled callback."""
        from app.services.agent.tools.base_tools import search_web

        wrapped = _wrap_tool_with_tracking(search_web, "search_web")
        assert callable(wrapped.is_enabled)


class TestIntegration:
    """Integration tests for limited tools."""

    @pytest.mark.asyncio
    async def test_tool_disabled_after_reaching_limit(self):
        """Test that tool is_enabled returns False after reaching limit."""
        context = AgentContext()
        context.tool_limits = {"search_knowledge": 2}

        tools = create_limited_tools(limits={"search_knowledge": 2, "search_web": 1})
        search_knowledge_tool = next(t for t in tools if t.name == "search_knowledge")

        mock_ctx = MagicMock()
        mock_ctx.context = context
        mock_agent = MagicMock()

        # First call - should be enabled
        context.tool_usage = {"search_knowledge": 0}
        assert search_knowledge_tool.is_enabled(mock_ctx, mock_agent) is True

        # Simulate reaching limit
        context.tool_usage = {"search_knowledge": 2}
        assert search_knowledge_tool.is_enabled(mock_ctx, mock_agent) is False

    def test_ask_mode_full_flow(self):
        """Test full flow of ask mode tool limiting."""
        context = AgentContext(user_permission=UserPermission.BASIC)

        # Get tools for ask mode
        tools = tool_initializer.get_tools_for_mode(AgentMode.ASK, context)

        # Verify limits are set
        assert context.tool_limits["search_knowledge"] == 8
        assert context.tool_limits["search_web"] == 7

        # Simulate usage
        for i in range(8):
            context.increment_tool_usage("search_knowledge")

        # Tool should now be disabled
        assert context.is_tool_enabled("search_knowledge") is False
        assert context.is_tool_enabled("search_web") is True  # Still under limit
