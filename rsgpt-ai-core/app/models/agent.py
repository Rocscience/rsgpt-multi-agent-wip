"""Agent API models for OpenAI Agent SDK integration"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.models.channels import SourceChannel, UserPermission


@dataclass
class AgentContext:
    """
    Context object passed to agent tools.

    Contains user information and permissions that tools can access
    to make permission-aware decisions.

    Device Connection Status:
    - device_id is None: No device connected at all
    - device_id is set but device_connected is False: Device ID provided but not connected
    - device_id is set and device_connected is True: Device connected and available

    Tool Usage Tracking (for ask mode limits):
    - tool_usage: Dict tracking how many times each tool has been called
    - tool_limits: Dict defining max calls per tool (None = unlimited)
    """

    user_permission: UserPermission = UserPermission.BASIC
    source_channels: Optional[List[SourceChannel]] = None
    device_id: Optional[str] = None
    session_id: Optional[str] = None  # For SDK session persistence
    usage_breakdown: Optional[List[Dict[str, Any]]] = (
        None  # Per-request usage data (NEW in openai-agents v0.5.0)
    )
    total_tokens: Optional[int] = None  # Total cumulative tokens for the response
    device_connected: bool = False

    # Tool usage tracking for ask mode (prevents exceeding max_turns)
    tool_usage: Optional[Dict[str, int]] = None
    tool_limits: Optional[Dict[str, int]] = None

    def __post_init__(self):
        """Initialize default values"""
        if self.source_channels is None:
            self.source_channels = [SourceChannel.ROC]
        if self.tool_usage is None:
            self.tool_usage = {}
        if self.tool_limits is None:
            self.tool_limits = {}

    def increment_tool_usage(self, tool_name: str) -> int:
        """Increment and return the new usage count for a tool."""
        if self.tool_usage is None:
            self.tool_usage = {}
        current = self.tool_usage.get(tool_name, 0)
        self.tool_usage[tool_name] = current + 1
        return self.tool_usage[tool_name]

    def is_tool_enabled(self, tool_name: str) -> bool:
        """Check if a tool is still enabled (under its usage limit)."""
        if self.tool_limits is None or tool_name not in self.tool_limits:
            return True  # No limit set = always enabled
        if self.tool_usage is None:
            return True
        current_usage = self.tool_usage.get(tool_name, 0)
        limit = self.tool_limits[tool_name]
        return current_usage < limit

    def get_tool_usage_status(self, tool_name: str) -> str:
        """Get human-readable status of tool usage."""
        usage = self.tool_usage.get(tool_name, 0) if self.tool_usage else 0
        limit = self.tool_limits.get(tool_name) if self.tool_limits else None
        if limit is None:
            return f"{tool_name}: {usage} calls (unlimited)"
        return f"{tool_name}: {usage}/{limit} calls"


class AgentMode(str, Enum):
    """Agent operation mode"""

    ASK = "ask"  # Knowledge retrieval only (search_knowledge, search_web)
    AGENT = "agent"  # Full agent with all tools


class ToolChoice(str, Enum):
    """Tool choice options"""

    AUTO = "auto"
    NONE = "none"
    REQUIRED = "required"


class FunctionDefinition(BaseModel):
    """Function tool definition"""

    name: str = Field(..., description="Function name")
    description: Optional[str] = Field(None, description="Function description")
    parameters: Optional[Dict[str, Any]] = Field(
        None, description="JSON Schema for function parameters"
    )
    strict: Optional[bool] = Field(None, description="Whether to use strict mode")


class ToolDefinition(BaseModel):
    """Tool definition for agent"""

    type: str = Field(default="function", description="Tool type")
    function: FunctionDefinition = Field(..., description="Function definition")


class AgentMessage(BaseModel):
    """A single agent message"""

    role: str = Field(..., description="Message role (user, assistant, system)")
    content: str = Field(..., description="Message content")


class AgentRequest(BaseModel):
    """Agent request model for streaming endpoint.

    Simplified payload - SDK session handles conversation history persistence.
    Supports both 'ask' mode (knowledge retrieval) and 'agent' mode (full tools).
    """

    # Required fields
    input: str = Field(..., min_length=1, description="User's input message")
    session_id: str = Field(
        ..., description="Chat session ID for SDK session persistence"
    )

    # Mode configuration
    mode: AgentMode = Field(
        default=AgentMode.AGENT,
        description="Agent operation mode. "
        "'ask' = knowledge retrieval only (search_knowledge, search_web). "
        "'agent' = full agent with all tools including device control.",
    )

    # Optional device connection (only relevant in agent mode)
    device_id: Optional[str] = Field(
        default=None,
        description="Device ID for WebSocket tool operations (RS2, Slide2, etc.). "
        "Only used in 'agent' mode.",
    )

    # Model configuration
    model: Optional[str] = Field(
        default="gpt-5",
        description="Model to use. "
        "Supported: OpenAI (gpt-5), Anthropic (anthropic/claude-sonnet-4-5), "
        "Perplexity (perplexity/sonar-pro - ask mode only, no tools).",
    )
    reasoning_effort: Optional[str] = Field(
        default=None,
        description="Reasoning effort (low, medium, high). "
        "For GPT-5: controls reasoning depth. "
        "For Anthropic: LiteLLM translates to thinking budget_tokens.",
    )

    # User context for permission-aware tools
    user_permission: UserPermission = Field(
        default=UserPermission.BASIC,
        description="User permission level for context retrieval and tool access",
    )
    source_channels: Optional[List[SourceChannel]] = Field(
        default=[SourceChannel.ROC],
        description="Source channels for knowledge search (defaults to [ROC])",
    )

    # SDK Session configuration
    use_sdk_session: bool = Field(
        default=False,
        description="Enable SDK session for persistent conversation memory. "
        "When enabled, conversation history is stored in the database.",
    )


class ToolCallInfo(BaseModel):
    """Information about a tool call"""

    id: str = Field(..., description="Unique tool call ID")
    type: str = Field(default="function", description="Tool type")
    function: Dict[str, Any] = Field(..., description="Function name and arguments")


class AgentRunStatus(str, Enum):
    """Agent run status"""

    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    MAX_TURNS_EXCEEDED = "max_turns_exceeded"


class AgentRunInfo(BaseModel):
    """Information about an agent run"""

    id: str = Field(..., description="Unique run identifier")
    agent_name: str = Field(..., description="Name of the agent")
    status: AgentRunStatus = Field(..., description="Current run status")
    turn_count: int = Field(default=0, description="Number of turns completed")
    created_at: float = Field(..., description="Unix timestamp when run was created")
    completed_at: Optional[float] = Field(
        None, description="Unix timestamp when run was completed"
    )


# Agent-specific streaming events (in addition to OpenAI Responses API events)


class AgentStreamEventType(str, Enum):
    """Agent stream event types"""

    # OpenAI Responses API events (relayed)
    RAW_RESPONSE_EVENT = "raw_response_event"

    # Higher-level agent events
    RUN_STARTED = "agent.run.started"
    RUN_ITEM_CREATED = "agent.run_item.created"
    RUN_ITEM_COMPLETED = "agent.run_item.completed"
    AGENT_UPDATED = "agent.updated"
    RUN_COMPLETED = "agent.run.completed"
    RUN_FAILED = "agent.run.failed"

    # Tool execution events (our custom events)
    TOOL_EXECUTION_STARTED = "agent.tool_execution.started"
    TOOL_EXECUTION_COMPLETED = "agent.tool_execution.completed"
    TOOL_EXECUTION_FAILED = "agent.tool_execution.failed"

    # Context manager events
    CONTEXT_USAGE_UPDATE = "context.usage"
    CONTEXT_SUMMARY_INITIATION = "context.summary_initiation"
    CONTEXT_SUMMARY_COMPLETION = "context.summary_completion"


class RunStartedEvent(BaseModel):
    """Event emitted when agent run starts"""

    type: AgentStreamEventType = Field(
        default=AgentStreamEventType.RUN_STARTED, description="Event type"
    )
    sequence_number: int = Field(..., description="Event sequence number")
    run: AgentRunInfo = Field(..., description="Run information")


class RunItemCreatedEvent(BaseModel):
    """Event emitted when a new run item is created"""

    type: AgentStreamEventType = Field(
        default=AgentStreamEventType.RUN_ITEM_CREATED, description="Event type"
    )
    sequence_number: int = Field(..., description="Event sequence number")
    item_type: str = Field(..., description="Type of item (message, tool_call, etc)")
    item_data: Dict[str, Any] = Field(..., description="Item data")


class RunItemCompletedEvent(BaseModel):
    """Event emitted when a run item is completed"""

    type: AgentStreamEventType = Field(
        default=AgentStreamEventType.RUN_ITEM_COMPLETED, description="Event type"
    )
    sequence_number: int = Field(..., description="Event sequence number")
    item_type: str = Field(..., description="Type of item")
    item_data: Dict[str, Any] = Field(..., description="Completed item data")


class AgentUpdatedEvent(BaseModel):
    """Event emitted when the current agent changes"""

    type: AgentStreamEventType = Field(
        default=AgentStreamEventType.AGENT_UPDATED, description="Event type"
    )
    sequence_number: int = Field(..., description="Event sequence number")
    new_agent_name: str = Field(..., description="New agent name")


class RunCompletedEvent(BaseModel):
    """Event emitted when agent run completes"""

    type: AgentStreamEventType = Field(
        default=AgentStreamEventType.RUN_COMPLETED, description="Event type"
    )
    sequence_number: int = Field(..., description="Event sequence number")
    run: AgentRunInfo = Field(..., description="Completed run information")
    final_output: Optional[str] = Field(None, description="Final output text")


class RunFailedEvent(BaseModel):
    """Event emitted when agent run fails"""

    type: AgentStreamEventType = Field(
        default=AgentStreamEventType.RUN_FAILED, description="Event type"
    )
    sequence_number: int = Field(..., description="Event sequence number")
    run: AgentRunInfo = Field(..., description="Failed run information")
    error: str = Field(..., description="Error message")


class ToolExecutionStartedEvent(BaseModel):
    """Event emitted when tool execution starts"""

    type: AgentStreamEventType = Field(
        default=AgentStreamEventType.TOOL_EXECUTION_STARTED, description="Event type"
    )
    sequence_number: int = Field(..., description="Event sequence number")
    tool_call_id: str = Field(..., description="Tool call ID")
    tool_name: str = Field(..., description="Tool name")
    tool_args: Dict[str, Any] = Field(..., description="Tool arguments")


class ToolExecutionCompletedEvent(BaseModel):
    """Event emitted when tool execution completes"""

    type: AgentStreamEventType = Field(
        default=AgentStreamEventType.TOOL_EXECUTION_COMPLETED, description="Event type"
    )
    sequence_number: int = Field(..., description="Event sequence number")
    tool_call_id: str = Field(..., description="Tool call ID")
    tool_name: str = Field(..., description="Tool name")
    output: Any = Field(..., description="Tool output")


class ToolExecutionFailedEvent(BaseModel):
    """Event emitted when tool execution fails"""

    type: AgentStreamEventType = Field(
        default=AgentStreamEventType.TOOL_EXECUTION_FAILED, description="Event type"
    )
    sequence_number: int = Field(..., description="Event sequence number")
    tool_call_id: str = Field(..., description="Tool call ID")
    tool_name: str = Field(..., description="Tool name")
    error: str = Field(..., description="Error message")


class ContextUsageUpdateEvent(BaseModel):
    """Event emitted when context usage is updated"""

    type: AgentStreamEventType = Field(
        default=AgentStreamEventType.CONTEXT_USAGE_UPDATE, description="Event type"
    )
    sequence_number: int = Field(..., description="Event sequence number")
    session_id: str = Field(..., description="Chat session ID")
    total_tokens: int = Field(..., description="Current input tokens used")
    max_tokens: int = Field(..., description="Maximum input tokens available")
    usage_percentage: float = Field(..., description="Usage percentage (0-100)")
    model_name: str = Field(..., description="Model name")


class ContextSummaryInitiationEvent(BaseModel):
    """Event emitted when context summarization is initiated"""

    type: AgentStreamEventType = Field(
        default=AgentStreamEventType.CONTEXT_SUMMARY_INITIATION,
        description="Event type",
    )
    sequence_number: int = Field(..., description="Event sequence number")
    session_id: str = Field(..., description="Chat session ID")
    model_name: str = Field(..., description="Model name")
    total_tokens: int = Field(..., description="Total tokens at summarization")
    max_tokens: int = Field(..., description="Maximum tokens")
    usage_percentage: float = Field(..., description="Usage percentage (0-100)")


class ContextSummaryCompletionEvent(BaseModel):
    """Event emitted when context summarization completes"""

    type: AgentStreamEventType = Field(
        default=AgentStreamEventType.CONTEXT_SUMMARY_COMPLETION,
        description="Event type",
    )
    sequence_number: int = Field(..., description="Event sequence number")
    session_id: str = Field(..., description="Chat session ID")
    model_name: str = Field(..., description="Model name used for summarization")
    token_count: int = Field(..., description="Token count at time of summarization")
    replaced_messages: int = Field(
        ..., description="Number of messages replaced by summary"
    )
    summary: Dict[str, Any] = Field(..., description="Summary data")


# Multi-Agent Workflow Models


class WorkflowStatus(str, Enum):
    """Workflow status for UI display (NOT stored in DB)"""

    ORCHESTRATING = "orchestrating"
    RESEARCHING = "researching"
    PLANNING = "planning"
    EXECUTING = "executing"
    EVALUATING = "evaluating"
    SUMMARIZING = "summarizing"
    COMPLETED = "completed"
    OUT_OF_SCOPE = "out_of_scope"
    FAILED = "failed"


class WorkflowStartedEvent(BaseModel):
    """Event emitted when workflow starts (includes trace_id)"""

    type: str = Field(default="agent.workflow.started", description="Event type")
    sequence_number: int = Field(..., description="Event sequence number")
    trace_id: str = Field(..., description="OpenAI trace ID")
    timestamp: float = Field(..., description="Unix timestamp")


class WorkflowStatusChangedEvent(BaseModel):
    """Event emitted when workflow status changes (for UI display only)"""

    type: str = Field(default="agent.workflow.status_changed", description="Event type")
    sequence_number: int = Field(..., description="Event sequence number")
    status: WorkflowStatus = Field(..., description="Current workflow status")
    agent_name: str = Field(..., description="Current agent name")


class WorkflowCompletedEvent(BaseModel):
    """Event emitted when workflow completes (includes trace_id)"""

    type: str = Field(default="agent.workflow.completed", description="Event type")
    sequence_number: int = Field(..., description="Event sequence number")
    trace_id: str = Field(..., description="OpenAI trace ID")
    timestamp: float = Field(..., description="Unix timestamp")
    usage_breakdown: Optional[List[Dict[str, Any]]] = Field(
        None, description="Per-request usage breakdown (NEW in openai-agents v0.5.0)"
    )
    total_tokens: Optional[int] = Field(
        None, description="Total cumulative tokens used for this response"
    )


class WorkflowFailedEvent(BaseModel):
    """Event emitted when workflow fails (includes trace_id and error)"""

    type: str = Field(default="agent.workflow.failed", description="Event type")
    sequence_number: int = Field(..., description="Event sequence number")
    trace_id: str = Field(..., description="OpenAI trace ID")
    error: str = Field(..., description="Error message")
    timestamp: float = Field(..., description="Unix timestamp")


class AgentThinkingEvent(BaseModel):
    """Event for displaying reasoning/thinking steps"""

    type: str = Field(default="agent.thinking", description="Event type")
    sequence_number: int = Field(..., description="Event sequence number")
    agent_name: str = Field(..., description="Agent name")
    thinking_text: str = Field(..., description="Reasoning/thinking text")
    is_complete: bool = Field(..., description="Whether thinking is complete")


class AgentPlanningEvent(BaseModel):
    """Event for plan creation"""

    type: str = Field(default="agent.planning", description="Event type")
    sequence_number: int = Field(..., description="Event sequence number")
    plan: Dict[str, Any] = Field(..., description="Execution plan")


class TaskProgressEvent(BaseModel):
    """Event for task execution progress"""

    type: str = Field(default="agent.task_progress", description="Event type")
    sequence_number: int = Field(..., description="Event sequence number")
    task_id: int = Field(..., description="Current task ID")
    task_description: str = Field(..., description="Task description")
    status: str = Field(..., description="Task status")
    current_task_index: int = Field(..., description="Current task index (0-based)")
    total_tasks: int = Field(..., description="Total number of tasks")


class OutOfScopeEvent(BaseModel):
    """Event for out of scope requests"""

    type: str = Field(default="agent.out_of_scope", description="Event type")
    sequence_number: int = Field(..., description="Event sequence number")
    reason: str = Field(..., description="Reason for out of scope")


class AgentTransitionEvent(BaseModel):
    """Event emitted when orchestrator transitions between agents (via tool calls)"""

    type: str = Field(default="agent.transition", description="Event type")
    sequence_number: int = Field(..., description="Event sequence number")
    from_agent: str = Field(..., description="Agent transitioning from")
    to_agent: str = Field(..., description="Agent transitioning to")
    tool_name: str | None = Field(
        default=None, description="Tool name (for agent tools)"
    )
    completed: bool = Field(
        default=False, description="Whether this is a return transition"
    )
    timestamp: float | None = Field(default=None, description="Transition timestamp")


class HeartbeatEvent(BaseModel):
    """Heartbeat event to keep SSE connection alive during long operations.

    Emitted periodically when the stream is "quiet" (e.g., during tool execution)
    to prevent connection timeouts from ALB/proxies.
    """

    type: str = Field(default="agent.heartbeat", description="Event type")
    sequence_number: int = Field(..., description="Event sequence number")
    timestamp: float = Field(..., description="Unix timestamp")
    message: str = Field(default="keepalive", description="Heartbeat message")


# Multi-Agent Workflow Output Schemas


class EvaluatorTaskItem(BaseModel):
    """Task item in evaluator's updated plan"""

    id: int = Field(..., description="Task ID")
    description: str = Field(..., description="Task description")
    done: bool = Field(..., description="Whether task is completed")


