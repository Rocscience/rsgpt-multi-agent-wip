"""Database models for MCP installation logs"""

from sqlalchemy import String, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db_models.base import BaseDbModel
from uuid import UUID
from datetime import datetime


class MCPInstallLogsORM(BaseDbModel):
    """Track MCP installations, updates, and uninstalls per device"""
    __tablename__ = "mcp_install_logs"

    # Foreign keys
    mcp_id: Mapped[UUID] = mapped_column(ForeignKey("mcp_registry.id", ondelete="CASCADE"), nullable=False)
    device_id: Mapped[UUID] = mapped_column(ForeignKey("devices.id", ondelete="CASCADE"), nullable=False)

    # Installation details
    version: Mapped[str] = mapped_column(String(20), nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False, default="install")  # install, update, uninstall
    installed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    # Relationships
    mcp: Mapped["MCPRegistryORM"] = relationship(back_populates="install_logs")
    device: Mapped["DevicesORM"] = relationship(back_populates="mcp_install_logs")