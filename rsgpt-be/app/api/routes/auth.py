"""Authentication and token management endpoints"""

import logging
from typing import Dict, Any

from fastapi import APIRouter, Depends, HTTPException

from app.dependencies import get_current_user
from app.models.auth import ServiceTokensResponse, MCPCredential
from app.services.secrets_manager_service import get_token_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.get("/service-tokens", response_model=ServiceTokensResponse)
async def get_service_tokens(
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> ServiceTokensResponse:
    """
    Get shared MCP service tokens for authenticated user.

    **Security Model**
    - Requires valid Auth0 JWT (user must be authenticated)
    - Returns SHARED MCP tokens (same for all users)
    - MCP servers use these tokens to authenticate with AI-Core
    - Desktop uses JWT directly for backend API calls (no desktop token needed)

    **Usage:**
    Desktop app calls this endpoint after Auth0 login to fetch MCP tokens.
    Tokens are stored in memory (not persisted to disk) and cleared on logout.

    Returns:
        ServiceTokensResponse with MCP service tokens
    """
    user_id = current_user["user_id"]
    user_email = current_user.get("user_email", "unknown")

    logger.info(f"User {user_id} ({user_email}) fetching MCP service tokens")

    try:
        token_service = get_token_service()
        tokens = token_service.get_shared_tokens()

        logger.info(f"✅ MCP service tokens provided to user {user_id}")

        return ServiceTokensResponse(
            mcp_credentials={
                "mcp": MCPCredential(token=tokens["mcp"])
            }
        )

    except Exception as e:
        logger.error(f"Error getting tokens for user {user_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve service tokens"
        )
