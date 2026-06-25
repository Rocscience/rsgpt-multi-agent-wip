"""Agent session models for SDK session persistence.

These models match the schema expected by the OpenAI Agent SDK's SQLAlchemySession.
Table names must match: 'agent_sessions' and 'agent_messages'.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from .base import BaseDbModel


class AgentSessionsORM(BaseDbModel):
    """
    Agent session tracking table.

    Matches the SDK's 'agent_sessions' table schema for SQLAlchemySession compatibility.
    Uses session_id as the primary key (matching SDK expectations).

    Also stores token tracking data for context window management:
    - last_input_tokens: Last known input token count from LLM response
    - last_model_name: Model used (for max token calculation)
    - token_updated_at: When tokens were last tracked
    """

    __tablename__ = "agent_sessions"

    # SDK uses session_id as the primary key (string)
    # Override the UUID id from BaseDbModel
    id = None  # type: ignore[assignment]
    session_id: Mapped[str] = mapped_column(String(255), primary_key=True)

    # Override timestamps to match SDK expectations (no timezone, CURRENT_TIMESTAMP default)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Token tracking for context window management
    last_input_tokens: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        default=None,
        comment="Last known input token count from LLM response",
    )
    last_model_name: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        default=None,
        comment="Model name used for max token calculation",
    )
    token_updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=False),
        nullable=True,
        default=None,
        comment="When token tracking was last updated",
    )

    # We don't use deleted_at from BaseDbModel for SDK compatibility
    deleted_at = None  # type: ignore[assignment]


class AgentMessagesORM(BaseDbModel):
    """
    Agent message storage table.

    Matches the SDK's 'agent_messages' table schema for SQLAlchemySession compatibility.
    Stores serialized message data as JSON text.
    """

    __tablename__ = "agent_messages"

    # SDK uses integer auto-increment id
    id = mapped_column(Integer, primary_key=True, autoincrement=True)  # type: ignore[assignment]
    session_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("agent_sessions.session_id", ondelete="CASCADE"),
        nullable=False,
    )
    message_data: Mapped[str] = mapped_column(Text, nullable=False)

    # Override timestamps to match SDK expectations
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        server_default=func.now(),
        nullable=False,
    )

    # No updated_at or deleted_at for messages
    updated_at = None  # type: ignore[assignment]
    deleted_at = None  # type: ignore[assignment]

    # Index for efficient session queries
    __table_args__ = (
        Index("idx_agent_messages_session_time", "session_id", "created_at"),
    )
