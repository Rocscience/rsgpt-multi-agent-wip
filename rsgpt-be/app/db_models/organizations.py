"""Organization-related database models"""

from datetime import date
from typing import Optional, TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Boolean, Date, String, Integer, ForeignKey, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import BaseDbModel

if TYPE_CHECKING:
    from .users import UsersORM


class OrganizationsORM(BaseDbModel):
    """Organizations table - RocPortal organizations"""
    __tablename__ = "organizations"
    
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    question_quota: Mapped[int] = mapped_column(Integer, default=20, nullable=False)  # Total questions allowed per month
    questions_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # Questions used this month
    access_level: Mapped[str] = mapped_column(
        Enum("BASIC", "FLEXIBLE", name="access_level"), 
        default="BASIC", 
        nullable=False
    )
    quota_reset_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)  # When quota resets (monthly)
    rocportal_status: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    user_organizations_orm: Mapped[list["UserOrganizationsORM"]] = relationship(
        "UserOrganizationsORM", 
        back_populates="organizations_orm", 
        cascade="all, delete-orphan"
    )
    
    def __repr__(self) -> str:
        return f"<OrganizationsORM(id={self.id}, name={self.name})>"


class UserOrganizationsORM(BaseDbModel):
    """User-Organization relationship table"""
    __tablename__ = "user_organizations"
    
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), 
        nullable=False
    )
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), 
        nullable=False
    )

    # Relationships
    users_orm: Mapped["UsersORM"] = relationship("UsersORM", back_populates="organizations_orm")
    organizations_orm: Mapped["OrganizationsORM"] = relationship("OrganizationsORM", back_populates="user_organizations_orm")
    
    def __repr__(self) -> str:
        return f"<UserOrganizationsORM(user_id={self.user_id}, org_id={self.organization_id})>"
