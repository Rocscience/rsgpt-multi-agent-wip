"""Quota request database models"""

from enum import Enum
from uuid import UUID

from sqlalchemy import String, Text, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import BaseDbModel


class QuotaRequestStatus(str, Enum):
    """Status of a quota request"""
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"


class QuotaRequestsORM(BaseDbModel):
    """Quota requests table - tracks user requests for additional agent quota"""
    __tablename__ = "quota_requests"
    
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), 
        nullable=False
    )
    requested_quota: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), 
        default=QuotaRequestStatus.PENDING.value, 
        nullable=False
    )
    
    # Relationships
    users_orm = relationship("UsersORM", backref="quota_requests_orm")
    
    def __repr__(self) -> str:
        return f"<QuotaRequestsORM(id={self.id}, user_id={self.user_id}, requested_quota={self.requested_quota}, status={self.status})>"
