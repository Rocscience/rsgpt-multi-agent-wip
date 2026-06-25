import os
import time
import json
import logging
from typing import Optional, Dict, Any
import requests
from app.config import settings
from fastapi import Response

logger = logging.getLogger(__name__)


class RocportalClient:
    """Rocportal client for handling rocportal status"""
    
    def __init__(self):
        self.user_org_license_api_token = settings.user_org_license_api_token
        self.user_license_api_url = settings.user_license_api_url
        
    def get_rocportal_status(self, userSub: str) -> Response:
        """
        Get the rocportal status for a user
        
        Args:
            userSub: The user sub to from the auth0 client
            
        Returns:
            Dict containing the rocportal status
        """
        try:
            # Get user info from Rocportal
            headers = {
                "Authorization": f"Token {self.user_org_license_api_token}",
                "Content-Type": "application/json"
            }

            data = {
                "sub": userSub
            }
            
            response = requests.post(
                f"{self.user_license_api_url}",
                headers=headers,
                json=data,
                timeout=30
            )

            logger.info(f"Rocportal status response: {response.status_code}")

            return response
        except Exception as e:
            logger.error(f"Unexpected error during rocportal status request: {str(e)}")
            logger.error(f"ERROR Inside of get_rocportal_status")
            return {
                "status_code": 500,
                "user": None,
                "error_message": f"Rocportal status request failed: {str(e)}"
            }
        
    def get_moc_status(self, userSub: str) -> Response:
        """
        Get the moc status for a user
        
        Args:
            userSub: The user sub to from the auth0 client
        """

        mock_response_data = {
            "result": True,
            "msg": "Found matching user MockFirst MockLast <mock@mock.com>",
            "data": {
                "id": "12345678-1234-1234-1234-123456789012",
                "stream": "Commercial",
                "email": "mock@mock.com",
                "first_name": "MockFirst",
                "last_name": "MockLast",
                "city": "Berlin",
                "country": "DE",
                "current_organization": {
                    "id": "87654321-8765-8765-8765-987654321098",
                    "sf_account_id": "1234567890123ABCDE",
                    "name": "Mock Organization",
                    "status": "Active",
                    "is_educational": False,
                    "licenses": [
                        {
                            "name": "CP-12345-123",
                            "program": "CPillar",
                            "type": "PCL",
                            "num_seats": 1,
                            "status": "Lapsed",
                            "expiry_data": "2024-10-10"
                        },
                        {
                            "name": "DP-12345-123",
                            "program": "Dips",
                            "type": "FCL",
                            "num_seats": 2,
                            "status": "Active",
                            "expiry_data": "2025-10-16"
                        }
                    ]
                }
            },
            "meta": None
        }

        mock_response = Response()
        mock_response.status_code = 200
        mock_response._content = json.dumps(mock_response_data).encode('utf-8')

        return mock_response

# Global instance
rocportal_client = RocportalClient()