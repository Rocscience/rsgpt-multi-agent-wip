"""Unit tests for tool initializer"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.agent.tools.tool_initializer import (
    DeviceToolsResult,
    ToolInitializer,
    tool_initializer,
)


class TestToolInitializer:
    """Test ToolInitializer class"""

    @pytest.fixture
    def initializer(self):
        """Create a fresh initializer instance"""
        return ToolInitializer()

    def test_base_tools_defined(self, initializer):
        """Test that base tools are defined"""
        assert len(initializer.BASE_TOOLS) == 2
        tool_names = [getattr(t, "name", str(t)) for t in initializer.BASE_TOOLS]
        assert "search_knowledge" in str(tool_names)
        assert "search_web" in str(tool_names)

    def test_get_base_tools(self, initializer):
        """Test getting base tools"""
        tools = initializer.get_base_tools()

        assert len(tools) == 2
        # Should return a copy, not the original list
        assert tools is not initializer.BASE_TOOLS

    @pytest.mark.asyncio
    async def test_initialize_device_tools_not_connected(self, initializer):
        """Test initializing device tools when device is not connected"""
        mock_agent = MagicMock()

        with patch(
            "app.services.agent.tools.tool_initializer.connection_manager.is_device_connected",
            return_value=False,
        ):
            result = await initializer.initialize_device_tools(
                device_id="device123",
                agent=mock_agent,
            )

            assert isinstance(result, DeviceToolsResult)
            assert result.tools == []
            assert result.device_connected is False

    @pytest.mark.asyncio
    async def test_initialize_device_tools_connected(self, initializer):
        """Test initializing device tools when device is connected"""
        mock_agent = MagicMock()
        mock_tools = [{"name": "Tool1"}, {"name": "Tool2"}]

        with patch(
            "app.services.agent.tools.tool_initializer.connection_manager.is_device_connected",
            return_value=True,
        ), patch(
            "app.services.agent.tools.tool_initializer.connection_manager.request_list_tools",
            new_callable=AsyncMock,
            return_value={"tools": mock_tools},
        ), patch(
            "app.services.agent.tools.tool_initializer.parse_device_tools_to_functions",
            return_value=["device_tool_1", "device_tool_2"],
        ):
            result = await initializer.initialize_device_tools(
                device_id="device123",
                agent=mock_agent,
            )

            assert len(result.tools) == 2
            assert result.device_connected is True

    @pytest.mark.asyncio
    async def test_initialize_device_tools_error(self, initializer):
        """Test initializing device tools when fetch fails"""
        mock_agent = MagicMock()

        with patch(
            "app.services.agent.tools.tool_initializer.connection_manager.is_device_connected",
            return_value=True,
        ), patch(
            "app.services.agent.tools.tool_initializer.connection_manager.request_list_tools",
            new_callable=AsyncMock,
            return_value={"error": "Connection failed"},
        ):
            result = await initializer.initialize_device_tools(
                device_id="device123",
                agent=mock_agent,
            )

            assert result.tools == []
            assert result.device_connected is True  # Connected but error

    @pytest.mark.asyncio
    async def test_initialize_device_tools_exception(self, initializer):
        """Test initializing device tools when exception thrown"""
        mock_agent = MagicMock()

        with patch(
            "app.services.agent.tools.tool_initializer.connection_manager.is_device_connected",
            return_value=True,
        ), patch(
            "app.services.agent.tools.tool_initializer.connection_manager.request_list_tools",
            new_callable=AsyncMock,
            side_effect=Exception("Network error"),
        ):
            result = await initializer.initialize_device_tools(
                device_id="device123",
                agent=mock_agent,
            )

            assert result.tools == []
            assert result.device_connected is True  # Connected but error

    @pytest.mark.asyncio
    async def test_add_device_tools_to_agent(self, initializer):
        """Test adding device tools to an existing agent"""
        mock_agent = MagicMock()
        mock_agent.tools = ["base_tool_1", "base_tool_2"]
        mock_tools = [{"name": "Tool1"}]

        with patch(
            "app.services.agent.tools.tool_initializer.connection_manager.is_device_connected",
            return_value=True,
        ), patch(
            "app.services.agent.tools.tool_initializer.connection_manager.request_list_tools",
            new_callable=AsyncMock,
            return_value={"tools": mock_tools},
        ), patch(
            "app.services.agent.tools.tool_initializer.parse_device_tools_to_functions",
            return_value=["device_tool_1"],
        ):
            result = await initializer.add_device_tools_to_agent(
                agent=mock_agent,
                device_id="device123",
            )

            assert result.device_connected is True
            # Agent should now have base tools + device tools
            assert len(mock_agent.tools) == 3

    @pytest.mark.asyncio
    async def test_add_device_tools_no_tools_returned(self, initializer):
        """Test adding device tools when no tools returned"""
        mock_agent = MagicMock()
        mock_agent.tools = ["base_tool_1", "base_tool_2"]

        with patch(
            "app.services.agent.tools.tool_initializer.connection_manager.is_device_connected",
            return_value=False,
        ):
            result = await initializer.add_device_tools_to_agent(
                agent=mock_agent,
                device_id="device123",
            )

            assert result.device_connected is False
            # Agent should still only have base tools
            assert len(mock_agent.tools) == 2


class TestDeviceToolsResult:
    """Test DeviceToolsResult dataclass"""

    def test_default_values(self):
        """Test default values"""
        result = DeviceToolsResult(tools=[])

        assert result.tools == []
        assert result.device_connected is False

    def test_custom_values(self):
        """Test custom values"""
        result = DeviceToolsResult(
            tools=["tool1", "tool2"],
            device_connected=True,
        )

        assert len(result.tools) == 2
        assert result.device_connected is True


class TestToolInitializerSingleton:
    """Test singleton instance"""

    def test_singleton_exists(self):
        """Test that singleton instance exists"""
        assert tool_initializer is not None
        assert isinstance(tool_initializer, ToolInitializer)
