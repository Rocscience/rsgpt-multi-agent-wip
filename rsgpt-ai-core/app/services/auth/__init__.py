"""Authentication services"""

from .auth_service import AuthenticationService, auth_service

# Compatibility alias
AuthService = AuthenticationService
get_auth_service = auth_service

__all__ = [
    "AuthenticationService",
    "auth_service",
    "AuthService",
    "get_auth_service",
]
