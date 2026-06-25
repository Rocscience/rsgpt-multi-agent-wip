"""FastAPI dependencies for authentication and authorization"""

import hmac
import logging
from typing import Optional

from fastapi import Header, HTTPException, Request

from app.auth import auth0
from app.config import settings
from app.models.services import SERVICE_NAME_BE, SERVICE_NAME_MCP
from app.models.consts import CLIENT_TYPE_DESKTOP, CLIENT_TYPE_BACKEND
from app.services.auth import auth_service

logger = logging.getLogger(__name__)


async def verify_service_auth(
    request: Request,
    x_service_token: Optional[str] = Header(None, alias="X-Service-Token"),
) -> str:
    """
    Verify service-to-service authentication token with endpoint scoping.

    This validates that:
    1. The request includes a service token
    2. The token is valid (matches one of our configured tokens)
    3. The token is authorized for the specific endpoint being called

    Token Scoping:
    - BE token can access: /chat/stream, /agent/stream, /ws/request_file_path/*
    - MCP token can access: /search/semantic, /rerank

    Args:
        request: FastAPI request object (for endpoint path)
        x_service_token: Service token from X-Service-Token header

    Returns:
        str: Service name ("rsgpt-be" or "rsgpt-mcp") for logging

    Raises:
        HTTPException:
            - 401: Missing or invalid token
            - 403: Valid token but not allowed for this endpoint
            - 500: Service auth not configured in production
    """
    # Normalize path for stable matching (avoid trailing-slash mismatches)
    endpoint = request.url.path.rstrip("/")

    # Allow bypassing in dev mode if not configured
    if settings.is_development and not settings.is_service_auth_enabled:
        logger.warning(f"DEV MODE: Bypassing service auth for {endpoint}")
        return "dev-bypass"

    # In production, tokens must be configured
    if not settings.is_service_auth_enabled:
        logger.error("Service authentication tokens not configured")
        raise HTTPException(
            status_code=500, detail="Service authentication not configured"
        )

    if not x_service_token:
        logger.warning(
            f"Service auth failed for {endpoint}: Missing X-Service-Token header"
        )
        raise HTTPException(status_code=401, detail="Missing X-Service-Token header")

    # Check if token is valid and allowed for this endpoint
    service_tokens = settings.service_tokens

    for token, allowed_endpoints in service_tokens.items():
        # Constant-time comparison to prevent timing attacks
        if hmac.compare_digest(x_service_token, token):
            # Normalize allowed endpoints for comparison
            allowed_norm = [e.rstrip("/") for e in allowed_endpoints]

            # Token is valid, check if endpoint is allowed
            # Support both exact matches and prefix matches (for endpoints with path params)
            endpoint_allowed = endpoint in allowed_norm or any(
                endpoint.startswith(allowed + "/") for allowed in allowed_norm
            )

            if endpoint_allowed:
                # Return service name directly (fixes mypy error)
                if token == settings.be_service_token:
                    logger.info(
                        "Service auth success: %s → %s", SERVICE_NAME_BE, endpoint
                    )
                    return SERVICE_NAME_BE
                if token == settings.mcp_service_token:
                    logger.info(
                        "Service auth success: %s → %s", SERVICE_NAME_MCP, endpoint
                    )
                    return SERVICE_NAME_MCP
            else:
                # Token is valid but endpoint not allowed (scope violation)
                logger.warning(
                    f"Service auth scope violation: Token valid but {endpoint} "
                    f"not in allowed list. Allowed endpoints: {allowed_endpoints}"
                )
                raise HTTPException(
                    status_code=403,
                    detail=f"Service not authorized for endpoint {endpoint}",
                )

    # No valid token found
    logger.warning(f"Service auth failed for {endpoint}: Invalid service token")
    raise HTTPException(status_code=401, detail="Invalid service token")


