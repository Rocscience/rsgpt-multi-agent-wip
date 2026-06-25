"""Device-related database models"""

from typing import Optional, TYPE_CHECKING
from uuid import UUID
import enum

from sqlalchemy import Boolean, String, Text, ForeignKey, Enum
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import BaseDbModel

if TYPE_CHECKING:
    from .users import UsersORM
    from .mcp_install_logs import MCPInstallLogsORM


class DeviceType(enum.Enum):
    """Device type enumeration"""
    MACOS = "macos"
    WINDOWS = "windows"


class DevicesORM(BaseDbModel):
    """Devices table - tracks user devices and their metadata"""
    __tablename__ = "devices"
    
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), 
        nullable=False
    )
    device_token: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)  # Client-generated UUID
    device_name: Mapped[str] = mapped_column(String(255), nullable=False)
    device_type: Mapped[DeviceType] = mapped_column(Enum(DeviceType), nullable=False)
    os_name: Mapped[str] = mapped_column(String(50), nullable=False)
    os_version: Mapped[str] = mapped_column(String(50), nullable=False)
    app_version: Mapped[str] = mapped_column(String(50), nullable=False)
    mcp_servers: Mapped[Optional[list[str]]] = mapped_column(ARRAY(String), nullable=True)  # List of installed MCP servers
    last_active: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # ISO timestamp
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    # Relationships
    users_orm: Mapped["UsersORM"] = relationship("UsersORM", back_populates="devices_orm")
    mcp_install_logs: Mapped[list["MCPInstallLogsORM"]] = relationship("MCPInstallLogsORM", back_populates="device")
    
    def __repr__(self) -> str:
        return f"<DevicesORM(id={self.id}, device_name={self.device_name}, user_id={self.user_id})>"

