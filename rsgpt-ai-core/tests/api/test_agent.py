"""Unit tests for agent API endpoints"""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import HTTPException

from app.api.routes.agent import (
    agent_info,
    agent_stream,
    list_active_runs,
    list_connected_devices,
)
from app.models.agent import AgentRequest, AgentRunInfo, AgentRunStatus


class TestAgentInfo:
    """Test agent info endpoint"""

    @pytest.mark.asyncio
    async def test_agent_info_success(self):
        """Test successful agent info retrieval"""
        with patch(
            "app.api.routes.agent.orchestration_service.get_active_runs"
        ) as mock_get_runs, patch(
            "app.api.routes.agent.connection_manager.get_connected_devices"
        ) as mock_get_devices:
            # Mock active runs
            mock_get_runs.return_value = {
                "run1": Mock(),
                "run2": Mock(),
            }

            # Mock connected devices
            mock_get_devices.return_value = ["device1", "device2", "device3"]

            result = await agent_info()

            assert result["status"] == "success"
            assert result["service"] == "rsgpt-ai-core-agent"
            assert result["active_runs"] == 2
            assert result["connected_devices"] == 3
            assert "streaming" in result["features"]
            assert "dynamic_tool_discovery" in result["features"]

    @pytest.mark.asyncio
    async def test_agent_info_no_runs(self):
        """Test agent info with no active runs"""
        with patch(
            "app.api.routes.agent.orchestration_service.get_active_runs"
        ) as mock_get_runs, patch(
            "app.api.routes.agent.connection_manager.get_connected_devices"
        ) as mock_get_devices:
            mock_get_runs.return_value = {}
            mock_get_devices.return_value = []

            result = await agent_info()

            assert result["active_runs"] == 0
            assert result["connected_devices"] == 0


class TestAgentStream:
    """Test agent streaming endpoint"""

    @pytest.mark.asyncio
    async def test_agent_stream_success(self):
        """Test successful agent stream creation"""
        agent_request = AgentRequest(
            input="Hello",
            session_id="test-session-123",
            device_id="device-123",
        )

        # Mock FastAPI Request object
        mock_http_request = AsyncMock()
        mock_http_request.is_disconnected.return_value = False

        with patch(
            "app.api.routes.agent.connection_manager.is_device_connected"
        ) as mock_is_connected, patch(
            "app.api.routes.agent.orchestration_service.stream_workflow"
        ) as mock_generate:
            mock_is_connected.return_value = True

            # Mock the generator
            async def mock_stream():
                yield "event: test\ndata: {}\n\n"

            mock_generate.return_value = mock_stream()

            response = await agent_stream(agent_request, mock_http_request)

            assert response.media_type == "text/event-stream"
            assert response.headers["Cache-Control"] == "no-cache"
            assert response.headers["Connection"] == "keep-alive"

    @pytest.mark.asyncio
    async def test_agent_stream_without_device_id(self):
        """Test agent stream without device_id"""
        agent_request = AgentRequest(
            input="Hello",
            session_id="test-session-456",
        )

        # Mock FastAPI Request object
        mock_http_request = AsyncMock()
        mock_http_request.is_disconnected.return_value = False

        with patch(
            "app.api.routes.agent.orchestration_service.stream_workflow"
        ) as mock_generate:

            async def mock_stream():
                yield "event: test\ndata: {}\n\n"

            mock_generate.return_value = mock_stream()

            response = await agent_stream(agent_request, mock_http_request)

            assert response.media_type == "text/event-stream"

    @pytest.mark.asyncio
    async def test_agent_stream_service_error(self):
        """Test agent stream with service error"""
        agent_request = AgentRequest(
            input="Hello",
            session_id="test-session-789",
        )

        # Mock FastAPI Request object
        mock_http_request = AsyncMock()
        mock_http_request.is_disconnected.return_value = False

        with patch(
            "app.api.routes.agent.orchestration_service.stream_workflow"
        ) as mock_generate:
            mock_generate.side_effect = ValueError("Service error")

            with pytest.raises(HTTPException) as exc_info:
                await agent_stream(agent_request, mock_http_request)

            assert exc_info.value.status_code == 500


class TestListConnectedDevices:
    """Test list connected devices endpoint"""

    @pytest.mark.asyncio
    async def test_list_connected_devices_success(self):
        """Test successful device listing"""
        with patch(
            "app.api.routes.agent.connection_manager.get_connected_devices"
        ) as mock_get_devices:
            mock_get_devices.return_value = ["device1", "device2", "device3"]

            result = await list_connected_devices()

            assert result["status"] == "success"
            assert result["count"] == 3
            assert len(result["devices"]) == 3
            assert "device1" in result["devices"]

    @pytest.mark.asyncio
    async def test_list_connected_devices_empty(self):
        """Test device listing with no devices"""
        with patch(
            "app.api.routes.agent.connection_manager.get_connected_devices"
        ) as mock_get_devices:
            mock_get_devices.return_value = []

            result = await list_connected_devices()

            assert result["status"] == "success"
            assert result["count"] == 0
            assert result["devices"] == []

    @pytest.mark.asyncio
    async def test_list_connected_devices_error(self):
        """Test device listing error handling"""
        with patch(
            "app.api.routes.agent.connection_manager.get_connected_devices"
        ) as mock_get_devices:
            mock_get_devices.side_effect = Exception("Connection error")

            with pytest.raises(HTTPException) as exc_info:
                await list_connected_devices()

            assert exc_info.value.status_code == 500


class TestListActiveRuns:
    """Test list active runs endpoint"""

    @pytest.mark.asyncio
    async def test_list_active_runs_success(self):
        """Test successful runs listing"""
        run1 = AgentRunInfo(
            id="run1",
            agent_name="Agent1",
            status=AgentRunStatus.RUNNING,
            turn_count=2,
            created_at=1234567890.0,
        )
        run2 = AgentRunInfo(
            id="run2",
            agent_name="Agent2",
            status=AgentRunStatus.RUNNING,
            turn_count=1,
            created_at=1234567891.0,
        )

        with patch(
            "app.api.routes.agent.orchestration_service.get_active_runs"
        ) as mock_get_runs:
            mock_get_runs.return_value = {"run1": run1, "run2": run2}

            result = await list_active_runs()

            assert result["status"] == "success"
            assert result["count"] == 2
            assert len(result["active_runs"]) == 2
            assert result["active_runs"][0]["id"] in ["run1", "run2"]

    @pytest.mark.asyncio
    async def test_list_active_runs_empty(self):
        """Test runs listing with no active runs"""
        with patch(
            "app.api.routes.agent.orchestration_service.get_active_runs"
        ) as mock_get_runs:
            mock_get_runs.return_value = {}

            result = await list_active_runs()

            assert result["status"] == "success"
            assert result["count"] == 0
            assert result["active_runs"] == []

    @pytest.mark.asyncio
    async def test_list_active_runs_error(self):
        """Test runs listing error handling"""
        with patch(
            "app.api.routes.agent.orchestration_service.get_active_runs"
        ) as mock_get_runs:
            mock_get_runs.side_effect = Exception("Database error")

            with pytest.raises(HTTPException) as exc_info:
                await list_active_runs()

            assert exc_info.value.status_code == 500
