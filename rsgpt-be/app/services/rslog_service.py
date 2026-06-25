"""RSLog service for API integration and token management"""

import logging
import requests
from typing import Optional, Union, Dict, Any
from datetime import datetime, timezone, timedelta
from uuid import UUID
from urllib.parse import urlencode

from app.models.rslog import (
    RSLogConnectTokenRequest,
    RSLogVerifyRequest,
    RSLogRefreshRequest,
    RSLogTokenResponse,
    RSLogTwoFactorResponse,
    RSLogErrorResponse,
    RSLogConnectionStatus,
    CreateRSLogSettingsRequest,
    UpdateRSLogSettingsRequest,
    RSLogSettingsResponse,
)
from app.db_interface.rslog import (
    get_rslog_settings_by_user_id,
    create_rslog_settings,
    update_rslog_settings,
    delete_rslog_settings,
)
from app.utils.crypto import encrypt_rslog_token, decrypt_rslog_token

logger = logging.getLogger(__name__)


class RSLogService:
    """Service for RSLog API integration and token management"""
    
    RSLOG_BASE_URL = "https://www.rslogonline.com/"
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/x-www-form-urlencoded',
            'User-Agent': 'RSGPT-RSLog-Integration/1.0'
        })
    
    def _make_rslog_request(self, endpoint: str, data: Dict[str, Any]) -> requests.Response:
        """Make a form-encoded request to RSLog API"""
        url = f"{self.RSLOG_BASE_URL}{endpoint}"
        form_data = urlencode(data)
        
        logger.info(f"Making RSLog API request to {endpoint}")
        try:
            response = self.session.post(url, data=form_data, timeout=30)
            logger.info(f"RSLog API response: {response.status_code}")
            return response
        except requests.RequestException as e:
            logger.error(f"RSLog API request failed: {e}")
            raise e
    
    def authenticate_token(self, request: RSLogConnectTokenRequest) -> Union[RSLogTokenResponse, RSLogTwoFactorResponse, RSLogErrorResponse]:
        """Authenticate with RSLog API to get access token"""
        try:
            data = {
                'username': request.username,
                'password': request.password,
                'company': request.company
            }
            
            response = self._make_rslog_request('/api/connect/token', data)
            response_data = response.json()
            
            if response.status_code == 200:
                return RSLogTokenResponse(**response_data)
            elif response.status_code == 202:
                return RSLogTwoFactorResponse(**response_data)
            else:
                return RSLogErrorResponse(**response_data)
                
        except Exception as e:
            logger.error(f"Error in RSLog token authentication: {e}")
            return RSLogErrorResponse(
                error="authentication_failed",
                errorDescription=f"Authentication failed: {str(e)}"
            )
    
    def verify_two_factor(self, request: RSLogVerifyRequest) -> Union[RSLogTokenResponse, RSLogErrorResponse]:
        """Verify two-factor authentication code"""
        try:
            data = {
                'username': request.username,
                'password': request.password,
                'company': request.company,
                'twoFactorCode': request.twoFactorCode
            }
            
            response = self._make_rslog_request('/api/connect/verify', data)
            response_data = response.json()
            
            if response.status_code == 200:
                return RSLogTokenResponse(**response_data)
            else:
                return RSLogErrorResponse(**response_data)
                
        except Exception as e:
            logger.error(f"Error in RSLog 2FA verification: {e}")
            return RSLogErrorResponse(
                error="verification_failed",
                errorDescription=f"2FA verification failed: {str(e)}"
            )
    
    def refresh_token(self, request: RSLogRefreshRequest) -> Union[RSLogTokenResponse, RSLogErrorResponse]:
        """Refresh access token using refresh token"""
        try:
            data = {
                'company': request.company,
                'refreshToken': request.refreshToken
            }
            
            response = self._make_rslog_request('/api/connect/refresh', data)
            response_data = response.json()
            
            if response.status_code == 200:
                return RSLogTokenResponse(**response_data)
            else:
                return RSLogErrorResponse(**response_data)
                
        except Exception as e:
            logger.error(f"Error in RSLog token refresh: {e}")
            return RSLogErrorResponse(
                error="refresh_failed",
                errorDescription=f"Token refresh failed: {str(e)}"
            )
    
    def get_connection_status(self, user_id: UUID) -> RSLogConnectionStatus:
        """Get RSLog connection status for a user"""
        try:
            settings = get_rslog_settings_by_user_id(user_id)
            
            if not settings:
                # No RSLog account at all
                return RSLogConnectionStatus(
                    is_connected=False,
                    needs_refresh=False
                )
            
            # User has RSLog account - check connection status and token expiry
            needs_refresh = False
            token_expires_at = None
            
            if settings.is_connected and settings.token_created_at and settings.expires_in:
                token_expires_at = settings.token_created_at + timedelta(seconds=settings.expires_in)
                # Consider token expired if it expires within 5 minutes
                needs_refresh = datetime.now(timezone.utc) >= (token_expires_at - timedelta(minutes=5))
            
            return RSLogConnectionStatus(
                is_connected=settings.is_connected,
                company=settings.company,
                username=settings.username,
                token_expires_at=token_expires_at,
                needs_refresh=needs_refresh
            )
            
        except Exception as e:
            logger.error(f"Error getting RSLog connection status for user {user_id}: {e}")
            return RSLogConnectionStatus(
                is_connected=False,
                needs_refresh=False
            )
    
    def save_connection(self, user_id: UUID, token_response: RSLogTokenResponse, username: str, company: str) -> RSLogSettingsResponse:
        """Save RSLog connection details to database with encrypted tokens"""
        try:
            # Encrypt tokens before storing
            encrypted_access_token = encrypt_rslog_token(token_response.access_token)
            encrypted_refresh_token = encrypt_rslog_token(token_response.refresh_token)
            
            # Check if settings already exist
            existing_settings = get_rslog_settings_by_user_id(user_id)
            
            if existing_settings:
                # Update existing settings
                update_request = UpdateRSLogSettingsRequest(
                    access_token=encrypted_access_token,
                    refresh_token=encrypted_refresh_token,
                    expires_in=token_response.expires_in,
                    is_connected=True
                )
                settings = update_rslog_settings(user_id, update_request)
            else:
                # Create new settings
                create_request = CreateRSLogSettingsRequest(
                    company=company,
                    username=username,
                    access_token=encrypted_access_token,
                    refresh_token=encrypted_refresh_token,
                    expires_in=token_response.expires_in,
                    is_connected=True
                )
                settings = create_rslog_settings(user_id, create_request)
            
            if not settings:
                raise Exception("Failed to save RSLog settings")
            
            # Calculate token expiry
            token_expires_at = None
            if settings.token_created_at and settings.expires_in:
                token_expires_at = settings.token_created_at + timedelta(seconds=settings.expires_in)
            
            return RSLogSettingsResponse(
                id=settings.id,
                user_id=settings.user_id,
                company=settings.company,
                username=settings.username,
                is_connected=settings.is_connected,
                token_expires_at=token_expires_at,
                created_at=settings.created_at,
                updated_at=settings.updated_at
            )
            
        except Exception as e:
            logger.error(f"Error saving RSLog connection for user {user_id}: {e}")
            raise e
    
    def refresh_user_token(self, user_id: UUID) -> Union[RSLogSettingsResponse, RSLogErrorResponse]:
        """Refresh token for a user if needed"""
        try:
            settings = get_rslog_settings_by_user_id(user_id)
            
            if not settings or not settings.is_connected or not settings.refresh_token:
                return RSLogErrorResponse(
                    error="no_connection",
                    errorDescription="No active RSLog connection found"
                )
            
            # Decrypt refresh token before using it
            try:
                decrypted_refresh_token = decrypt_rslog_token(settings.refresh_token)
            except Exception as e:
                logger.error(f"Failed to decrypt refresh token for user {user_id}: {e}")
                return RSLogErrorResponse(
                    error="decryption_failed",
                    errorDescription="Failed to decrypt stored tokens"
                )
            
            # Attempt token refresh
            refresh_request = RSLogRefreshRequest(
                company=settings.company,
                refreshToken=decrypted_refresh_token
            )
            
            refresh_result = self.refresh_token(refresh_request)
            
            if isinstance(refresh_result, RSLogErrorResponse):
                # Mark connection as disconnected on refresh failure
                update_rslog_settings(user_id, UpdateRSLogSettingsRequest(is_connected=False))
                return refresh_result
            
            # Save new tokens
            return self.save_connection(user_id, refresh_result, settings.username, settings.company)
            
        except Exception as e:
            logger.error(f"Error refreshing token for user {user_id}: {e}")
            return RSLogErrorResponse(
                error="refresh_error",
                errorDescription=f"Token refresh error: {str(e)}"
            )
    
    def enable_user(self, user_id: UUID) -> bool:
        """Enable RSLog for a user (soft connect - no re-authentication needed)"""
        try:
            # Check if user has RSLog account
            existing_settings = get_rslog_settings_by_user_id(user_id)
            if not existing_settings or not existing_settings.company:
                return False  # No account to enable
            
            # Update settings to set is_connected=True
            update_request = UpdateRSLogSettingsRequest(is_connected=True)
            settings = update_rslog_settings(user_id, update_request)
            return settings is not None
        except Exception as e:
            logger.error(f"Error enabling RSLog for user {user_id}: {e}")
            return False
    
    def disconnect_user(self, user_id: UUID) -> bool:
        """Disconnect RSLog for a user (soft disconnect - keeps account info)"""
        try:
            # Update settings to set is_connected=False but keep account info
            update_request = UpdateRSLogSettingsRequest(is_connected=False)
            settings = update_rslog_settings(user_id, update_request)
            return settings is not None
        except Exception as e:
            logger.error(f"Error disconnecting RSLog for user {user_id}: {e}")
            return False