class EvaluatorPlan(BaseModel):
    """Plan structure in evaluator output"""

    goal: str = Field(..., description="Overall goal")
    tasks: List[EvaluatorTaskItem] = Field(..., description="List of tasks")


class EvaluatorSchema(BaseModel):
    """Schema for evaluator agent output"""

    plan: EvaluatorPlan = Field(..., description="Updated plan")
    task_success: bool = Field(..., description="Whether task was successful")
    major_error: bool = Field(..., description="Whether a major error occurred")
    analysis: str = Field(..., description="Analysis of execution")


class ExecutorActionItem(BaseModel):
    """Action taken by executor"""

    tool: str = Field(..., description="Tool name")
    params: str = Field(..., description="Tool parameters (JSON string)")
    result_summary: str = Field(..., description="Result summary")


class ExecutorSchema(BaseModel):
    """Schema for executor agent output"""

    task_id: int = Field(..., description="Task ID being executed")
    status: str = Field(..., description="Status: completed | failed | partial")
    major_error: bool = Field(..., description="Whether a major error occurred")
    actions_taken: List[ExecutorActionItem] = Field(..., description="Actions taken")
    result_summary: str = Field(..., description="Summary of results")
    notes: str = Field(..., description="Additional notes")


class PlannerTaskMetadata(BaseModel):
    """Metadata for a task in the plan"""

    complexity: str = Field(..., description="Complexity: low | medium | high")


class PlannerTaskItem(BaseModel):
    """Task item in planner's plan"""

    id: int = Field(..., description="Task ID")
    description: str = Field(..., description="Task description")
    success_criteria: str = Field(..., description="Success criteria")
    validation: str = Field(..., description="How to validate")
    hints: str = Field(..., description="Hints for execution")
    prerequisites: List[str] = Field(..., description="Prerequisites")
    risk: str = Field(..., description="Risk assessment")
    metadata: PlannerTaskMetadata = Field(..., description="Task metadata")


class HighLevelPlannerSchema(BaseModel):
    """Schema for high-level planner agent output"""

    goal: str = Field(..., description="Overall goal")
    assumptions: List[str] = Field(..., description="Assumptions made")
    tasks: List[PlannerTaskItem] = Field(..., description="List of tasks")
    requires_followup: bool = Field(..., description="Whether followup is required")
    notes: str = Field(..., description="Additional notes")
