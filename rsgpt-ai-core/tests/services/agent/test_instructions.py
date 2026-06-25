"""Unit tests for agent instructions module"""

import pytest

from app.models.agent import AgentContext, AgentMode
from app.services.agent.instructions import (
    DEVICE_CONNECTED_INSTRUCTIONS,
    DEVICE_DISCONNECTED_INSTRUCTIONS,
    MAIN_AGENT_INSTRUCTIONS,
    NO_DEVICE_SELECTED_INSTRUCTIONS,
    STRATEGIC_TOOL_USAGE_INSTRUCTIONS,
    _needs_strategic_tool_guidance,
    build_device_context,
    build_instructions,
)


class TestBuildDeviceContext:
    """Test cases for build_device_context function"""

    def test_device_connected_returns_connected_instructions(self):
        """Test that connected device returns DEVICE_CONNECTED_INSTRUCTIONS"""
        context = AgentContext(
            session_id="test-session",
            device_id="RS2_device_123",
            device_connected=True,
        )

        result = build_device_context(context)

        assert result is not None
        assert "DEVICE CONNECTED" in result
        assert "RS2_device_123" in result
        assert "Model Queries" in result
        assert "Model Editing" in result

    def test_device_disconnected_returns_disconnected_instructions(self):
        """Test that disconnected device returns DEVICE_DISCONNECTED_INSTRUCTIONS"""
        context = AgentContext(
            session_id="test-session",
            device_id="RS2_device_456",
            device_connected=False,
        )

        result = build_device_context(context)

        assert result is not None
        assert "not connected" in result
        assert "RS2_device_456" in result
        assert "check connection" in result.lower()

    def test_no_device_id_returns_no_device_instructions(self):
        """Test that no device_id returns NO_DEVICE_SELECTED_INSTRUCTIONS"""
        context = AgentContext(
            session_id="test-session",
            device_id=None,
            device_connected=False,
        )

        result = build_device_context(context)

        assert result is not None
        assert "No device selected" in result
        assert "connect" in result.lower()

    def test_no_device_id_with_none_connected_status(self):
        """Test with device_id=None and device_connected not set"""
        context = AgentContext(
            session_id="test-session",
        )

        result = build_device_context(context)

        assert result is not None
        assert "No device selected" in result


class TestDeviceInstructionConstants:
    """Test the device instruction constant strings"""

    def test_device_connected_instructions_has_model_guidance(self):
        """Test DEVICE_CONNECTED_INSTRUCTIONS contains model guidance"""
        instructions = DEVICE_CONNECTED_INSTRUCTIONS.format(device_id="test_device")

        assert (
            "start_rs2_server" in instructions or "start_rspile_server" in instructions
        )
        assert (
            "get_project_settings" in instructions or "get_model_state" in instructions
        )
        assert "grep_search" in instructions or "grep" in instructions.lower()

    def test_device_connected_instructions_has_editing_tips(self):
        """Test DEVICE_CONNECTED_INSTRUCTIONS contains editing tips"""
        instructions = DEVICE_CONNECTED_INSTRUCTIONS.format(device_id="test_device")

        assert "modify" in instructions.lower() or "edit" in instructions.lower()
        assert "activate" in instructions.lower()

    def test_device_disconnected_instructions_has_guidance(self):
        """Test DEVICE_DISCONNECTED_INSTRUCTIONS contains reconnection guidance"""
        instructions = DEVICE_DISCONNECTED_INSTRUCTIONS.format(device_id="test_device")

        assert "test_device" in instructions
        assert "not connected" in instructions
        assert "documentation" in instructions.lower()

    def test_no_device_selected_instructions_has_guidance(self):
        """Test NO_DEVICE_SELECTED_INSTRUCTIONS contains selection guidance"""
        instructions = NO_DEVICE_SELECTED_INSTRUCTIONS

        assert "No device selected" in instructions
        assert "RSInsight" in instructions
        assert "sidebar" in instructions.lower()


