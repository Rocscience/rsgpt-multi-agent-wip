"""Organization-related api models"""

from datetime import date
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field

class CreateOrganizationRequest(BaseModel):
    """Request model for creating an organization"""
    id: UUID = Field(..., description="Organization ID")
    name: str = Field(..., description="Organization name")
    question_quota: int = Field(..., description="Question quota limit")
    rocportal_status: bool = Field(..., description="Rocportal status")
    access_level: str = Field(..., description="Access level for organization")
    quota_reset_date: Optional[date] = Field(None, description="Date when quota resets")

class CreateOrganizationResponse(BaseModel):
    """Response model for creating an organization"""
    id: UUID = Field(..., description="Organization ID")
    name: str = Field(..., description="Organization name")
    question_quota: int = Field(..., description="Question quota limit")
    rocportal_status: bool = Field(..., description="Rocportal status")
    access_level: str = Field(..., description="Access level for organization")
    quota_reset_date: Optional[date] = Field(None, description="Date when quota resets")
