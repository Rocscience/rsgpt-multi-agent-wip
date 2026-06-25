from typing import Optional, List, Any, Dict
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from zoneinfo import ZoneInfo


def convert_datetime_to_gmt(dt: datetime) -> str:
    """Convert datetime to GMT string format"""
    if not dt.tzinfo:
        dt = dt.replace(tzinfo=ZoneInfo("UTC"))
    return dt.strftime("%Y-%m-%dT%H:%M:%S%z")


class CreateChatSessionRequest(BaseModel):
    title: Optional[str] = Field(None, description="Optional title for the chat session")


class CreateChatSessionResponse(BaseModel):
    """Response model for creating a chat session"""
    model_config = ConfigDict(json_encoders={datetime: convert_datetime_to_gmt})
    
    id: UUID = Field(..., description="Chat session ID")
    user_id: UUID = Field(..., description="User ID")
    title: str = Field(..., description="Chat session title")
    message_count: int = Field(..., description="Number of messages in session")


class GetChatSessionMetaResponse(BaseModel):
    """Response model for chat session metadata"""
    model_config = ConfigDict(json_encoders={datetime: convert_datetime_to_gmt})
    
    user_id: UUID = Field(..., description="User ID")
    chat_session_id: UUID = Field(..., description="Chat session ID")
    title: str = Field(..., description="Chat session title")
    message_count: int = Field(..., description="Number of messages in session")
    created_at: datetime = Field(..., description="Session creation timestamp")
    updated_at: datetime = Field(..., description="Session last update timestamp")


class GetChatSessionsListResponse(BaseModel):
    """Response model for list of chat sessions"""
    sessions: List[GetChatSessionMetaResponse] = Field(..., description="List of chat sessions")
    total_count: int = Field(..., description="Total number of sessions")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Number of items per page")
    total_pages: int = Field(..., description="Total number of pages")
    has_next: bool = Field(..., description="Whether there are more pages")
    has_previous: bool = Field(..., description="Whether there are previous pages")

class StreamPromptRequest(BaseModel):
    """Request model for streaming a prompt completion."""
    model_config = ConfigDict(protected_namespaces=())
    
    prompt: str = Field(
        ...,
        description="User prompt.",
    )
    source_selections: List[str] = Field(..., description="List of source selections for the prompt.")
    client_temp_id: str = Field(..., description="Client-generated temporary ID for message reconciliation (UUID format)")
    idempotency_key: str = Field(..., description="Idempotency key for request deduplication (UUID` format)")
    provider_name: Optional[str] = Field(default=None, description="Provider name (e.g., 'openai', 'anthropic/claude-sonnet-4-5', 'perplexity')")
    model_name: str = Field(..., description="Model choice for request")
    is_agent_mode: bool = Field(default=False, description="Whether to use agent mode with tool calling")
    device_id: Optional[str] = Field(default=None, description="Device ID for device-specific tool operations")
    is_web_search_enabled: bool = Field(default=False, description="Whether to enable web search capabilities")
    reasoning: Optional[str] = Field(default=None, description="Reasoning level for GPT-5 (minimal, medium, high)")

class MediaImage(BaseModel):
    """Media image with source"""
    image_url: str = Field(..., description="URL of the image")
    source_url: str = Field(..., description="URL of the source page where image was found")

class MediaData(BaseModel):
    """Media data"""
    images: List[MediaImage] = Field(default_factory=list, description="Images with their source URLs")

class UserMessageDto(BaseModel):
    """Data transfer object for user messages"""
    model_config = ConfigDict(json_encoders={datetime: convert_datetime_to_gmt})
    
    id: UUID = Field(..., description="User message ID")
    message_text: str = Field(..., description="User's message text")
    status: str = Field(..., description="Message status")
    sources_requested: List[str] = Field(..., description="Sources requested by user")
    created_at: datetime = Field(..., description="When the message was created")
    client_temp_id: Optional[str] = Field(None, description="Client temporary ID")
    idempotency_key: Optional[str] = Field(None, description="Idempotency key")


