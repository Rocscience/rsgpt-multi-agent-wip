"""Unit tests for orchestration service"""

import time
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from app.models.agent import AgentContext, AgentRequest, AgentRunInfo, AgentRunStatus
from app.services.agent.orchestration_service import (
    OrchestrationService,
    orchestration_service,
)


class TestOrchestrationService:
    """Test OrchestrationService class"""

    @pytest.fixture
    def service(self):
        """Create a fresh service instance"""
        return OrchestrationService()

    def test_initialization(self, service):
        """Test service initializes with empty active runs"""
        assert service.active_runs == {}

    def test_emit_event(self, service):
        """Test event emission formatting"""
        result = service._emit_event("test.event", {"key": "value", "number": 42})

        assert result.startswith("event: test.event\n")
        assert "data: " in result
        assert '"key": "value"' in result
        assert '"number": 42' in result
        assert result.endswith("\n\n")

    def test_create_run_info(self, service):
        """Test creating run info"""
        run_info = service._create_run_info("test-run-123")

        assert run_info.id == "test-run-123"
        assert run_info.agent_name == "RSInsight Agent"
        assert run_info.status == AgentRunStatus.RUNNING
        assert run_info.turn_count == 0

    def test_create_run_info_with_failed_status(self, service):
        """Test creating run info with failed status"""
        run_info = service._create_run_info("test-run-123", AgentRunStatus.FAILED)

        assert run_info.id == "test-run-123"
        assert run_info.status == AgentRunStatus.FAILED

    @patch("app.services.agent.orchestration_service.connection_manager")
    def test_create_agent_context(self, mock_cm, service):
        """Test creating agent context from request"""
        mock_cm.is_device_connected.return_value = True

        request = MagicMock()
        request.user_permission = "admin"
        request.source_channels = ["channel1"]
        request.device_id = "device-123"
        request.session_id = "session-456"

        context = service._create_agent_context(request)

        assert context.user_permission == "admin"
        assert context.source_channels == ["channel1"]
        assert context.device_id == "device-123"
        assert context.session_id == "session-456"
        assert context.device_connected is True
        mock_cm.is_device_connected.assert_called_once_with("device-123")

    @patch("app.services.agent.orchestration_service.connection_manager")
    def test_create_agent_context_no_device(self, mock_cm, service):
        """Test creating agent context without device"""
        request = MagicMock()
        request.user_permission = "user"
        request.source_channels = []
        request.device_id = None
        request.session_id = "session-789"

        context = service._create_agent_context(request)

        assert context.device_connected is False
        mock_cm.is_device_connected.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_active_runs(self, service):
        """Test getting active runs"""
        run1 = AgentRunInfo(
            id="run1",
            agent_name="Agent1",
            status=AgentRunStatus.RUNNING,
            turn_count=0,
            created_at=1234567890.0,
        )
        service.active_runs["run1"] = run1

        runs = await service.get_active_runs()

        assert len(runs) == 1
        assert "run1" in runs
        assert runs["run1"] == run1
        # Verify it's a copy
        assert runs is not service.active_runs

    @pytest.mark.asyncio
    async def test_initialize_rslog_mcp_server(self, service):
        """Test initializing RSLog MCP server"""
        with patch("agents.mcp.MCPServerStreamableHttp") as mock_mcp_class:
            mock_server = AsyncMock()
            mock_server.connect = AsyncMock()
            mock_mcp_class.return_value = mock_server

            result = await service._initialize_rslog_mcp_server(
                rslog_mcp_url="https://rslog.example.com/mcp",
                rslog_mcp_token="test-token",
                timeout=30,
            )

            assert result == mock_server
            mock_mcp_class.assert_called_once()
            mock_server.connect.assert_called_once()

    @pytest.mark.asyncio
    async def test_initialize_rslog_mcp_server_no_token(self, service):
        """Test initializing RSLog MCP server without token"""
        with patch("agents.mcp.MCPServerStreamableHttp") as mock_mcp_class:
            mock_server = AsyncMock()
            mock_server.connect = AsyncMock()
            mock_mcp_class.return_value = mock_server

            result = await service._initialize_rslog_mcp_server(
                rslog_mcp_url="https://rslog.example.com/mcp",
                rslog_mcp_token=None,
                timeout=30,
            )

            assert result == mock_server

    @pytest.mark.asyncio
    async def test_initialize_rslog_mcp_server_error(self, service):
        """Test RSLog MCP server initialization error"""
        with patch("agents.mcp.MCPServerStreamableHttp") as mock_mcp_class:
            mock_mcp_class.side_effect = Exception("Connection failed")

            result = await service._initialize_rslog_mcp_server(
                rslog_mcp_url="https://rslog.example.com/mcp",
                rslog_mcp_token="test-token",
                timeout=30,
            )

            assert result is None


