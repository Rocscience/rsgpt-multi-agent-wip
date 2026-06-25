"""Chat-related database models"""

from typing import Optional, TYPE_CHECKING
from uuid import UUID
import enum

from sqlalchemy import Boolean, String, Text, Integer, ForeignKey, Enum, TIMESTAMP, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import BaseDbModel

if TYPE_CHECKING:
    from .users import UsersORM
    from .feedback import MessageFeedbackORM


class MessageStatus(enum.Enum):
    """Message processing status"""
    SUBMITTED = "submitted"
    STREAMING = "streaming"
    COMPLETED = "completed"
    ERRORED = "errored"
    CANCELLED = "cancelled"

class ChatSessionsORM(BaseDbModel):
    """Chat sessions table"""
    __tablename__ = "chat_sessions"
    
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), 
        nullable=False
    )
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # Auto-generated or user-set title
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    message_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    current_token_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # Current total token count for the session
    
    # Relationships
    users_orm: Mapped["UsersORM"] = relationship("UsersORM", back_populates="chat_sessions_orm")
    user_messages_orm: Mapped[list["UserMessagesORM"]] = relationship(
        "UserMessagesORM",
        back_populates="chat_sessions_orm",
        cascade="all, delete-orphan",
        order_by="UserMessagesORM.created_at"
    )
    ai_responses_orm: Mapped[list["AIResponsesORM"]] = relationship(
        "AIResponsesORM",
        back_populates="chat_sessions_orm",
        cascade="all, delete-orphan",
        order_by="AIResponsesORM.created_at"
    )
    def __repr__(self) -> str:
        return f"<ChatSessionsORM(id={self.id}, user_id={self.user_id}, title={self.title})>"


class UserMessagesORM(BaseDbModel):
    """User messages table"""
    __tablename__ = "user_messages"
    
    session_id: Mapped[UUID] = mapped_column(
        ForeignKey("chat_sessions.id", ondelete="CASCADE"), 
        nullable=False
    )
    message_text: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[MessageStatus] = mapped_column(Enum(MessageStatus), nullable=False, default=MessageStatus.SUBMITTED)
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, unique=True)  # UUID/ULID for idempotency
    client_temp_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)  # Client-generated temp ID for reconciliation
    sources_requested: Mapped[Optional[list[str]]] = mapped_column(ARRAY(String), nullable=True)  # Sources user requested
    model_requested: Mapped[str] = mapped_column(String(255), nullable=False, default="gpt-4.1-2025-04-14")  # Model user requested
    device_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # Device ID for device-specific operations
    
    # Relationships
    chat_sessions_orm: Mapped["ChatSessionsORM"] = relationship("ChatSessionsORM", back_populates="user_messages_orm")
    ai_responses_orm: Mapped[list["AIResponsesORM"]] = relationship(
        "AIResponsesORM", 
        back_populates="user_message_orm", 
        cascade="all, delete-orphan"
    )
    
    def __repr__(self) -> str:
        return f"<UserMessagesORM(id={self.id}, session_id={self.session_id})>"


class AIResponsesORM(BaseDbModel):
    """AI responses table"""
    __tablename__ = "ai_responses"
    
    user_message_id: Mapped[UUID] = mapped_column(
        ForeignKey("user_messages.id", ondelete="CASCADE"), 
        nullable=False
    )
    session_id: Mapped[UUID] = mapped_column(
        ForeignKey("chat_sessions.id", ondelete="CASCADE"), 
        nullable=False
    )
    message_text: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[MessageStatus] = mapped_column(Enum(MessageStatus), nullable=False, default=MessageStatus.STREAMING)
    response_time_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # Response time for AI messages
    sources_used: Mapped[Optional[list[str]]] = mapped_column(ARRAY(String), nullable=True)  # Sources used for this response
    media_links: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)  # Media links (images, documents, etc.) stored as JSON
    search_results: Mapped[Optional[list[dict]]] = mapped_column(JSONB, nullable=True)  # Search results from web search (Perplexity, etc.)
    token_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # Token count for AI response
    run_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # AI service run ID
    trace_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # OpenAI Agent SDK trace ID for multi-agent workflows
    model_used: Mapped[str] = mapped_column(String(255), nullable=False, default="gpt-4.1-2025-04-14")  # Model used for this response
    is_agent_mode: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)  # Whether agent mode was used
    device_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # Device ID for device-specific operations
    reasoning_level: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # Reasoning level (minimal, medium, high)
    timeline: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)  # Coalesced timeline blocks (thinking, messages, tool executions) as JSON
    usage_breakdown: Mapped[Optional[list[dict]]] = mapped_column(JSONB, nullable=True)  # Per-request usage breakdown (NEW in openai-agents v0.5.0)

    # Relationships
    user_message_orm: Mapped["UserMessagesORM"] = relationship("UserMessagesORM", back_populates="ai_responses_orm")
    chat_sessions_orm: Mapped["ChatSessionsORM"] = relationship("ChatSessionsORM", back_populates="ai_responses_orm")
    feedback_orm: Mapped[list["MessageFeedbackORM"]] = relationship(
        "MessageFeedbackORM", 
        back_populates="ai_response_orm", 
        cascade="all, delete-orphan"
    )
    
    def __repr__(self) -> str:
        return f"<AIResponsesORM(id={self.id}, user_message_id={self.user_message_id}, session_id={self.session_id})>"