"""Authentication service for JWT token validation"""

import json
import logging
from typing import Dict, Optional
from urllib.request import urlopen

from fastapi import HTTPException
from jose import JWTError, jwt

from app.config import settings

logger = logging.getLogger(__name__)


class AuthenticationService:
    """Service for handling JWT token authentication with Auth0"""

    def __init__(self):
        self._jwks_cache: Optional[Dict] = None
        self._algorithms = (
            [settings.auth0_algorithms] if settings.auth0_algorithms else ["RS256"]
        )

    def get_jwks(self) -> Dict:
        """Get JSON Web Key Set from Auth0"""
        if self._jwks_cache is None:
            if not settings.auth0_domain:
                raise HTTPException(
                    status_code=500, detail="Auth0 domain not configured"
                )

            try:
                jwks_url = f"https://{settings.auth0_domain}/.well-known/jwks.json"
                with urlopen(jwks_url) as response:
                    self._jwks_cache = json.load(response)
            except Exception as e:
                logger.error(f"Failed to fetch JWKS: {e}")
                raise HTTPException(
                    status_code=500, detail="Failed to fetch authentication keys"
                )

        return self._jwks_cache

    def get_rsa_key(self, token: str) -> Dict:
        """Extract RSA key from JWKS for token validation"""
        try:
            unverified_header = jwt.get_unverified_header(token)
        except JWTError as e:
            logger.error(f"Invalid token header: {e}")
            raise HTTPException(status_code=401, detail="Invalid token format")

        rsa_key = {}
        jwks = self.get_jwks()

        for key in jwks["keys"]:
            if key["kid"] == unverified_header["kid"]:
                rsa_key = {
                    "kty": key["kty"],
                    "kid": key["kid"],
                    "use": key["use"],
                    "n": key["n"],
                    "e": key["e"],
                }
                break

        if not rsa_key:
            raise HTTPException(
                status_code=401, detail="Unable to find appropriate key"
            )

        return rsa_key

    async def verify_token(self, token: str) -> Dict:
        """Verify JWT token and return user information"""
        try:
            # RSI-140: Log configuration for debugging
            logger.info(
                f"[RSI-140] Auth config: environment={settings.environment}, "
                f"is_development={settings.is_development}, "
                f"auth0_domain={settings.auth0_domain}"
            )
            logger.info(
                f"[RSI-140] Accepted audiences: {settings.auth0_accepted_audiences}"
            )

            # Decode token without verification to see what's in it
            try:
                unverified_payload = jwt.decode(token, options={"verify_signature": False})
                token_audience = unverified_payload.get("aud")
                token_issuer = unverified_payload.get("iss")
                token_sub = unverified_payload.get("sub", "unknown")[:20]  # First 20 chars for privacy
                logger.info(
                    f"[RSI-140] Incoming token: aud={token_audience}, iss={token_issuer}, sub={token_sub}..."
                )
            except Exception as decode_err:
                logger.warning(f"[RSI-140] Could not decode token for logging: {decode_err}")
                token_audience = "unknown"

            # For development, allow bypassing signature verification
            if settings.is_development and not settings.auth0_domain:
                logger.warning("Development mode: Skipping JWT signature verification")
                payload = jwt.decode(token, options={"verify_signature": False})
            else:
                # Production: Full verification with Auth0
                rsa_key = self.get_rsa_key(token)

                # Try validating with each accepted audience
                # Supports both Desktop JWT (rsgpt-be-test-identifier) and BE M2M JWT (rsgpt-ai-core-test-identifier)
                jwt_error = None
                payload = None

                for audience in settings.auth0_accepted_audiences:
                    try:
                        logger.info(f"[RSI-140] Trying audience: {audience}")
                        payload = jwt.decode(
                            token,
                            rsa_key,
                            algorithms=self._algorithms,
                            audience=audience,
                            issuer=f"https://{settings.auth0_domain}/",
                        )
                        logger.info(f"[RSI-140] ✓ Token validated with audience: {audience}")
                        break  # Success - stop trying other audiences
                    except JWTError as e:
                        jwt_error = e
                        logger.info(f"[RSI-140] ✗ Failed for audience {audience}: {e}")
                        continue  # Try next audience

                if payload is None:
                    # None of the accepted audiences worked
                    logger.error(
                        f"[RSI-140] Token validation FAILED - no matching audience. "
                        f"Token aud={token_audience}, accepted={settings.auth0_accepted_audiences}"
                    )
                    raise jwt_error or JWTError("Token does not match any accepted audience")

            # Extract user information
            user_id = payload.get("sub")
            if not user_id:
                raise HTTPException(
                    status_code=401, detail="Invalid token: missing user ID"
                )

            return {
                "user_id": user_id,
                "email": payload.get("email"),
                "name": payload.get("name"),
                "nickname": payload.get("nickname"),
                "picture": payload.get("picture"),
                "exp": payload.get("exp"),
                "iat": payload.get("iat"),
                "raw_payload": payload,
            }

        except JWTError as e:
            logger.error(f"JWT validation error: {e}")
            raise HTTPException(status_code=401, detail="Invalid token")
        except Exception as e:
            logger.error(f"Unexpected authentication error: {e}")
            raise HTTPException(status_code=500, detail="Authentication service error")


# Global authentication service instance
auth_service = AuthenticationService()