class TestBuildInstructions:
    """Test cases for build_instructions function"""

    def test_agent_mode_with_connected_device(self):
        """Test agent mode instructions include device context when connected"""
        context = AgentContext(
            session_id="test-session",
            device_id="RS2_test",
            device_connected=True,
        )

        result = build_instructions(
            MAIN_AGENT_INSTRUCTIONS,
            agent_context=context,
            mode=AgentMode.AGENT,
        )

        assert "DEVICE CONNECTED" in result
        assert "RS2_test" in result
        assert "Model Queries" in result

    def test_agent_mode_with_disconnected_device(self):
        """Test agent mode instructions include disconnected context"""
        context = AgentContext(
            session_id="test-session",
            device_id="RSPile_test",
            device_connected=False,
        )

        result = build_instructions(
            MAIN_AGENT_INSTRUCTIONS,
            agent_context=context,
            mode=AgentMode.AGENT,
        )

        assert "not connected" in result
        assert "RSPile_test" in result

    def test_agent_mode_with_no_device(self):
        """Test agent mode instructions include no device context"""
        context = AgentContext(
            session_id="test-session",
            device_id=None,
        )

        result = build_instructions(
            MAIN_AGENT_INSTRUCTIONS,
            agent_context=context,
            mode=AgentMode.AGENT,
        )

        assert "No device selected" in result

    def test_agent_mode_without_context(self):
        """Test agent mode returns base instructions without context"""
        result = build_instructions(
            MAIN_AGENT_INSTRUCTIONS,
            agent_context=None,
            mode=AgentMode.AGENT,
        )

        assert result == MAIN_AGENT_INSTRUCTIONS

    def test_ask_mode_does_not_include_device_context(self):
        """Test ask mode instructions don't include device context"""
        context = AgentContext(
            session_id="test-session",
            device_id="RS2_test",
            device_connected=True,
        )

        result = build_instructions(
            MAIN_AGENT_INSTRUCTIONS,
            agent_context=context,
            mode=AgentMode.ASK,
        )

        # Ask mode uses its own template, not device context
        assert "Ask Mode" in result
        assert "DEVICE CONNECTED" not in result

    def test_base_instructions_not_modified(self):
        """Test that base instructions are not modified by device context"""
        context = AgentContext(
            session_id="test-session",
            device_id="RS2_test",
            device_connected=True,
        )

        result = build_instructions(
            MAIN_AGENT_INSTRUCTIONS,
            agent_context=context,
            mode=AgentMode.AGENT,
        )

        # Base instructions should be at the start
        assert result.startswith(MAIN_AGENT_INSTRUCTIONS[:100])

        # Device context should be appended
        assert result != MAIN_AGENT_INSTRUCTIONS
        assert len(result) > len(MAIN_AGENT_INSTRUCTIONS)


class TestStrategicToolGuidance:
    """Test cases for strategic tool usage guidance"""

    def test_gpt5_needs_guidance(self):
        """Test that GPT-5 models need strategic tool guidance"""
        assert _needs_strategic_tool_guidance("gpt-5") is True
        assert _needs_strategic_tool_guidance("gpt-5-mini") is True

    def test_gpt4_needs_guidance(self):
        """Test that GPT-4 models need strategic tool guidance"""
        assert _needs_strategic_tool_guidance("gpt-4o") is True
        assert _needs_strategic_tool_guidance("gpt-4o-mini") is True
        assert _needs_strategic_tool_guidance("gpt-4-turbo") is True

    def test_o_series_needs_guidance(self):
        """Test that O-series models need strategic tool guidance"""
        assert _needs_strategic_tool_guidance("o1") is True
        assert _needs_strategic_tool_guidance("o1-preview") is True
        assert _needs_strategic_tool_guidance("o3") is True
        assert _needs_strategic_tool_guidance("o3-mini") is True
        assert _needs_strategic_tool_guidance("o4-mini") is True

    def test_xai_needs_guidance(self):
        """Test that xAI models need strategic tool guidance"""
        assert _needs_strategic_tool_guidance("xai/grok-2") is True
        assert _needs_strategic_tool_guidance("xai/grok-beta") is True

    def test_anthropic_does_not_need_guidance(self):
        """Test that Anthropic models don't need strategic tool guidance"""
        assert _needs_strategic_tool_guidance("anthropic/claude-sonnet-4-5") is False
        assert _needs_strategic_tool_guidance("anthropic/claude-3-opus") is False
        assert _needs_strategic_tool_guidance("claude-sonnet-4-5") is False

    def test_perplexity_does_not_need_guidance(self):
        """Test that Perplexity models don't need strategic tool guidance"""
        assert _needs_strategic_tool_guidance("perplexity/sonar-pro") is False
        assert _needs_strategic_tool_guidance("perplexity/sonar") is False

    def test_none_model_does_not_need_guidance(self):
        """Test that None model doesn't need guidance"""
        assert _needs_strategic_tool_guidance(None) is False

    def test_empty_model_does_not_need_guidance(self):
        """Test that empty model string doesn't need guidance"""
        assert _needs_strategic_tool_guidance("") is False

    def test_build_instructions_injects_guidance_for_gpt(self):
        """Test that build_instructions injects strategic guidance for GPT models"""
        result = build_instructions(
            MAIN_AGENT_INSTRUCTIONS,
            agent_context=None,
            mode=AgentMode.AGENT,
            model_name="gpt-5",
        )

        assert "STRATEGIC TOOL USAGE" in result
        assert "search_knowledge" in result
        assert "search_web" in result
        assert "Search sparingly" in result

    def test_build_instructions_injects_guidance_for_xai(self):
        """Test that build_instructions injects strategic guidance for xAI models"""
        result = build_instructions(
            MAIN_AGENT_INSTRUCTIONS,
            agent_context=None,
            mode=AgentMode.AGENT,
            model_name="xai/grok-2",
        )

        assert "STRATEGIC TOOL USAGE" in result

    def test_build_instructions_no_guidance_for_anthropic(self):
        """Test that build_instructions doesn't inject guidance for Anthropic models"""
        result = build_instructions(
            MAIN_AGENT_INSTRUCTIONS,
            agent_context=None,
            mode=AgentMode.AGENT,
            model_name="anthropic/claude-sonnet-4-5",
        )

        assert "STRATEGIC TOOL USAGE" not in result

    def test_build_instructions_no_guidance_without_model(self):
        """Test that build_instructions doesn't inject guidance without model_name"""
        result = build_instructions(
            MAIN_AGENT_INSTRUCTIONS,
            agent_context=None,
            mode=AgentMode.AGENT,
            model_name=None,
        )

        assert "STRATEGIC TOOL USAGE" not in result


