import os
import logging
from typing import Optional, Dict, Any
import requests
from app.config import settings

logger = logging.getLogger(__name__)


class Auth0Client:
    """Auth0 client for handling authentication and user management"""
    
    def __init__(self):
        self.domain = settings.auth0_domain
        self.client_id = settings.auth0_client_id
        self.client_secret = settings.auth0_client_secret
        self.api_base_url = f"https://{self.domain}"
        
    def verify_token(self, token: str) -> Dict[str, Any]:
        """
        Verify an Auth0 access token and return user information
        
        Args:
            token: The access token to verify
            
        Returns:
            Dict containing user information if valid, None if invalid
        """
        try:
            # Get user info from Auth0 userinfo endpoint
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
            
            response = requests.get(
                f"{self.api_base_url}/userinfo",
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                user_data = response.json()
                return {
                    "status_code": 200,
                    "user": user_data,
                    "error_message": None
                }
            else:
                error_data = response.json() if response.content else {}
                return {
                    "status_code": response.status_code,
                    "user": None,
                    "error_message": error_data.get("error_description", "Invalid token")
                }
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Auth0 API request failed: {str(e)}")
            return {
                "status_code": 500,
                "user": None,
                "error_message": f"Auth0 API request failed: {str(e)}"
            }
        except Exception as e:
            logger.error(f"Unexpected error during token verification: {str(e)}")
            return {
                "status_code": 500,
                "user": None,
                "error_message": f"Token verification failed: {str(e)}"
            }


# Global instance
auth0_client = Auth0Client() 