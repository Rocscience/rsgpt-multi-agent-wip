"""System-related database models"""

from typing import Optional
from uuid import UUID

from sqlalchemy import String, Text, JSON, Boolean, Integer
from sqlalchemy.orm import Mapped, mapped_column

from .base import BaseDbModel


class SystemConfigORM(BaseDbModel):
    """System configuration table"""
    __tablename__ = "system_config"
    
    config_key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    config_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    config_type: Mapped[str] = mapped_column(String(50), default="string", nullable=False)  # string, json, boolean, integer
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    def __repr__(self) -> str:
        return f"<SystemConfigORM(key={self.config_key}, type={self.config_type})>"


class ErrorLogsORM(BaseDbModel):
    """Error logging table"""
    __tablename__ = "error_logs"
    
    error_type: Mapped[str] = mapped_column(String(100), nullable=False)
    error_message: Mapped[str] = mapped_column(Text, nullable=False)
    error_details: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # Stack trace, request details, etc.
    user_id: Mapped[Optional[UUID]] = mapped_column(nullable=True)  # User who encountered the error (if applicable)
    session_id: Mapped[Optional[UUID]] = mapped_column(nullable=True)  # Chat session if related to chat
    request_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)  # API endpoint that caused the error
    request_method: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)  # HTTP method
    status_code: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # HTTP status code
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)  # IPv4 or IPv6
    user_agent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    def __repr__(self) -> str:
        return f"<ErrorLogsORM(id={self.id}, type={self.error_type}, resolved={self.resolved})>"