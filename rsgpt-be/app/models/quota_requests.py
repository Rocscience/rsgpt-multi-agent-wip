"""Quota request API models"""

from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field


class QuotaRequestCreate(BaseModel):
    """Request model for creating a quota request"""
    requested_quota: int = Field(
        ..., 
        gt=0, 
        le=100,
        description="Number of additional agent requests being requested (1-100)"
    )
    reason: str = Field(
        ..., 
        min_length=10, 
        max_length=1000,
        description="Reason for requesting additional quota (10-1000 characters)"
    )


class QuotaRequestResponse(BaseModel):
    """Response model for quota request creation"""
    success: bool = Field(..., description="Whether the request was created successfully")
    message: str = Field(..., description="Status message")
    request_id: Optional[UUID] = Field(None, description="ID of the created request")


class QuotaRequestDto(BaseModel):
    """DTO for quota request details"""
    id: UUID
    user_id: UUID
    requested_quota: int
    reason: str
    status: str
    created_at: datetime


# Admin API Models
class AdminQuotaRequestItem(BaseModel):
    """Admin view of a quota request with user info"""
    id: str
    user_id: str
    user_name: Optional[str] = None
    user_email: Optional[str] = None
    current_quota: int
    current_used: int
    requested_quota: int
    reason: str
    status: str
    created_at: Optional[str] = None


class AdminQuotaRequestsListResponse(BaseModel):
    """Response for listing quota requests (admin)"""
    requests: list[AdminQuotaRequestItem]
    total: int


class AdminQuotaRequestActionResponse(BaseModel):
    """Response for approve/deny action"""
    success: bool
    message: str
    id: str
    status: str
    new_quota: Optional[int] = None
