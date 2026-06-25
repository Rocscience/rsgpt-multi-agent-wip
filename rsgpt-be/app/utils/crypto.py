"""Cryptographic utilities for secure token storage"""

import os
import base64
import logging
from typing import Optional
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

logger = logging.getLogger(__name__)


class TokenEncryption:
    """Utility class for encrypting and decrypting RSLog tokens"""
    
    def __init__(self, encryption_key: Optional[str] = None):
        """
        Initialize token encryption with a key.
        If no key is provided, uses environment variable or generates one.
        """
        if encryption_key:
            self.key = encryption_key.encode()
        else:
            # Try to get from environment variable
            env_key = os.getenv('RSLOG_ENCRYPTION_KEY')
            if env_key:
                self.key = env_key.encode()
            else:
                # Generate a key from a password (in production, use a proper secret)
                password_env = os.getenv('SECRET_KEY')
                if not password_env:
                    raise RuntimeError(
                        "RSLOG_ENCRYPTION_KEY or SECRET_KEY must be set before using TokenEncryption"
                    )
                password = password_env.encode()
                salt = b'rslog-salt-2024'  # In production, use a random salt per installation
                kdf = PBKDF2HMAC(
                    algorithm=hashes.SHA256(),
                    length=32,
                    salt=salt,
                    iterations=100000,
                )
                self.key = base64.urlsafe_b64encode(kdf.derive(password))
        
        self.fernet = Fernet(self.key)
    
    def encrypt_token(self, token: str) -> str:
        """
        Encrypt a token string.
        
        Args:
            token: The token string to encrypt
            
        Returns:
            Base64 encoded encrypted token
        """
        try:
            if not token:
                return ""
            
            encrypted_token = self.fernet.encrypt(token.encode())
            return base64.urlsafe_b64encode(encrypted_token).decode()
        except Exception as e:
            logger.error(f"Error encrypting token: {e}")
            raise e
    
    def decrypt_token(self, encrypted_token: str) -> str:
        """
        Decrypt an encrypted token string.
        
        Args:
            encrypted_token: The base64 encoded encrypted token
            
        Returns:
            Decrypted token string
        """
        try:
            if not encrypted_token:
                return ""
            
            encrypted_data = base64.urlsafe_b64decode(encrypted_token.encode())
            decrypted_token = self.fernet.decrypt(encrypted_data)
            return decrypted_token.decode()
        except Exception as e:
            logger.error(f"Error decrypting token: {e}")
            raise e


# Global instance for token encryption
_token_encryption = None


def get_token_encryption() -> TokenEncryption:
    """Get the global token encryption instance"""
    global _token_encryption
    if _token_encryption is None:
        _token_encryption = TokenEncryption()
    return _token_encryption


def encrypt_rslog_token(token: str) -> str:
    """Convenience function to encrypt an RSLog token"""
    return get_token_encryption().encrypt_token(token)


def decrypt_rslog_token(encrypted_token: str) -> str:
    """Convenience function to decrypt an RSLog token"""
    return get_token_encryption().decrypt_token(encrypted_token)
