"""Chat API models"""

from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field

from app.models.channels import SourceChannel, UserPermission


class ReasoningEffort(str, Enum):
    """OpenAI reasoning effort levels"""

    MINIMAL = "minimal"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ToolCallFunction(BaseModel):
    """Function call details within a tool call"""

    name: str = Field(..., description="Function name being called")
    arguments: str = Field(..., description="JSON string of function arguments")


class ToolCall(BaseModel):
    """Tool call returned by the model"""

    id: str = Field(..., description="Unique tool call ID")
    type: str = Field(default="function", description="Tool call type")
    function: ToolCallFunction = Field(..., description="Function call details")


class ChatMessage(BaseModel):
    """A single chat message"""

    role: Optional[str] = Field(default=None, description="Message role (user, assistant, system)")
    content: Optional[str | List[Dict[str, Any]]] = Field(default=None, description="Message content")
    tool_calls: Optional[List[ToolCall]] = Field(
        default=None,
        description="Tool calls on assistant messages (required for multi-turn tool loops)",
    )
    tool_call_id: Optional[str] = Field(
        default=None, description="Tool call ID (for tool response messages)"
    )
    type: Optional[str] = Field(
        default=None, description="Message type (function_call, tool_result, etc.)"
    )
    call_id: Optional[str] = Field(
        default=None, description="Call ID (for tool call messages)"
    )
    output: Optional[str] = Field(
        default=None, description="Output (for tool result messages)"
    )
    name: Optional[str] = Field(
        default=None, description="Name (for tool call messages)"
    )
    arguments: Optional[str] = Field(
        default=None, description="Arguments (for tool call messages)"
    )


# Tool calling models (OpenAI-compatible format)
class ToolFunction(BaseModel):
    """Function definition for a tool"""

    name: str = Field(..., description="Function name")
    description: str = Field(..., description="Function description")
    parameters: Dict[str, Any] = Field(
        default_factory=dict, description="JSON Schema for function parameters"
    )


class Tool(BaseModel):
    """Tool definition (OpenAI-compatible format)"""

    type: str = Field(default="function", description="Tool type (always 'function')")
    function: ToolFunction = Field(..., description="Function definition")


class ChatRequest(BaseModel):
    """Chat request model"""

    messages: List[ChatMessage] = Field(
        ..., min_length=1, description="List of chat messages"
    )
    provider: Optional[str] = Field(
        default=None, description="LLM provider (openai, claude, perplexity)"
    )
    model: Optional[str] = Field(default=None, description="Specific model to use")
    reasoning_effort: Optional[ReasoningEffort] = Field(
        default=None, description="Reasoning effort for OpenAI models"
    )
    max_tokens: Optional[int] = Field(
        default=None, description="Maximum tokens to generate"
    )
    temperature: Optional[float] = Field(
        default=None, description="Sampling temperature"
    )

    # Tool calling parameters
    tools: Optional[List[Tool]] = Field(
        default=None, description="List of tools available for the model to call"
    )

    # RAG (Retrieval-Augmented Generation) parameters
    use_rag: bool = Field(
        default=False, description="Whether to use RAG for context retrieval"
    )
    rag_source_channels: Optional[List[SourceChannel]] = Field(
        default=None, description="Source channels for RAG (defaults to [ROC])"
    )
    rag_user_permission: UserPermission = Field(
        default=UserPermission.BASIC, description="User permission for RAG"
    )
    rag_top_k: int = Field(
        default=5, ge=1, le=20, description="Number of RAG contexts to retrieve"
    )


class ChatResponse(BaseModel):
    """Non-streaming chat response model"""

    content: str = Field(default="", description="Generated response content")
    provider: str = Field(..., description="Provider used")
    model: str = Field(..., description="Model used")
    usage: Dict[str, Any] = Field(
        default_factory=dict, description="Token usage information"
    )
    tool_calls: Optional[List[ToolCall]] = Field(
        default=None, description="Tool calls requested by the model"
    )


class ChatStreamChunk(BaseModel):
    """Streaming chat response chunk"""

    content: str = Field(..., description="Chunk content")
    finished: bool = Field(default=False, description="Whether this is the final chunk")


class ErrorResponse(BaseModel):
    """Error response model"""

    error: str = Field(..., description="Error message")
    detail: Optional[str] = Field(
        default=None, description="Detailed error information"
    )