async def verify_be_auth(
    request: Request,
    x_service_token: Optional[str] = Header(None, alias="X-Service-Token"),
    x_client_type: Optional[str] = Header(None, alias="X-Client-Type"),
) -> dict:
    """
    Authentication for BE-only requests with client type validation.

    Security Model:
    1. Validates JWT (proves identity via Auth0)
    2. Validates X-Client-Type header (ensures caller is backend, not desktop)

    The X-Client-Type header is not a secret - it just declares intent.
    The real security is the JWT validation. This prevents Desktop from
    accidentally or intentionally calling BE-only endpoints.

    Args:
        request: FastAPI request object
        x_service_token: X-Service-Token header (development only)
        x_client_type: X-Client-Type header ("backend" required)

    Returns:
        dict: Service authentication info for logging

    Raises:
        HTTPException: 401 if auth fails, 403 if wrong client type
    """
    endpoint = request.url.path.rstrip("/")

    # Development/Testing mode: Use static token
    if settings.is_development or settings.is_testing:
        if not x_service_token:
            logger.warning(f"DEV MODE: Missing X-Service-Token for {endpoint}")
            raise HTTPException(
                status_code=401,
                detail="Development mode requires X-Service-Token header",
            )

        # Validate using existing verify_service_auth logic
        service_tokens = settings.service_tokens
        for token, allowed_endpoints in service_tokens.items():
            if hmac.compare_digest(x_service_token, token):
                allowed_norm = [e.rstrip("/") for e in allowed_endpoints]
                endpoint_allowed = endpoint in allowed_norm or any(
                    endpoint.startswith(allowed + "/") for allowed in allowed_norm
                )

                if endpoint_allowed and token == settings.be_service_token:
                    logger.info(
                        f"Service auth success (DEV - static token): {SERVICE_NAME_BE} → {endpoint}"
                    )
                    return {
                        "service": SERVICE_NAME_BE,
                        "auth_method": "static_token",
                        "client_type": CLIENT_TYPE_BACKEND,
                    }

        logger.warning(
            f"DEV MODE: Invalid or unauthorized X-Service-Token for {endpoint}"
        )
        raise HTTPException(status_code=401, detail="Invalid service token")

    # Production mode: Use M2M JWT + X-Client-Type validation
    else:
        # Validate X-Client-Type header
        if x_client_type != CLIENT_TYPE_BACKEND:
            logger.warning(
                f"Client type validation failed for {endpoint}: "
                f"expected '{CLIENT_TYPE_BACKEND}', got '{x_client_type}'"
            )
            raise HTTPException(
                status_code=403,
                detail=f"This endpoint requires X-Client-Type: {CLIENT_TYPE_BACKEND}",
            )

        # Check if auth0 is configured
        if auth0 is None:
            logger.error(
                "Production mode requires Auth0 configuration (AUTH0_DOMAIN and AUTH0_AUDIENCE)"
            )
            raise HTTPException(status_code=500, detail="Authentication not configured")

        # Call auth0.require_auth() to get and validate JWT claims
        try:
            claims = await auth0.require_auth()(request)

            # Log successful M2M authentication
            client_id = (
                claims.get("azp") or claims.get("client_id") or claims.get("sub")
            )
            logger.info(
                f"BE auth success (PROD - JWT + client_type): {SERVICE_NAME_BE}"
                f" (client: {client_id}) → {endpoint}"
            )

            # Return claims in compatible format
            return {
                "service": SERVICE_NAME_BE,
                "auth_method": "m2m_jwt",
                "client_type": CLIENT_TYPE_BACKEND,
                "claims": claims,
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"M2M JWT auth error for {endpoint}: {e}", exc_info=True)
            raise HTTPException(status_code=401, detail="Invalid or expired JWT token")


async def verify_desktop_auth(
    request: Request,
    x_client_type: Optional[str] = Header(None, alias="X-Client-Type"),
    authorization: Optional[str] = Header(None, alias="Authorization"),
) -> dict:
    """
    Authentication for Desktop-only requests with client type validation.

    Security Model:
    1. Validates JWT (proves identity via Auth0)
    2. Validates X-Client-Type header (ensures caller is desktop, not backend)

    The X-Client-Type header is not a secret - it just declares intent.
    The real security is the JWT validation. This prevents BE from
    accidentally calling Desktop-only endpoints.

    Args:
        request: FastAPI request object
        x_client_type: X-Client-Type header ("desktop" required)
        authorization: Authorization header with Bearer token

    Returns:
        dict: User authentication info

    Raises:
        HTTPException: 401 if auth fails, 403 if wrong client type
    """
    endpoint = request.url.path.rstrip("/")

    # Development mode: Skip client type check, just validate JWT
    if settings.is_development or settings.is_testing:
        logger.debug(f"DEV MODE: Skipping X-Client-Type check for {endpoint}")
    else:
        # Validate X-Client-Type header in production
        if x_client_type != CLIENT_TYPE_DESKTOP:
            logger.warning(
                f"Client type validation failed for {endpoint}: "
                f"expected '{CLIENT_TYPE_DESKTOP}', got '{x_client_type}'"
            )
            raise HTTPException(
                status_code=403,
                detail=f"This endpoint requires X-Client-Type: {CLIENT_TYPE_DESKTOP}",
            )

    # Validate Authorization header
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Invalid authorization header format. Expected 'Bearer <token>'",
        )

    token = authorization[7:]  # Remove "Bearer " prefix

    # Validate JWT using auth_service
    try:
        user_info = await auth_service.verify_token(token)
        user_id = user_info.get("user_id", "unknown")

        logger.info(f"Desktop auth success: user {user_id} → {endpoint}")

        return {
            "user": user_info,
            "client_type": CLIENT_TYPE_DESKTOP,
            "auth_method": "jwt",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Desktop JWT auth error for {endpoint}: {e}", exc_info=True)
        raise HTTPException(status_code=401, detail="Invalid or expired token")
