"""Unit tests for dynamic tool factory"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from agents import Agent, FunctionTool

from app.services.agent.tools.device_tools import (
    _fix_json_schema,
    parse_device_tools_to_functions,
    update_agent_tools,
)


class TestFixJsonSchema:
    """Test _fix_json_schema function"""

    def test_fix_schema_missing_type(self):
        """Test fixing schema with missing type"""
        schema = {"properties": {"name": {"description": "Name"}}}

        fixed = _fix_json_schema(schema, "test_tool")

        assert fixed["type"] == "object"
        assert fixed["properties"]["name"]["type"] == "string"

    def test_fix_schema_with_enum(self):
        """Test fixing schema with enum (infers string type)"""
        schema = {
            "properties": {"status": {"enum": ["active", "inactive"]}},
        }

        fixed = _fix_json_schema(schema, "test_tool")

        assert fixed["properties"]["status"]["type"] == "string"

    def test_fix_schema_with_nested_object(self):
        """Test fixing nested object schema"""
        schema = {
            "type": "object",
            "properties": {
                "config": {
                    "properties": {"key": {"description": "Key"}},
                },
            },
        }

        fixed = _fix_json_schema(schema, "test_tool")

        assert fixed["properties"]["config"]["type"] == "object"
        assert fixed["properties"]["config"]["properties"]["key"]["type"] == "string"

    def test_fix_schema_with_array(self):
        """Test fixing array schema"""
        schema = {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "items": {"description": "Item"},
                },
            },
        }

        fixed = _fix_json_schema(schema, "test_tool")

        assert fixed["properties"]["items"]["type"] == "array"
        assert fixed["properties"]["items"]["items"]["type"] == "object"

    def test_fix_schema_invalid_input(self):
        """Test fixing invalid schema input"""
        schema = "not a dict"

        fixed = _fix_json_schema(schema, "test_tool")

        assert fixed == {"type": "object", "properties": {}}

    def test_fix_schema_preserves_existing_type(self):
        """Test that existing types are preserved"""
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Name"},
                "count": {"type": "number", "description": "Count"},
            },
        }

        fixed = _fix_json_schema(schema, "test_tool")

        assert fixed["type"] == "object"
        assert fixed["properties"]["name"]["type"] == "string"
        assert fixed["properties"]["count"]["type"] == "number"


class TestParseDeviceToolsToFunctions:
    """Test parse_device_tools_to_functions function"""

    @pytest.fixture
    def sample_tools(self):
        """Sample device tools"""
        return [
            {
                "name": "read_file",
                "description": "Read a file",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "File path"},
                    },
                    "required": ["path"],
                },
            },
            {
                "name": "write_file",
                "description": "Write a file",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "content": {"type": "string", "description": "File content"},
                    },
                    "required": ["content"],
                },
            },
        ]

    @pytest.fixture
    def mock_agent(self):
        """Mock agent"""
        agent = MagicMock(spec=Agent)
        agent.tools = []
        return agent

    def test_parse_device_tools_basic(self, sample_tools, mock_agent):
        """Test parsing basic device tools"""
        tools = parse_device_tools_to_functions(
            device_id="device1",
            json_tools=sample_tools,
            agent_ref=mock_agent,
            update_callback=None,
        )

        assert len(tools) == 2
        assert all(isinstance(t, FunctionTool) for t in tools)
        assert tools[0].name == "read_file"
        assert tools[1].name == "write_file"

    def test_parse_device_tools_without_agent(self, sample_tools):
        """Test parsing tools without agent reference"""
        tools = parse_device_tools_to_functions(
            device_id="device1",
            json_tools=sample_tools,
            agent_ref=None,
            update_callback=None,
        )

        assert len(tools) == 2
        assert all(isinstance(t, FunctionTool) for t in tools)

    def test_parse_device_tools_skips_invalid(self):
        """Test that invalid tools are skipped"""
        invalid_tools = [
            {"name": "valid_tool", "input_schema": {}},
            {"description": "missing name"},
            {"name": "", "input_schema": {}},
        ]

        tools = parse_device_tools_to_functions(
            device_id="device1",
            json_tools=invalid_tools,
            agent_ref=None,
            update_callback=None,
        )

        assert len(tools) == 1
        assert tools[0].name == "valid_tool"

    def test_parse_device_tools_deduplicates(self):
        """Test that duplicate tool names are deduplicated"""
        duplicate_tools = [
            {"name": "tool1", "input_schema": {}},
            {"name": "tool1", "input_schema": {}},  # Duplicate
            {"name": "tool2", "input_schema": {}},
        ]

        tools = parse_device_tools_to_functions(
            device_id="device1",
            json_tools=duplicate_tools,
            agent_ref=None,
            update_callback=None,
        )

        assert len(tools) == 2
        assert tools[0].name == "tool1"
        assert tools[1].name == "tool2"

    def test_parse_device_tools_handler_execution(self, sample_tools, mock_agent):
        """Test that tool handlers are created correctly"""
        tools = parse_device_tools_to_functions(
            device_id="device1",
            json_tools=sample_tools,
            agent_ref=mock_agent,
            update_callback=None,
        )

        assert len(tools) == 2
        assert tools[0].on_invoke_tool is not None
        assert tools[1].on_invoke_tool is not None


class TestUpdateAgentTools:
    """Test update_agent_tools function"""

    @pytest.fixture
    def mock_agent(self):
        """Mock agent with existing tools"""
        agent = MagicMock(spec=Agent)
        # Create mock tools that represent built-in tools (non-device)
        search_knowledge = MagicMock()
        search_knowledge.name = "search_knowledge"
        # Ensure _device_tool is False (default for built-in tools)
        search_knowledge.configure_mock(**{"_device_tool": False})

        search_web = MagicMock()
        search_web.name = "search_web"
        search_web.configure_mock(**{"_device_tool": False})

        agent.tools = [search_knowledge, search_web]
        return agent

    @pytest.mark.asyncio
    async def test_update_agent_tools_success(self, mock_agent):
        """Test successful tool update"""
        mock_tools_response = {
            "tools": [
                {
                    "name": "new_tool",
                    "description": "New tool",
                    "input_schema": {"type": "object", "properties": {}},
                },
            ],
            "error": None,
        }

        with patch(
            "app.services.agent.tools.device_tools.connection_manager.request_list_tools",
            new_callable=AsyncMock,
        ) as mock_list_tools:
            mock_list_tools.return_value = mock_tools_response

            await update_agent_tools(mock_agent, "device1")

            # Should keep all built-in tools (search_knowledge, search_web) and add new_tool
            assert len(mock_agent.tools) == 3
            tool_names = [t.name for t in mock_agent.tools]
            assert "search_knowledge" in tool_names
            assert "search_web" in tool_names
            assert "new_tool" in tool_names

    @pytest.mark.asyncio
    async def test_update_agent_tools_with_error(self, mock_agent):
        """Test tool update with error response"""
        mock_tools_response = {"tools": [], "error": "Device not connected"}

        with patch(
            "app.services.agent.tools.device_tools.connection_manager.request_list_tools",
            new_callable=AsyncMock,
        ) as mock_list_tools:
            mock_list_tools.return_value = mock_tools_response

            await update_agent_tools(mock_agent, "device1")

            # Tools should remain unchanged (built-in tools preserved, no device tools added)
            assert len(mock_agent.tools) == 2
            tool_names = [t.name for t in mock_agent.tools]
            assert "search_knowledge" in tool_names
            assert "search_web" in tool_names

    @pytest.mark.asyncio
    async def test_update_agent_tools_timeout(self, mock_agent):
        """Test tool update with timeout"""
        with patch(
            "app.services.agent.tools.device_tools.connection_manager.request_list_tools",
            new_callable=AsyncMock,
        ) as mock_list_tools:
            mock_list_tools.side_effect = TimeoutError("Request timeout")

            await update_agent_tools(mock_agent, "device1")

            # Tools should remain unchanged (built-in tools preserved, no device tools added)
            assert len(mock_agent.tools) == 2
            tool_names = [t.name for t in mock_agent.tools]
            assert "search_knowledge" in tool_names
            assert "search_web" in tool_names

    @pytest.mark.asyncio
    async def test_update_agent_tools_exception(self, mock_agent):
        """Test tool update with exception"""
        with patch(
            "app.services.agent.tools.device_tools.connection_manager.request_list_tools",
            new_callable=AsyncMock,
        ) as mock_list_tools:
            mock_list_tools.side_effect = Exception("Unexpected error")

            await update_agent_tools(mock_agent, "device1")

            # Tools should remain unchanged (built-in tools preserved, no device tools added)
            assert len(mock_agent.tools) == 2
            tool_names = [t.name for t in mock_agent.tools]
            assert "search_knowledge" in tool_names
            assert "search_web" in tool_names