class AIResponseDto(BaseModel):
    """Data transfer object for AI responses"""
    model_config = ConfigDict(json_encoders={datetime: convert_datetime_to_gmt}, protected_namespaces=())
    
    id: UUID = Field(..., description="AI response ID")
    message_text: str = Field(..., description="AI response text")
    status: str = Field(..., description="Response status")
    response_time_ms: Optional[int] = Field(None, description="Response time in milliseconds")
    model_used: str = Field(..., description="Model used for this response")
    sources_used: List[str] = Field(..., description="Sources used for this response")
    media_links: MediaData = Field(..., description="Media links (images, documents, etc.)")
    search_results: Optional[List[Dict[str, Any]]] = Field(None, description="Search results from web search")
    token_count: Optional[int] = Field(None, description="Token count")
    run_id: Optional[str] = Field(None, description="AI service run ID")
    trace_id: Optional[str] = Field(None, description="OpenAI Agent SDK trace ID for multi-agent workflows")
    created_at: datetime = Field(..., description="When the response was created")
    is_latest: bool = Field(..., description="Whether this is the latest response for the user message")
    is_agent_mode: bool = Field(default=False, description="Whether agent mode was used for this response")
    timeline: Optional[Dict[str, Any]] = Field(None, description="Coalesced timeline of blocks (thinking, messages, tool executions) as JSON")
    usage_breakdown: Optional[List[Dict[str, Any]]] = Field(None, description="Per-request usage breakdown (NEW in openai-agents v0.5.0)")


class ConversationTurnDto(BaseModel):
    """A conversation turn containing a user message and its AI responses"""
    user_message: UserMessageDto = Field(..., description="The user message")
    ai_responses: List[AIResponseDto] = Field(..., description="All AI responses for this message")
    has_retries: bool = Field(..., description="Whether this turn has retry attempts")


class GetConversationHistoryResponse(BaseModel):
    """Response model for hierarchical conversation history"""
    conversation: List[ConversationTurnDto] = Field(..., description="Conversation turns")
    total_count: int = Field(..., description="Total number of conversation turns")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Number of items per page")
    total_pages: int = Field(..., description="Total number of pages")
    has_next: bool = Field(..., description="Whether there are more pages")
    has_previous: bool = Field(..., description="Whether there are previous pages")
    current_token_count: int = Field(..., description="Current usage of the chat session")

class RetryUserPromptResponse(BaseModel):
    """Response model for retrying a user prompt"""
    success: bool = Field(..., description="Whether the retry was successful")
    ai_response_id: UUID = Field(..., description="ID of the new AI response")
    user_message_id: UUID = Field(..., description="ID of the user message being retried")
    status: str = Field(..., description="Status of the new AI response")
    message: str = Field(..., description="Success message")


# SSE Event Models for Hybrid Init-in-Stream

class UserMessageInitEvent(BaseModel):
    """SSE event for user message initialization"""
    client_temp_id: str = Field(..., description="Client's temporary ID")
    server_id: str = Field(..., description="Server's canonical message ID")
    conversation_id: str = Field(..., description="Conversation/session ID")


class AssistantMessageInitEvent(BaseModel):
    """SSE event for assistant message initialization"""
    server_id: str = Field(..., description="Server's canonical assistant message ID")
    conversation_id: str = Field(..., description="Conversation/session ID")


class AssistantDeltaEvent(BaseModel):
    """SSE event for assistant message delta/chunk"""
    server_id: str = Field(..., description="Server's canonical assistant message ID")
    seq: int = Field(..., description="Sequence number for ordering")
    text: str = Field(..., description="Text chunk/delta")


class AssistantCompletedEvent(BaseModel):
    """SSE event for assistant message completion"""
    server_id: str = Field(..., description="Server's canonical assistant message ID")
    token_count: Optional[int] = Field(None, description="Total token count")
    finish_reason: str = Field(..., description="Reason for completion (stop, length, etc.)")
    checksum: Optional[str] = Field(None, description="SHA256 checksum of complete text")


class StreamErrorEvent(BaseModel):
    """SSE event for stream errors"""
    error: str = Field(..., description="Error message")
    assistant_server_id: Optional[str] = Field(None, description="Assistant message ID if applicable")


class MediaSearchStartEvent(BaseModel):
    """SSE event for when media search begins"""
    server_id: str = Field(..., description="Server's canonical assistant message ID")


class MediaSearchCompletedEvent(BaseModel):
    """SSE event for when media search completes with results"""
    server_id: str = Field(..., description="Server's canonical assistant message ID")
    media_data: dict = Field(..., description="Media search results (images, videos, etc.)")