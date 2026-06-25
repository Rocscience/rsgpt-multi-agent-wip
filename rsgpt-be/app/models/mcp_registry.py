"""Pydantic models for MCP Registry API"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime


# Request Models
class MCPRegistryListRequest(BaseModel):
    """Request model for listing MCP registries"""
    category: Optional[str] = Field(None, description="Filter by category")
    search: Optional[str] = Field(None, description="Search by name/description")
    official_only: Optional[bool] = Field(False, description="Show only official MCPs")
    page: int = Field(1, ge=1, description="Page number")
    limit: int = Field(20, ge=1, le=100, description="Items per page")


class MCPInstallLogRequest(BaseModel):
    """Request model for logging MCP installation"""
    mcp_id: UUID = Field(..., description="MCP registry ID")
    device_id: UUID = Field(..., description="Device ID")
    version: str = Field(..., description="Version being installed")
    action: str = Field("install", description="Action type: install, update, uninstall")


class MCPRegistryCreate(BaseModel):
    """Request model for creating a new MCP registry entry"""
    name: str = Field(..., description="Unique MCP name")
    display_name: str = Field(..., description="Display name")
    description: Optional[str] = Field(None, description="MCP description")
    category: Optional[str] = Field(None, description="Category")
    author: Optional[str] = Field(None, description="Author name")
    repo_url: str = Field(..., description="Repository URL")
    latest_version: str = Field(..., description="Latest version")
    min_app_version: Optional[str] = Field(None, description="Minimum app version required")
    checksum_sha256: Optional[str] = Field(None, description="SHA256 checksum")
    release_date: Optional[datetime] = Field(None, description="Release date")
    is_official: bool = Field(False, description="Is official MCP")
    is_active: bool = Field(True, description="Is active")
    extra_metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")

    # S3 Storage fields (required)
    s3_bucket: str = Field(..., description="S3 bucket name")
    s3_key: str = Field(..., description="S3 object key")

    # Rocscience application version compatibility (optional)
    rocscience_app: Optional[str] = Field(None, description="Rocscience app name (e.g., RS2, RSPile)")
    required_app_version: Optional[str] = Field(None, description="Required Rocscience app version (e.g., 11.0.2.7)")
    rocscience_app_path: Optional[str] = Field(None, description="Default path to Rocscience app executable")


class MCPRegistryUpdate(BaseModel):
    """Request model for updating an MCP registry entry"""
    display_name: Optional[str] = Field(None, description="Display name")
    description: Optional[str] = Field(None, description="MCP description")
    category: Optional[str] = Field(None, description="Category")
    author: Optional[str] = Field(None, description="Author name")
    repo_url: Optional[str] = Field(None, description="Repository URL")
    latest_version: Optional[str] = Field(None, description="Latest version")
    min_app_version: Optional[str] = Field(None, description="Minimum app version required")
    checksum_sha256: Optional[str] = Field(None, description="SHA256 checksum")
    release_date: Optional[datetime] = Field(None, description="Release date")
    is_official: Optional[bool] = Field(None, description="Is official MCP")
    is_active: Optional[bool] = Field(None, description="Is active")
    extra_metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")

    # S3 Storage fields
    s3_bucket: Optional[str] = Field(None, description="S3 bucket name")
    s3_key: Optional[str] = Field(None, description="S3 object key")

    # Rocscience application version compatibility (optional)
    rocscience_app: Optional[str] = Field(None, description="Rocscience app name (e.g., RS2, RSPile)")
    required_app_version: Optional[str] = Field(None, description="Required Rocscience app version (e.g., 11.0.2.7)")
    rocscience_app_path: Optional[str] = Field(None, description="Default path to Rocscience app executable")


# Response Models
class MCPRegistrySummary(BaseModel):
    """Summary model for MCP registry listing"""
    id: UUID
    name: str
    display_name: str
    description: Optional[str]
    category: Optional[str]
    author: Optional[str]
    latest_version: str
    downloads_count: int
    is_official: bool
    # Rocscience application version compatibility (for desktop app to check before install)
    rocscience_app: Optional[str] = Field(None, description="Rocscience app name (e.g., RS2, RSPile)")
    required_app_version: Optional[str] = Field(None, description="Required Rocscience app version (e.g., 11.0.2.7)")
    rocscience_app_path: Optional[str] = Field(None, description="Default path to Rocscience app executable")

    class Config:
        from_attributes = True


class MCPVersionInfo(BaseModel):
    """Model for MCP version information"""
    version: str
    release_date: Optional[datetime]
    release_notes: Optional[str]

    class Config:
        from_attributes = True


class MCPRegistryDetailResponse(BaseModel):
    """Detailed response model for a single MCP registry"""
    id: UUID
    name: str
    display_name: str
    description: Optional[str]
    category: Optional[str]
    author: Optional[str]
    repo_url: str
    latest_version: str
    checksum_sha256: Optional[str]
    min_app_version: Optional[str]
    release_date: Optional[datetime]
    downloads_count: int
    is_official: bool
    is_active: bool
    metadata: Dict[str, Any]
    versions: List[MCPVersionInfo]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class MCPRegistryListResponse(BaseModel):
    """Response model for MCP registry listing"""
    mcps: List[MCPRegistrySummary]
    total: int
    page: int
    pages: int

    class Config:
        from_attributes = True


class S3DownloadResponse(BaseModel):
    """Generic response model for S3 presigned URL download information.

    Used for both MCP server downloads and desktop app downloads.
    """
    download_url: str
    checksum_sha256: Optional[str]
    filename: str
    size_bytes: Optional[int]

    class Config:
        from_attributes = True


# Alias for backwards compatibility
MCPDownloadResponse = S3DownloadResponse


class MCPInstallLogResponse(BaseModel):
    """Response model for MCP installation log"""
    id: UUID
    mcp_id: UUID
    device_id: UUID
    version: str
    action: str
    installed_at: datetime
    message: str

    class Config:
        from_attributes = True


# Registration Models (for GitHub Actions to register/update MCPs)
class MCPRegistryRegisterRequest(BaseModel):
    """Request model for registering or updating an MCP from GitHub Actions"""
    name: str = Field(..., description="Unique MCP identifier (lowercase, hyphens only)")
    display_name: str = Field(..., description="Human-readable display name")
    description: str = Field(..., description="MCP description")
    category: str = Field(..., description="Category: dev-tools, automation, data-analysis")
    author: str = Field(..., description="Author or organization name")
    repo_url: str = Field(..., description="GitHub repository URL")
    version: str = Field(..., description="Semantic version (e.g., 1.2.0)")
    min_app_version: Optional[str] = Field(None, description="Minimum desktop app version required")
    checksums: Dict[str, str] = Field(..., description="Platform-specific SHA256 checksums")
    release_notes: Optional[str] = Field(None, description="Release notes for this version")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata (requirements, permissions, etc)")
    is_official: bool = Field(False, description="Mark as official RSInsight MCP")

    # S3 Storage fields (required)
    s3_bucket: str = Field(..., description="S3 bucket name (e.g., rsinsight-mcp-releases-staging)")
    s3_key: str = Field(..., description="S3 object key (e.g., rs2-server/v1.0.0/rs2-server-v1.0.0.exe)")
    file_size: Optional[int] = Field(None, description="File size in bytes (for presigned URL expiration calculation)")

    # Rocscience application version compatibility (optional)
    rocscience_app: Optional[str] = Field(None, description="Rocscience app name (e.g., RS2, RSPile, Slide2)")
    required_app_version: Optional[str] = Field(None, description="Required Rocscience app version (e.g., 11.0.2.7)")
    rocscience_app_path: Optional[str] = Field(None, description="Default path to Rocscience app executable")

    class Config:
        json_schema_extra = {
            "example": {
                "name": "rs2-server",
                "display_name": "RS2 MCP Server",
                "description": "MCP server for RS2 integration",
                "category": "automation",
                "author": "RSInsight",
                "repo_url": "https://github.com/rsinsight/rs2-mcp",
                "version": "1.2.0",
                "min_app_version": "1.0.0",
                "checksums": {
                    "windows": "abc123...",
                    "macos": "def456...",
                    "linux": "ghi789..."
                },
                "s3_bucket": "rsinsight-mcp-releases-staging",
                "s3_key": "rs2-server/v1.2.0/rs2-server-v1.2.0.exe",
                "file_size": 25000000,
                "release_notes": "- Added feature X\n- Fixed bug Y",
                "metadata": {
                    "requirements": ["Python 3.11+"],
                    "permissions": ["network.outbound", "file.read"]
                },
                "is_official": True,
                "rocscience_app": "RS2",
                "required_app_version": "11.0.2.7",
                "rocscience_app_path": "C:\\Program Files\\Rocscience\\RS2\\RS2.exe"
            }
        }


class MCPRegistryRegisterResponse(BaseModel):
    """Response model for MCP registration"""
    success: bool = Field(..., description="Whether the registration was successful")
    mcp_id: Optional[UUID] = Field(None, description="UUID of the registered/updated MCP")
    message: str = Field(..., description="Success or error message")
    action: Optional[str] = Field(None, description="Action taken: 'created' or 'updated'")
    error: Optional[str] = Field(None, description="Error type if failed")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "success": True,
                    "mcp_id": "123e4567-e89b-12d3-a456-426614174000",
                    "message": "MCP registered successfully",
                    "action": "created"
                },
                {
                    "success": False,
                    "error": "Version not newer",
                    "message": "Version 1.0.0 is not newer than current version 1.1.0",
                    "details": {
                        "current_version": "1.1.0",
                        "provided_version": "1.0.0"
                    }
                }
            ]
        }