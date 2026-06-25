from datetime import date
from typing import Optional
from pydantic import BaseModel, Field


class AuthResponse(BaseModel):
    """Response model for basic auth endpoint"""
    message: str = Field(..., description="Response message")

class RocportalStatusResponse(BaseModel):
    """Response model for rocportal status endpoint"""
    rocportal_status: bool = Field(..., description="Whether user has access to rocportal")
    message: Optional[str] = Field(None, description="Optional message explaining the status")

class QuotaInfoResponse(BaseModel):
    """Response model for quota info endpoint"""
    organization_name: str = Field(..., description="Organization name")
    question_quota: int = Field(..., description="Question quota for the user (Ask mode)")
    questions_used: int = Field(..., description="Questions used by the user (Ask mode)")
    quota_reset_date: Optional[date] = Field(None, description="Date when quota resets")
    agent_quota: int = Field(..., description="Agent mode quota limit for the user")
    agent_quota_used: int = Field(..., description="Agent mode requests used by the user")


class MCPCredential(BaseModel):
    """MCP service credential"""
    token: str = Field(..., description="Service token for MCP server")


class ServiceTokensResponse(BaseModel):
    """
    Response model for service tokens endpoint.

    Note  desktop_service_token was removed - Desktop uses JWT auth directly.
    Note  Unified MCP token for all servers (RS2, RSPile, etc.)
    """
    mcp_credentials: dict[str, MCPCredential] = Field(..., description="MCP service credentials by service name")

    class Config:
        json_schema_extra = {
            "example": {
                "mcp_credentials": {
                    "mcp": {
                        "token": "unified_mcp_token_xyz789..."
                    }
                }
            }
        }