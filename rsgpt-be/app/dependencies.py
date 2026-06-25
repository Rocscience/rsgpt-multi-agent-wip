import os
import logging
import hmac
from typing import Dict, Any
from fastapi import Depends, HTTPException, Request, Header
import requests
from app.clients.auth0_client import auth0_client
from app.services.user_service import UserService
from app.db_interface.users import get_user_by_auth0_sub
from app.auth import auth0
from uuid import UUID

logger = logging.getLogger(__name__)


async def get_current_user_with_claims(claims: dict, request: Request) -> Dict[str, Any]:
    """
    Authentication dependency that returns user information from database or Auth0.
    
    First checks if user exists in database using the sub from claims.
    Only calls Auth0 userinfo endpoint for new users.
    
    Args:
        claims: JWT claims containing the user's 'sub' and other information
        request: FastAPI request object to get the authorization token if needed
    
    Returns:
        Dict containing user_id, user_sub, user_email, and user_data
        
    Raises:
        HTTPException: 401 for auth failures, 400 for validation errors, 503 for service errors
    """
    try:
        # Extract the Auth0 sub from claims
        user_sub = claims.get("sub")
        if not user_sub:
            raise HTTPException(
                status_code=401,
                detail="Invalid claims: missing 'sub' field"
            )
        
        # First, check if user exists in database
        existing_user = get_user_by_auth0_sub(user_sub)
        
        if existing_user:
            # User exists in database, return data from DB
            logger.info(f"User found in database: {existing_user.email}")
            return {
                "user_id": existing_user.id,
                "user_sub": existing_user.auth0_sub,
                "user_email": existing_user.email,
            }
        else:
            # User doesn't exist, need to fetch from Auth0 and create
            logger.info(f"User not found in database, fetching from Auth0: {user_sub}")
            
            # Get the Authorization header to extract token
            auth_header = request.headers.get("Authorization")
            if not auth_header or not auth_header.startswith("Bearer "):
                raise HTTPException(
                    status_code=401,
                    detail="Authorization header missing or invalid format"
                )
            
            token = auth_header.split(" ")[1]
            
            # Call Auth0 userinfo endpoint
            resp = auth0_client.verify_token(token)
            if resp["status_code"] == 200:
                auth_service = UserService()
                user_data = resp["user"]
                
                # Create user in database
                user_id = auth_service.get_or_create_user(user_data)
                
                return {
                    "user_id": user_id,
                    "user_sub": user_data.get("sub"),
                    "user_email": user_data.get("email"),
                }
            else:
                logger.warning(f"Auth0 authentication failed: {resp['error_message']}")
                raise HTTPException(
                    detail=f"Invalid Auth0 token: {resp['error_message']}", 
                    status_code=resp["status_code"]
                )
            
    except HTTPException:
        # Re-raise HTTPExceptions as-is
        raise
    except ValueError as ve:
        logger.error(f"Data validation error during authentication: {str(ve)}")
        raise HTTPException(
            detail=f"Invalid user data: {str(ve)}", 
            status_code=400
        )
    except requests.RequestException as re:
        logger.error(f"Network error during Auth0 authentication: {str(re)}")
        raise HTTPException(
            detail="Authentication service temporarily unavailable", 
            status_code=503
        )
    except Exception as exc:
        logger.error(f"Unexpected error during authentication: {str(exc)}", exc_info=True)
        raise HTTPException(
            detail="Internal authentication error", 
            status_code=500
        )


async def get_current_user(
    request: Request, 
    claims: dict = Depends(auth0.require_auth())
) -> Dict[str, Any]:
    """
    Optimized authentication dependency that can be used with Depends().
    
    This function combines Auth0 claims validation with database-first user lookup.
    Use this dependency for new routes that want the optimized behavior.
    
    Returns:
        Dict containing user_id, user_sub, user_email, and user_data
        
    Raises:
        HTTPException: 401 for auth failures, 400 for validation errors, 503 for service errors
    """
    return await get_current_user_with_claims(claims, request)


async def verify_desktop_service_token(
    x_service_token: str = Header(..., alias="X-Service-Token")
) -> bool:
    """
    Verify the desktop service token for MCP install log endpoint.

    This uses the SharedTokenService to validate the shared desktop token
    that desktop apps fetch from the /auth/service-tokens endpoint.

    Args:
        x_service_token: Service token from X-Service-Token header

    Returns:
        True if token is valid

    Raises:
        HTTPException: 401 if token is missing or invalid
    """
    from app.services.secrets_manager_service import get_token_service

    try:
        token_service = get_token_service()

        # Validate the token using SharedTokenService
        if not token_service.validate_desktop_token(x_service_token):
            logger.warning("Invalid desktop service token provided")
            raise HTTPException(
                status_code=401,
                detail="Invalid service token"
            )

        logger.info("Desktop service authentication successful")
        return True

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error verifying desktop service token: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Service authentication error"
        )


async def verify_github_actions_token(
    x_service_token: str = Header(..., alias="X-Service-Token")
) -> bool:
    """
    Verify the GitHub Actions service token for MCP registration endpoint.

    This is service-to-service authentication between GitHub Actions
    workflows and rsgpt-be for automated MCP registration.

    Args:
        x_service_token: Service token from X-Service-Token header

    Returns:
        True if token is valid

    Raises:
        HTTPException: 401 if token is missing or invalid, 500 if not configured
    """
    from app.config import settings

    if not settings.github_actions_service_token:
        logger.error("GitHub Actions service token not configured")
        raise HTTPException(
            status_code=500,
            detail="Service authentication not configured"
        )

    # Constant-time comparison to prevent timing attacks
    if not hmac.compare_digest(x_service_token, settings.github_actions_service_token):
        logger.warning("Invalid GitHub Actions service token provided")
        raise HTTPException(
            status_code=401,
            detail="Invalid service token"
        )

    logger.info("GitHub Actions service authentication successful")
    return True


async def verify_admin_token(
    x_admin_token: str = Header(..., alias="X-Admin-Token")
) -> bool:
    """
    Verify the admin API token for admin endpoints.

    Args:
        x_admin_token: Admin token from X-Admin-Token header

    Returns:
        True if token is valid

    Raises:
        HTTPException: 401 if token is missing or invalid, 500 if not configured
    """
    from app.config import settings

    if not settings.admin_api_token:
        logger.error("Admin API token not configured")
        raise HTTPException(
            status_code=500,
            detail="Admin authentication not configured"
        )

    # Constant-time comparison to prevent timing attacks
    if not hmac.compare_digest(x_admin_token, settings.admin_api_token):
        logger.warning("Invalid admin token provided")
        raise HTTPException(
            status_code=401,
            detail="Invalid admin token"
        )

    logger.info("Admin authentication successful")
    return True
