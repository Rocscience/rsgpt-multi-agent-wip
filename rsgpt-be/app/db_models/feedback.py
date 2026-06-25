"""Feedback-related database models"""

from typing import Optional, TYPE_CHECKING
from uuid import UUID

from sqlalchemy import String, Text, ForeignKey, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import BaseDbModel

if TYPE_CHECKING:
    from .users import UsersORM
    from .chats import AIResponsesORM


class MessageFeedbackORM(BaseDbModel):
    """User feedback on AI responses"""
    __tablename__ = "message_feedback"
    
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), 
        nullable=False
    )
    ai_response_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("ai_responses.id", ondelete="SET NULL"), 
        nullable=True
    )
    feedback_type: Mapped[str] = mapped_column(
        Enum("positive", "negative", name="feedback_type"), 
        nullable=False
    )
    feedback_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Optional detailed feedback
    feedback_score: Mapped[Optional[int]] = mapped_column(nullable=True)  # 1 for positive, 0 for negative
    
    # Relationships
    users_orm: Mapped["UsersORM"] = relationship("UsersORM", back_populates="message_feedback_orm")
    ai_response_orm: Mapped[Optional["AIResponsesORM"]] = relationship("AIResponsesORM", back_populates="feedback_orm")
    
    def __repr__(self) -> str:
        return f"<MessageFeedbackORM(id={self.id}, user_id={self.user_id}, type={self.feedback_type})>"