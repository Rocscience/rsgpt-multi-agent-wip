"""Unit tests for agent models"""

import time

import pytest

from app.models.agent import (
    AgentContext,
    AgentRunInfo,
    AgentRunStatus,
    WorkflowCompletedEvent,
    WorkflowFailedEvent,
    WorkflowStartedEvent,
)
from app.models.channels import SourceChannel, UserPermission


class TestAgentContext:
    """Test AgentContext dataclass"""

    def test_default_initialization(self):
        """Test AgentContext with default values"""
        context = AgentContext()

        assert context.user_permission == UserPermission.BASIC
        assert context.source_channels == [SourceChannel.ROC]
        assert context.device_id is None
        assert context.session_id is None
        assert context.usage_breakdown is None
        assert context.total_tokens is None
        assert context.device_connected is False
        assert context.tool_usage == {}
        assert context.tool_limits == {}

    def test_custom_initialization(self):
        """Test AgentContext with custom values"""
        context = AgentContext(
            user_permission=UserPermission.FLEXIBLE,
            source_channels=[SourceChannel.DIANA],
            device_id="device-123",
            session_id="session-456",
            device_connected=True,
            total_tokens=5000,
            usage_breakdown=[{"request_number": 1, "input_tokens": 1000}],
        )

        assert context.user_permission == UserPermission.FLEXIBLE
        assert context.source_channels == [SourceChannel.DIANA]
        assert context.device_id == "device-123"
        assert context.session_id == "session-456"
        assert context.device_connected is True
        assert context.total_tokens == 5000
        assert context.usage_breakdown is not None
        assert len(context.usage_breakdown) == 1

    def test_total_tokens_field(self):
        """Test that total_tokens field can store cumulative token count"""
        context = AgentContext(session_id="test")

        # Initially None
        assert context.total_tokens is None

        # Can be set to an integer
        context.total_tokens = 12500
        assert context.total_tokens == 12500

    def test_usage_breakdown_field(self):
        """Test that usage_breakdown field can store per-request usage"""
        context = AgentContext(session_id="test")

        breakdown = [
            {"request_number": 1, "input_tokens": 1000, "output_tokens": 500},
            {"request_number": 2, "input_tokens": 1500, "output_tokens": 800},
        ]
        context.usage_breakdown = breakdown

        assert context.usage_breakdown == breakdown
        assert len(context.usage_breakdown) == 2


class TestWorkflowCompletedEvent:
    """Test WorkflowCompletedEvent model"""

    def test_basic_initialization(self):
        """Test basic WorkflowCompletedEvent creation"""
        event = WorkflowCompletedEvent(
            sequence_number=1,
            trace_id="trace-123",
            timestamp=time.time(),
        )

        assert event.type == "agent.workflow.completed"
        assert event.sequence_number == 1
        assert event.trace_id == "trace-123"
        assert event.usage_breakdown is None
        assert event.total_tokens is None

    def test_with_usage_data(self):
        """Test WorkflowCompletedEvent with usage data"""
        usage_breakdown = [
            {"request_number": 1, "input_tokens": 1000, "output_tokens": 500},
            {"request_number": 2, "input_tokens": 1500, "output_tokens": 800},
        ]

        event = WorkflowCompletedEvent(
            sequence_number=5,
            trace_id="trace-456",
            timestamp=time.time(),
            usage_breakdown=usage_breakdown,
            total_tokens=3800,
        )

        assert event.usage_breakdown == usage_breakdown
        assert event.total_tokens == 3800
        assert len(event.usage_breakdown) == 2

    def test_model_dump_includes_total_tokens(self):
        """Test that model_dump includes total_tokens"""
        event = WorkflowCompletedEvent(
            sequence_number=1,
            trace_id="trace-789",
            timestamp=1234567890.0,
            total_tokens=5000,
        )

        data = event.model_dump()

        assert "total_tokens" in data
        assert data["total_tokens"] == 5000
        assert data["trace_id"] == "trace-789"

    def test_model_dump_null_total_tokens(self):
        """Test that model_dump handles None total_tokens"""
        event = WorkflowCompletedEvent(
            sequence_number=1,
            trace_id="trace-abc",
            timestamp=1234567890.0,
        )

        data = event.model_dump()

        assert "total_tokens" in data
        assert data["total_tokens"] is None


class TestWorkflowStartedEvent:
    """Test WorkflowStartedEvent model"""

    def test_initialization(self):
        """Test WorkflowStartedEvent creation"""
        event = WorkflowStartedEvent(
            sequence_number=0,
            trace_id="trace-start",
            timestamp=time.time(),
        )

        assert event.type == "agent.workflow.started"
        assert event.trace_id == "trace-start"


class TestWorkflowFailedEvent:
    """Test WorkflowFailedEvent model"""

    def test_initialization(self):
        """Test WorkflowFailedEvent creation"""
        event = WorkflowFailedEvent(
            sequence_number=10,
            trace_id="trace-fail",
            timestamp=time.time(),
            error="Something went wrong",
        )

        assert event.type == "agent.workflow.failed"
        assert event.error == "Something went wrong"


class TestAgentRunInfo:
    """Test AgentRunInfo model"""

    def test_initialization(self):
        """Test AgentRunInfo creation"""
        info = AgentRunInfo(
            id="run-123",
            agent_name="TestAgent",
            status=AgentRunStatus.RUNNING,
            turn_count=0,
            created_at=time.time(),
        )

        assert info.id == "run-123"
        assert info.agent_name == "TestAgent"
        assert info.status == AgentRunStatus.RUNNING

    def test_status_transitions(self):
        """Test AgentRunInfo status can be updated"""
        info = AgentRunInfo(
            id="run-456",
            agent_name="TestAgent",
            status=AgentRunStatus.RUNNING,
            turn_count=0,
            created_at=time.time(),
        )

        assert info.status == AgentRunStatus.RUNNING

        info.status = AgentRunStatus.COMPLETED
        assert info.status == AgentRunStatus.COMPLETED

        info.status = AgentRunStatus.FAILED
        assert info.status == AgentRunStatus.FAILED
