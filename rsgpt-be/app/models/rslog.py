"""RSLog API models"""

from typing import Optional
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field


# Request Models
class RSLogConnectTokenRequest(BaseModel):
    """Request model for RSLog token authentication"""
    username: str = Field(..., description="Username or email address")
    password: str = Field(..., description="User password")
    company: str = Field(..., description="Company/tenant name")


class RSLogVerifyRequest(BaseModel):
    """Request model for RSLog 2FA verification"""
    username: str = Field(..., description="Username or email address")
    password: str = Field(..., description="User password")
    company: str = Field(..., description="Company/tenant name")
    twoFactorCode: str = Field(..., description="Two-factor authentication code from email")


class RSLogRefreshRequest(BaseModel):
    """Request model for RSLog token refresh"""
    company: str = Field(..., description="Company/tenant name")
    refreshToken: str = Field(..., description="Valid refresh token from previous authentication")


# Response Models
class RSLogTokenResponse(BaseModel):
    """Response model for successful RSLog authentication"""
    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field(..., description="Token type (Bearer)")
    expires_in: int = Field(..., description="Token expiry in seconds")
    refresh_token: str = Field(..., description="Refresh token for token renewal")
    scope: Optional[str] = Field(None, description="Token scope (optional)")


class RSLogTwoFactorResponse(BaseModel):
    """Response model when 2FA is required"""
    status: str = Field(..., description="Status message indicating 2FA requirement")
    twoFactorProvider: str = Field(..., description="2FA provider (Email)")
    maskedEmail: str = Field(..., description="Masked email address")
    message: str = Field(..., description="User-friendly message")


class RSLogErrorResponse(BaseModel):
    """Response model for RSLog API errors"""
    error: str = Field(..., description="Error code")
    errorDescription: str = Field(..., description="Human-readable error description")


# Internal Models
class RSLogConnectionStatus(BaseModel):
    """Model for RSLog connection status"""
    is_connected: bool = Field(..., description="Whether RSLog is connected")
    company: Optional[str] = Field(None, description="Connected company name")
    username: Optional[str] = Field(None, description="Connected username")
    token_expires_at: Optional[datetime] = Field(None, description="When the current token expires")
    needs_refresh: bool = Field(False, description="Whether token needs refresh")


class CreateRSLogSettingsRequest(BaseModel):
    """Request model for creating RSLog settings"""
    company: str = Field(..., description="Company/tenant name")
    username: str = Field(..., description="Username or email address")
    access_token: str = Field(..., description="Access token (will be encrypted)")
    refresh_token: str = Field(..., description="Refresh token (will be encrypted)")
    expires_in: int = Field(..., description="Token expiry in seconds")
    is_connected: bool = Field(True, description="Connection status")


class UpdateRSLogSettingsRequest(BaseModel):
    """Request model for updating RSLog settings"""
    access_token: Optional[str] = Field(None, description="New access token (will be encrypted)")
    refresh_token: Optional[str] = Field(None, description="New refresh token (will be encrypted)")
    expires_in: Optional[int] = Field(None, description="New token expiry in seconds")
    is_connected: Optional[bool] = Field(None, description="Connection status")


class RSLogSettingsResponse(BaseModel):
    """Response model for RSLog settings"""
    id: UUID = Field(..., description="Settings ID")
    user_id: UUID = Field(..., description="User ID")
    company: str = Field(..., description="Company/tenant name")
    username: str = Field(..., description="Username or email address")
    is_connected: bool = Field(..., description="Connection status")
    token_expires_at: Optional[datetime] = Field(None, description="When the current token expires")
    created_at: datetime = Field(..., description="When settings were created")
    updated_at: datetime = Field(..., description="When settings were last updated")
