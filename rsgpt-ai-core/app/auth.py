"""Auth0 authentication setup for AI-Core service

This module provides the Auth0FastAPI instance for validating M2M JWT tokens.
The instance is configured with domain and audience from environment settings
and is used by dependencies to validate Bearer tokens via auth0.require_auth().

In production mode, auth0 is initialized for JWT validation.
In development/testing mode, auth0 is None (static tokens are used instead).
"""

from typing import Optional
from fastapi_plugin import Auth0FastAPI
from app.config import settings

# Auth0 instance for validating M2M tokens from rsgpt-be
# Only initialized in production mode when domain and audience are configured
auth0: Optional[Auth0FastAPI] = None

if settings.auth0_domain and settings.auth0_audience:
    auth0 = Auth0FastAPI(
        domain=settings.auth0_domain,
        audience=settings.auth0_audience
    )