# Response Event Models (OpenAI-style)
class ResponseEventType(str, Enum):
    """Response event types"""

    RESPONSE_CREATED = "response.created"
    RESPONSE_IN_PROGRESS = "response.in_progress"
    RESPONSE_OUTPUT_TEXT_DELTA = "response.output_text.delta"
    RESPONSE_OUTPUT_TEXT_DONE = "response.output_text.done"
    RESPONSE_COMPLETED = "response.completed"
    RESPONSE_FAILED = "response.failed"
    ERROR = "error"

    # Agent SDK tool call events
    RESPONSE_TOOL_CALL_CREATED = "response.tool_call.created"
    RESPONSE_TOOL_CALL_DELTA = "response.tool_call.delta"
    RESPONSE_TOOL_CALL_DONE = "response.tool_call.done"
    RESPONSE_TOOL_CALL_OUTPUT = "response.tool_call_output.created"

    # Agent SDK reasoning events
    RESPONSE_REASONING_DELTA = "response.reasoning.delta"
    RESPONSE_REASONING_DONE = "response.reasoning.done"

    # Perplexity search results
    RESPONSE_SEARCH_RESULTS = "response.search_results"


class ResponseStatus(str, Enum):
    """Response status"""

    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class ResponseUsage(BaseModel):
    """Token usage information"""

    input_tokens: int = Field(default=0, description="Number of input tokens")
    output_tokens: int = Field(default=0, description="Number of output tokens")
    total_tokens: int = Field(default=0, description="Total number of tokens")


class ResponseInfo(BaseModel):
    """Basic response information"""

    id: str = Field(..., description="Unique response identifier")
    created_at: float = Field(
        ..., description="Unix timestamp when response was created"
    )
    model: str = Field(..., description="Model used for generation")
    provider: str = Field(..., description="Provider used")
    status: ResponseStatus = Field(..., description="Current response status")
    usage: Optional[ResponseUsage] = Field(default=None, description="Token usage")


class ResponseCreatedEvent(BaseModel):
    """Event emitted when a response is created"""

    type: ResponseEventType = Field(
        default=ResponseEventType.RESPONSE_CREATED, description="Event type"
    )
    sequence_number: int = Field(..., description="Event sequence number")
    response: ResponseInfo = Field(..., description="Response information")


class ResponseInProgressEvent(BaseModel):
    """Event emitted when response generation is in progress"""

    type: ResponseEventType = Field(
        default=ResponseEventType.RESPONSE_IN_PROGRESS, description="Event type"
    )
    sequence_number: int = Field(..., description="Event sequence number")
    response: ResponseInfo = Field(..., description="Response information")


class ResponseOutputTextDeltaEvent(BaseModel):
    """Event emitted for incremental text output"""

    type: ResponseEventType = Field(
        default=ResponseEventType.RESPONSE_OUTPUT_TEXT_DELTA, description="Event type"
    )
    sequence_number: int = Field(..., description="Event sequence number")
    delta: str = Field(..., description="Incremental text content")
    response_id: str = Field(..., description="Response ID this delta belongs to")


class ResponseOutputTextDoneEvent(BaseModel):
    """Event emitted when text output is complete"""

    type: ResponseEventType = Field(
        default=ResponseEventType.RESPONSE_OUTPUT_TEXT_DONE, description="Event type"
    )
    sequence_number: int = Field(..., description="Event sequence number")
    text: str = Field(..., description="Complete text content")
    response_id: str = Field(..., description="Response ID")


class ResponseCompletedEvent(BaseModel):
    """Event emitted when response generation is completed"""

    type: ResponseEventType = Field(
        default=ResponseEventType.RESPONSE_COMPLETED, description="Event type"
    )
    sequence_number: int = Field(..., description="Event sequence number")
    response: ResponseInfo = Field(..., description="Completed response information")


class ResponseFailedEvent(BaseModel):
    """Event emitted when response generation fails"""

    type: ResponseEventType = Field(
        default=ResponseEventType.RESPONSE_FAILED, description="Event type"
    )
    sequence_number: int = Field(..., description="Event sequence number")
    response: ResponseInfo = Field(..., description="Failed response information")
    error: str = Field(..., description="Error message")


class ResponseErrorEvent(BaseModel):
    """Event emitted for errors during streaming"""

    type: ResponseEventType = Field(
        default=ResponseEventType.ERROR, description="Event type"
    )
    sequence_number: int = Field(..., description="Event sequence number")
    error: str = Field(..., description="Error message")


class ResponseSearchResultsEvent(BaseModel):
    """Event emitted when search results are available (Perplexity)"""

    type: ResponseEventType = Field(
        default=ResponseEventType.RESPONSE_SEARCH_RESULTS, description="Event type"
    )
    sequence_number: int = Field(..., description="Event sequence number")
    response_id: str = Field(..., description="Response ID")
    search_results: List[Dict[str, Any]] = Field(
        ..., description="Search results with URLs and metadata"
    )


# Union type for all possible response events
ResponseEvent = Union[
    ResponseCreatedEvent,
    ResponseInProgressEvent,
    ResponseOutputTextDeltaEvent,
    ResponseOutputTextDoneEvent,
    ResponseCompletedEvent,
    ResponseFailedEvent,
    ResponseErrorEvent,
    ResponseSearchResultsEvent,
]
