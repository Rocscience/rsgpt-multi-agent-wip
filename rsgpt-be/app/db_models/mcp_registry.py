"""MCP Registry database models"""

from typing import Optional, TYPE_CHECKING
from uuid import UUID
from datetime import datetime

from sqlalchemy import (
    Boolean, String, Text, ForeignKey, JSON, Integer, Index, DateTime, BigInteger
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import BaseDbModel

if TYPE_CHECKING:
    from .mcp_install_logs import MCPInstallLogsORM

class MCPRegistryORM(BaseDbModel):
    """MCP Registry table - stores available MCP servers for installation"""
    __tablename__ = "mcp_registry"

    # Core fields
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    category: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # 'dev-tools', 'data-analysis', 'automation'
    author: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Repository and versioning
    repo_url: Mapped[str] = mapped_column(String(500), nullable=False)
    latest_version: Mapped[str] = mapped_column(String(20), nullable=False)  # semver: "1.2.3"
    min_app_version: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # minimum Electron app version

    # Download information
    checksum_sha256: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    # S3 Storage (required)
    s3_bucket: Mapped[str] = mapped_column(String(255), nullable=False)  # e.g., "rsinsight-mcp-releases-staging"
    s3_key: Mapped[str] = mapped_column(Text, nullable=False)  # e.g., "rs2-server/v1.0.0/rs2-server-v1.0.0.exe"

    # Metadata
    release_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    downloads_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_official: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    extra_metadata: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)  # flexible field for extra info

    # Rocscience application version compatibility
    rocscience_app: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # e.g., "RS2", "RSPile", "Slide2"
    required_app_version: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # e.g., "11.0.2.7"
    rocscience_app_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)  # e.g., "C:\Program Files\Rocscience\RS2\RS2.exe"

    # Relationships
    versions_orm: Mapped[list["MCPVersionsORM"]] = relationship(
        "MCPVersionsORM",
        back_populates="mcp_registry_orm",
        cascade="all, delete-orphan"
    )
    install_logs: Mapped[list["MCPInstallLogsORM"]] = relationship(
        "MCPInstallLogsORM",
        back_populates="mcp",
        cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<MCPRegistryORM(id={self.id}, name={self.name}, version={self.latest_version})>"


class MCPVersionsORM(BaseDbModel):
    """MCP Versions table - stores historical versions of MCP servers"""
    __tablename__ = "mcp_versions"

    mcp_id: Mapped[UUID] = mapped_column(
        ForeignKey("mcp_registry.id", ondelete="CASCADE"),
        nullable=False
    )
    version: Mapped[str] = mapped_column(String(20), nullable=False)
    checksum_sha256: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    # S3 Storage (required)
    s3_bucket: Mapped[str] = mapped_column(String(255), nullable=False)
    s3_key: Mapped[str] = mapped_column(Text, nullable=False)
    file_size: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)  # bytes, for presigned URL expiration calc

    release_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    release_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    mcp_registry_orm: Mapped["MCPRegistryORM"] = relationship(
        "MCPRegistryORM",
        back_populates="versions_orm"
    )

    # Add indexes
    __table_args__ = (
        Index('idx_mcp_version_unique', 'mcp_id', 'version', unique=True),
        Index('idx_mcp_versions_mcp_id', 'mcp_id'),
    )

    def __repr__(self) -> str:
        return f"<MCPVersionsORM(mcp_id={self.mcp_id}, version={self.version})>"


# Create indexes on the MCPRegistry table
Index('idx_mcp_category', MCPRegistryORM.category)
Index('idx_mcp_active', MCPRegistryORM.is_active)
