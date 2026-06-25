"""RSLog API routes"""

from fastapi import APIRouter, Depends, HTTPException, status
import logging
from typing import Dict, Any, Union

from app.models.rslog import (
    RSLogConnectTokenRequest,
    RSLogVerifyRequest,
    RSLogTokenResponse,
    RSLogTwoFactorResponse,
    RSLogErrorResponse,
    RSLogConnectionStatus,
    RSLogSettingsResponse,
)
from app.services.rslog_service import RSLogService
from app.dependencies import get_current_user

logger = logging.getLogger(__name__)

rslog_router = APIRouter()


@rslog_router.post("/connect/token", response_model=Union[RSLogTokenResponse, RSLogTwoFactorResponse])
async def connect_token(
    request: RSLogConnectTokenRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Authenticate with RSLog API to get access token.
    Returns either a token response or 2FA challenge.
    """
    try:
        logger.info(f"RSLog token authentication for user {current_user['user_id']}")
        
        rslog_service = RSLogService()
        result = rslog_service.authenticate_token(request)
        
        if isinstance(result, RSLogErrorResponse):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": result.error, "errorDescription": result.errorDescription}
            )
        
        # If successful authentication (200), save the connection
        if isinstance(result, RSLogTokenResponse):
            try:
                rslog_service.save_connection(
                    user_id=current_user['user_id'],
                    token_response=result,
                    username=request.username,
                    company=request.company
                )
                logger.info(f"RSLog connection saved for user {current_user['user_id']}")
            except Exception as e:
                logger.exception("Failed to save RSLog connection")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to persist RSLog connection"
                ) from e
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in RSLog token authentication: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during authentication"
        )


@rslog_router.post("/connect/verify", response_model=RSLogTokenResponse)
async def verify_two_factor(
    request: RSLogVerifyRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Verify two-factor authentication code and complete authentication.
    """
    try:
        logger.info(f"RSLog 2FA verification for user {current_user['user_id']}")
        
        rslog_service = RSLogService()
        result = rslog_service.verify_two_factor(request)
        
        if isinstance(result, RSLogErrorResponse):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": result.error, "errorDescription": result.errorDescription}
            )
        
        # Save the connection after successful 2FA
        try:
            rslog_service.save_connection(
                user_id=current_user['user_id'],
                token_response=result,
                username=request.username,
                company=request.company
            )
            logger.info(f"RSLog connection saved after 2FA for user {current_user['user_id']}")
        except Exception as e:
            logger.exception("Failed to save RSLog connection after 2FA")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to persist RSLog connection"
            ) from e
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in RSLog 2FA verification: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during 2FA verification"
        )


@rslog_router.post("/connect/refresh", response_model=RSLogSettingsResponse)
async def refresh_token(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Refresh the RSLog access token using the stored refresh token.
    """
    try:
        logger.info(f"RSLog token refresh for user {current_user['user_id']}")
        
        rslog_service = RSLogService()
        result = rslog_service.refresh_user_token(current_user['user_id'])
        
        if isinstance(result, RSLogErrorResponse):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": result.error, "errorDescription": result.errorDescription}
            )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in RSLog token refresh: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during token refresh"
        )


@rslog_router.get("/status", response_model=RSLogConnectionStatus)
async def get_connection_status(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Get the current RSLog connection status for the user.
    """
    try:
        logger.info(f"Getting RSLog connection status for user {current_user['user_id']}")
        
        rslog_service = RSLogService()
        status_info = rslog_service.get_connection_status(current_user['user_id'])
        
        return status_info
        
    except Exception as e:
        logger.error(f"Error getting RSLog connection status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error while checking connection status"
        )


@rslog_router.post("/connect/enable")
async def enable_rslog(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Enable RSLog integration for the user (soft connect - no re-authentication needed).
    """
    try:
        logger.info(f"Enabling RSLog for user {current_user['user_id']}")
        
        rslog_service = RSLogService()
        success = rslog_service.enable_user(current_user['user_id'])
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No RSLog account found to enable"
            )
        
        return {"message": "RSLog enabled successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error enabling RSLog: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during enable"
        )


@rslog_router.delete("/disconnect")
async def disconnect_rslog(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Disconnect RSLog integration for the user.
    """
    try:
        logger.info(f"Disconnecting RSLog for user {current_user['user_id']}")
        
        rslog_service = RSLogService()
        success = rslog_service.disconnect_user(current_user['user_id'])
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No RSLog connection found to disconnect"
            )
        
        return {"message": "RSLog disconnected successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error disconnecting RSLog: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during disconnection"
        )
