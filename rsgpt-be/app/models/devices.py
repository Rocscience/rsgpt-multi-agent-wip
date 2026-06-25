"""Device-related API models"""

from datetime import datetime
from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel, Field


class RegisterDeviceRequest(BaseModel):
    """Request model for registering a device"""
    device_token: str = Field(..., description="Client-generated device UUID")
    device_name: str = Field(..., description="Human-readable device name")
    device_type: str = Field(..., description="Device type: macos or windows")
    os_name: str = Field(..., description="Operating system name")
    os_version: str = Field(..., description="Operating system version")
    app_version: str = Field(..., description="Application version")
    mcp_servers: Optional[List[str]] = Field(None, description="List of installed MCP servers")


class RegisterDeviceResponse(BaseModel):
    """Response model for registering a device"""
    device_id: UUID = Field(..., description="Backend-generated device ID")
    status: str = Field(..., description="Registration status: registered or updated")
    message: str = Field(..., description="Human-readable message")
    is_new_device: bool = Field(..., description="Whether this is a new device registration")


class UpdateDeviceRequest(BaseModel):
    """Request model for updating device status"""
    mcp_servers: Optional[List[str]] = Field(None, description="Updated list of MCP servers")
    app_version: Optional[str] = Field(None, description="Updated application version")
    os_version: Optional[str] = Field(None, description="Updated operating system version")


class UpdateDeviceResponse(BaseModel):
    """Response model for updating device"""
    device_id: UUID = Field(..., description="Device ID")
    last_active: str = Field(..., description="Last active timestamp")
    message: str = Field(..., description="Human-readable message")


class DeviceResponse(BaseModel):
    """Response model for device details"""
    device_id: UUID = Field(..., description="Device ID")
    device_token: str = Field(..., description="Device token")
    device_name: str = Field(..., description="Device name")
    device_type: str = Field(..., description="Device type")
    os_name: str = Field(..., description="Operating system name")
    os_version: str = Field(..., description="Operating system version")
    app_version: str = Field(..., description="Application version")
    mcp_servers: Optional[List[str]] = Field(None, description="List of installed MCP servers")
    last_active: Optional[str] = Field(None, description="Last active timestamp")
    is_active: bool = Field(..., description="Whether device is active")
    created_at: str = Field(..., description="Device creation timestamp")


class DeviceListResponse(BaseModel):
    """Response model for listing devices"""
    devices: List[DeviceResponse] = Field(..., description="List of devices")
    total_count: int = Field(..., description="Total number of devices")

