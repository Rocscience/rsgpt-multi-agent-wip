from typing import List, Optional

from pydantic import BaseModel, Field


class RootResponse(BaseModel):
    """Response model for root endpoint"""

    message: str = Field(..., description="API status message")
    environment: str = Field(..., description="Current environment")
    version: str = Field(..., description="API version")
    docs_url: Optional[str] = Field(
        None, description="Documentation URL (development only)"
    )


class HealthResponse(BaseModel):
    """Response model for health check endpoint"""

    message: str = Field(..., description="Health status message")
    status: str = Field(..., description="Service status")
    service: str = Field(..., description="Service name")
    environment: str = Field(..., description="Current environment")
    debug: bool = Field(..., description="Debug mode status")


class ConfigResponse(BaseModel):
    """Response model for config endpoint (development only)"""

    message: str = Field(..., description="Configuration message")
    environment: str = Field(..., description="Current environment")
    debug: bool = Field(..., description="Debug mode status")
    host: str = Field(..., description="Server host")
    port: int = Field(..., description="Server port")
    cors_origins: List[str] = Field(..., description="CORS allowed origins")
    log_level: str = Field(..., description="Logging level")