class TestStrategicToolUsageInstructions:
    """Test the STRATEGIC_TOOL_USAGE_INSTRUCTIONS constant"""

    def test_has_when_to_search_guidance(self):
        """Test instructions have when to search guidance"""
        assert "DO search" in STRATEGIC_TOOL_USAGE_INSTRUCTIONS
        assert "DON'T search" in STRATEGIC_TOOL_USAGE_INSTRUCTIONS

    def test_has_tool_usage_guidelines(self):
        """Test instructions have tool usage guidelines"""
        assert "Guidelines" in STRATEGIC_TOOL_USAGE_INSTRUCTIONS
        assert "Search sparingly" in STRATEGIC_TOOL_USAGE_INSTRUCTIONS
        assert "One search at a time" in STRATEGIC_TOOL_USAGE_INSTRUCTIONS

    def test_has_tool_selection_guidance(self):
        """Test instructions have tool selection guidance"""
        assert "search_web" in STRATEGIC_TOOL_USAGE_INSTRUCTIONS
        assert "search_knowledge" in STRATEGIC_TOOL_USAGE_INSTRUCTIONS

    def test_has_stop_condition(self):
        """Test instructions have stop condition"""
        assert "Stop searching" in STRATEGIC_TOOL_USAGE_INSTRUCTIONS


class TestMainAgentInstructions:
    """Test the main agent instructions constant"""

    def test_main_instructions_has_scope(self):
        """Test main instructions include scope"""
        assert "## Scope" in MAIN_AGENT_INSTRUCTIONS
        assert "IN SCOPE" in MAIN_AGENT_INSTRUCTIONS
        assert "OUT OF SCOPE" in MAIN_AGENT_INSTRUCTIONS

    def test_main_instructions_has_tool_info(self):
        """Test main instructions include tool information"""
        assert "search_knowledge" in MAIN_AGENT_INSTRUCTIONS
        assert "search_web" in MAIN_AGENT_INSTRUCTIONS
        assert "Device Tools" in MAIN_AGENT_INSTRUCTIONS

    def test_main_instructions_has_communication(self):
        """Test main instructions include communication guidelines"""
        assert "## Communication" in MAIN_AGENT_INSTRUCTIONS

    def test_main_instructions_does_not_have_model_details_queries(self):
        """Test main instructions don't include device-specific model queries section"""
        # This section should only be in DEVICE_CONNECTED_INSTRUCTIONS
        assert "Model Queries" not in MAIN_AGENT_INSTRUCTIONS

    def test_main_instructions_has_critical_rules(self):
        """Test main instructions include critical rules"""
        assert "Critical Rules" in MAIN_AGENT_INSTRUCTIONS
        assert "Stop on errors" in MAIN_AGENT_INSTRUCTIONS
