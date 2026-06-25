"""User-related api models"""

from datetime import date
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field

class CreateUserRequest(BaseModel):
    """Request model for creating a user"""
    auth0_sub: str = Field(..., description="Auth0 subject identifier")
    email: str = Field(..., description="User email address")
    name: Optional[str] = Field(None, description="User display name")
    first_name: Optional[str] = Field(None, description="User first name")
    last_name: Optional[str] = Field(None, description="User last name")
    profile_picture_url: Optional[str] = Field(None, description="Profile picture URL")
    last_login: Optional[str] = Field(None, description="Last login timestamp")
    is_active: bool = Field(True, description="Whether user is active")

class CreateUserResponse(BaseModel):
    """Response model for creating a user"""
    id: UUID = Field(..., description="User ID")
    auth0_sub: str = Field(..., description="Auth0 subject identifier")
    email: str = Field(..., description="User email address")
    name: Optional[str] = Field(None, description="User display name")
    first_name: Optional[str] = Field(None, description="User first name")
    last_name: Optional[str] = Field(None, description="User last name")
    profile_picture_url: Optional[str] = Field(None, description="Profile picture URL")
    last_login: Optional[str] = Field(None, description="Last login timestamp")
    is_active: bool = Field(True, description="Whether user is active")

class UserSettingsRequest(BaseModel):
    """Request model for user settings"""
    preferred_sources: list[str] = Field(..., description="Preferred sources")
    theme: str = Field(..., description="Theme")
    language: str = Field(..., description="Language")
    timezone: str = Field(..., description="Time zone")
    agent_mode_opt_in: bool = Field(..., description="Opt-in status for agent mode data collection")

class UserSettingsResponse(BaseModel):
    """Response model for user settings"""
    preferred_sources: list[str] = Field(..., description="Preferred sources")
    theme: str = Field(..., description="Theme")
    language: str = Field(..., description="Language")
    timezone: str = Field(..., description="Time zone")
    agent_mode_opt_in: bool = Field(..., description="Opt-in status for agent mode data collection")