class TestExtractUsageData:
    """Test _extract_usage_data method"""

    @pytest.fixture
    def service(self):
        """Create a fresh service instance"""
        return OrchestrationService()

    def test_extract_usage_data_stores_total_tokens(self, service):
        """Test that total_tokens is extracted and stored in agent_context"""
        # Create mock agent result with usage data
        mock_usage = Mock()
        mock_usage.input_tokens = 1000
        mock_usage.output_tokens = 500
        mock_usage.total_tokens = 1500
        mock_usage.request_usage_entries = []

        mock_context_wrapper = Mock()
        mock_context_wrapper.usage = mock_usage

        mock_agent_result = Mock()
        mock_agent_result.context_wrapper = mock_context_wrapper

        # Create agent context
        agent_context = AgentContext(session_id="test-session")

        # Extract usage data
        service._extract_usage_data(mock_agent_result, agent_context)

        # Verify total_tokens was stored
        assert agent_context.total_tokens == 1500

    def test_extract_usage_data_stores_usage_breakdown(self, service):
        """Test that usage_breakdown is extracted and stored"""
        # Create mock request usage entries
        mock_request_1 = Mock()
        mock_request_1.input_tokens = 500
        mock_request_1.output_tokens = 200
        mock_request_1.total_tokens = 700
        mock_request_1.input_tokens_details = None
        mock_request_1.output_tokens_details = None

        mock_request_2 = Mock()
        mock_request_2.input_tokens = 500
        mock_request_2.output_tokens = 300
        mock_request_2.total_tokens = 800
        mock_request_2.input_tokens_details = None
        mock_request_2.output_tokens_details = None

        mock_usage = Mock()
        mock_usage.input_tokens = 1000
        mock_usage.output_tokens = 500
        mock_usage.total_tokens = 1500
        mock_usage.request_usage_entries = [mock_request_1, mock_request_2]

        mock_context_wrapper = Mock()
        mock_context_wrapper.usage = mock_usage

        mock_agent_result = Mock()
        mock_agent_result.context_wrapper = mock_context_wrapper

        agent_context = AgentContext(session_id="test-session")

        service._extract_usage_data(mock_agent_result, agent_context)

        # Verify both total_tokens and usage_breakdown were stored
        assert agent_context.total_tokens == 1500
        assert agent_context.usage_breakdown is not None
        assert len(agent_context.usage_breakdown) == 2
        assert agent_context.usage_breakdown[0]["input_tokens"] == 500
        assert agent_context.usage_breakdown[1]["output_tokens"] == 300

    def test_extract_usage_data_no_context_wrapper(self, service):
        """Test handling when context_wrapper is None"""
        mock_agent_result = Mock()
        mock_agent_result.context_wrapper = None

        agent_context = AgentContext(session_id="test-session")

        # Should not raise, just return early
        service._extract_usage_data(mock_agent_result, agent_context)

        assert agent_context.total_tokens is None
        assert agent_context.usage_breakdown is None

    def test_extract_usage_data_no_usage(self, service):
        """Test handling when usage is None"""
        mock_context_wrapper = Mock()
        mock_context_wrapper.usage = None

        mock_agent_result = Mock()
        mock_agent_result.context_wrapper = mock_context_wrapper

        agent_context = AgentContext(session_id="test-session")

        service._extract_usage_data(mock_agent_result, agent_context)

        assert agent_context.total_tokens is None
        assert agent_context.usage_breakdown is None

    def test_extract_usage_data_zero_tokens(self, service):
        """Test handling when total_tokens is zero"""
        mock_usage = Mock()
        mock_usage.input_tokens = 0
        mock_usage.output_tokens = 0
        mock_usage.total_tokens = 0
        mock_usage.request_usage_entries = []

        mock_context_wrapper = Mock()
        mock_context_wrapper.usage = mock_usage

        mock_agent_result = Mock()
        mock_agent_result.context_wrapper = mock_context_wrapper

        agent_context = AgentContext(session_id="test-session")

        service._extract_usage_data(mock_agent_result, agent_context)

        # Should return early without storing anything
        assert agent_context.total_tokens is None


class TestSingletons:
    """Test singleton instance"""

    def test_orchestration_service_singleton(self):
        """Test that orchestration_service is a singleton"""
        assert orchestration_service is not None
        assert isinstance(orchestration_service, OrchestrationService)
