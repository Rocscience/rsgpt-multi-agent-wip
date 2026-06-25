"""User-related database models"""

from datetime import datetime
from typing import Optional, TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Boolean, String, Text, ForeignKey, JSON, DateTime, Integer, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.consts import DEFAULT_AGENT_QUOTA
from .base import BaseDbModel

if TYPE_CHECKING:
    from .organizations import UserOrganizationsORM
    from .chats import ChatSessionsORM
    from .feedback import MessageFeedbackORM
    from .devices import DevicesORM


class UsersORM(BaseDbModel):
    """Users table - Auth0 authenticated users"""
    __tablename__ = "users"
    
    auth0_sub: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)  # Full Auth0 subject
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    first_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    last_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    profile_picture_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_login: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # Store as ISO string
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    agent_quota: Mapped[int] = mapped_column(Integer, default=DEFAULT_AGENT_QUOTA, nullable=False)
    agent_quota_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    
    # Relationships
    settings_orm: Mapped[Optional["UserSettingsORM"]] = relationship(
        "UserSettingsORM", 
        back_populates="users_orm", 
        uselist=False, 
        cascade="all, delete-orphan"
    )
    organizations_orm: Mapped[list["UserOrganizationsORM"]] = relationship(
        "UserOrganizationsORM", 
        back_populates="users_orm", 
        cascade="all, delete-orphan"
    )
    chat_sessions_orm: Mapped[list["ChatSessionsORM"]] = relationship(
        "ChatSessionsORM", 
        back_populates="users_orm", 
        cascade="all, delete-orphan"
    )
    message_feedback_orm: Mapped[list["MessageFeedbackORM"]] = relationship(
        "MessageFeedbackORM", 
        back_populates="users_orm", 
        cascade="all, delete-orphan"
    )
    devices_orm: Mapped[list["DevicesORM"]] = relationship(
        "DevicesORM", 
        back_populates="users_orm", 
        cascade="all, delete-orphan"
    )
    rslog_settings_orm: Mapped[Optional["RSLogUserSettingsORM"]] = relationship(
        "RSLogUserSettingsORM", 
        back_populates="users_orm", 
        uselist=False, 
        cascade="all, delete-orphan"
    )
    
    def __repr__(self) -> str:
        return f"<UsersORM(id={self.id}, email={self.email})>"


class UserSettingsORM(BaseDbModel):
    """User settings table"""
    __tablename__ = "user_settings"
    
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), 
        nullable=False, 
        unique=True
    )
    theme: Mapped[str] = mapped_column(String(10), default="light", nullable=False)  # 'light' or 'dark'
    preferred_sources: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # Array of preferred knowledge sources
    language: Mapped[str] = mapped_column(String(10), default="en", nullable=False)
    timezone: Mapped[str] = mapped_column(String(50), default="UTC", nullable=False)
    agent_mode_opt_in: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)  # User consent for agent mode data collection
    
    # Relationships
    users_orm: Mapped["UsersORM"] = relationship("UsersORM", back_populates="settings_orm")
    
    def __repr__(self) -> str:
        return f"<UserSettingsORM(user_id={self.user_id}, theme={self.theme})>"


class AgentModeOptInHistoryORM(BaseDbModel):
    """Tracks changes to user's agent mode opt-in status for compliance/audit purposes"""
    __tablename__ = "agent_mode_opt_in_history"
    
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )
    opt_in_status: Mapped[bool] = mapped_column(Boolean, nullable=False)  # True = opted in, False = opted out
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)  # When the user changed their preference
    
    # Relationships
    users_orm: Mapped["UsersORM"] = relationship("UsersORM", backref="opt_in_history_orm")
    
    # Indexes for efficient querying
    __table_args__ = (
        Index('ix_agent_mode_opt_in_history_user_id', 'user_id'),
        Index('ix_agent_mode_opt_in_history_changed_at', 'changed_at'),
    )
    
    def __repr__(self) -> str:
        return f"<AgentModeOptInHistoryORM(user_id={self.user_id}, opt_in_status={self.opt_in_status}, changed_at={self.changed_at})>"


class RSLogUserSettingsORM(BaseDbModel):
    """RSLog user settings table - stores RSLog connection credentials and tokens"""
    __tablename__ = "rslog_user_settings"
    
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), 
        nullable=False, 
        unique=True
    )
    company: Mapped[str] = mapped_column(String(255), nullable=False)  # RSLog company/tenant name
    username: Mapped[str] = mapped_column(String(255), nullable=False)  # RSLog username/email
    access_token: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Encrypted access token
    refresh_token: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Encrypted refresh token
    expires_in: Mapped[Optional[int]] = mapped_column(nullable=True)  # Token expiry in seconds
    token_created_at: Mapped[Optional[DateTime]] = mapped_column(DateTime(timezone=True), nullable=True)  # When token was created
    is_connected: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)  # Connection status
    
    # Relationships
    users_orm: Mapped["UsersORM"] = relationship("UsersORM", back_populates="rslog_settings_orm")
    
    def __repr__(self) -> str:
        return f"<RSLogUserSettingsORM(user_id={self.user_id}, company={self.company}, is_connected={self.is_connected})>" 