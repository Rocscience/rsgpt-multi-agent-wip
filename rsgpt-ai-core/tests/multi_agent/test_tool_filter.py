"""Tests for device MCP tool filtering."""

from app.services.multi_agent.schema import ServerEntry
from app.services.multi_agent.tool_filter import tool_belongs_to_server


def test_rs2_tool_filter():
    entry = ServerEntry(
        open_tool="open_rs2_model",
        state_tool="rs2_get_model_state",
        tool_patterns=["^rs2_", "^RS2_", "^enable_rs2", "^open_rs2"],
    )
    assert tool_belongs_to_server("open_rs2_model", "rs2-server", entry)
    assert tool_belongs_to_server("RS2_grep_tool", "rs2-server", entry)
    assert tool_belongs_to_server("rs2_compute", "rs2-server", entry)
    assert not tool_belongs_to_server("rspile_compute", "rs2-server", entry)
    assert not tool_belongs_to_server("read_file", "rs2-server", entry)


def test_rspile_tool_filter():
    entry = ServerEntry(
        open_tool="rspile_open_model",
        state_tool="rspile_get_model_state",
        tool_patterns=["^rspile_", "^RSP_", "^RSPile_", "^enable_rspile", "^open_rspile"],
    )
    assert tool_belongs_to_server("rspile_open_model", "rspile-server", entry)
    assert tool_belongs_to_server("RSP_grep_tool", "rspile-server", entry)
    assert tool_belongs_to_server("RSPile_Results_get_pile_results", "rspile-server", entry)
    assert not tool_belongs_to_server("rs2_compute", "rspile-server", entry)


def test_slide2_tool_filter():
    entry = ServerEntry(
        open_tool="open_slide2_model",
        state_tool="get_slide2_modifying_tool_capabilities",
        tool_patterns=["^open_slide2", "^modify_slide2", "^get_slide2", "^compare_slide2"],
    )
    assert tool_belongs_to_server("open_slide2_model", "slide2-server", entry)
    assert tool_belongs_to_server("modify_slide2_model", "slide2-server", entry)
    assert tool_belongs_to_server("compare_slide2_models", "slide2-server", entry)
    assert not tool_belongs_to_server("rspile_compute", "slide2-server", entry)


def test_settle3_tool_filter():
    entry = ServerEntry(
        open_tool="open_settle3_model",
        state_tool="analyze_model",
        tool_patterns=["^settle3_", "^open_settle3", "^modify_settle3", "^analyze_model$"],
    )
    assert tool_belongs_to_server("open_settle3_model", "settle3-server", entry)
    assert tool_belongs_to_server("modify_settle3_script", "settle3-server", entry)
    assert tool_belongs_to_server("analyze_model", "settle3-server", entry)


def test_tool_patterns_fall_back_to_server_id_prefix():
    """A server with no configured patterns still matches its <prefix>_ tools."""
    entry = ServerEntry(open_tool="open_foo_model")
    assert tool_belongs_to_server("foo_compute", "foo-server", entry)
    assert tool_belongs_to_server("open_foo_model", "foo-server", entry)
    assert not tool_belongs_to_server("bar_compute", "foo-server", entry)


def test_should_use_multi_agent_routing():
    from app.models.agent import AgentMode, AgentRequest
    from app.services.multi_agent.orchestration_service import should_use_multi_agent

    req = AgentRequest(input="test", session_id="s1", mode=AgentMode.AGENT, device_id="dev-1")
    assert should_use_multi_agent(req) is True
    req_no_device = AgentRequest(input="test", session_id="s1", mode=AgentMode.AGENT)
    assert should_use_multi_agent(req_no_device) is False
