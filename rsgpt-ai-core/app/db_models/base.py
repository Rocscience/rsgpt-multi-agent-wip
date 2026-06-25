"""Base database model with common fields"""

import uuid as uuid_pkg
from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import DateTime, func
from sqlalchemy.dialects import postgresql as psql
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class BaseDbModel(DeclarativeBase):
    """Base model with common fields for all database tables"""

    __abstract__ = True

    id: Mapped[UUID] = mapped_column(
        psql.UUID(as_uuid=True), default=uuid_pkg.uuid4, primary_key=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        onupdate=func.now(),
        default=func.now(),
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), default=None, nullable=True
    )
