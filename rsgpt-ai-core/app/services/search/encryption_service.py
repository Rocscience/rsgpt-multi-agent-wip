"""Encryption/decryption service for encrypted channel data"""

import logging
from typing import Optional

from cryptography.fernet import Fernet

from app.config import settings

logger = logging.getLogger(__name__)


class AESEncryptor:
    """
    AES encryption/decryption using Fernet (symmetric encryption).

    This class is used to decrypt text data stored in encrypted channels
    like tech_support. The encryption key must match the one used when
    the data was originally encrypted and uploaded to Pinecone.
    """

    def __init__(self, key: Optional[str] = None):
        """
        Initialize the AES encryptor with encryption key.

        Args:
            key: Base64-encoded Fernet key. If None, reads from AES_ENCRYPTOR_KEY in .env file.

        Raises:
            ValueError: If no key is provided or found in environment
        """
        if key is None:
            key = settings.aes_encryptor_key

        if not key:
            raise ValueError(
                "AES encryption key not found. Set AES_ENCRYPTOR_KEY in .env file."
            )

        self.key = self._str_to_bytes(key)
        self.cipher = Fernet(self.key)

    def _bytes_to_str(self, bytes_data: bytes) -> str:
        """Convert bytes to utf-8 string"""
        return bytes_data.decode("utf-8")

    def _str_to_bytes(self, str_data: str) -> bytes:
        """Convert utf-8 string to bytes"""
        return str_data.encode("utf-8")

    def decrypt_text(self, encrypted_message: str) -> str:
        """
        Decrypt an encrypted message string.

        Args:
            encrypted_message: The encrypted text (base64-encoded)

        Returns:
            str: The decrypted plain text

        Raises:
            Exception: If decryption fails
        """
        try:
            encrypted_bytes = self._str_to_bytes(encrypted_message)
            decrypted_message = self.cipher.decrypt(encrypted_bytes).decode()
            return decrypted_message
        except Exception as e:
            logger.error(f"Failed to decrypt text: {e}")
            raise


# Global encryptor instance
_aes_encryptor: Optional[AESEncryptor] = None


def get_aes_encryptor() -> Optional[AESEncryptor]:
    """
    Get the global AES encryptor instance.

    Returns None if encryption key is not configured (graceful degradation).
    """
    global _aes_encryptor

    if _aes_encryptor is None:
        try:
            _aes_encryptor = AESEncryptor()
            logger.info("AES encryptor initialized successfully")
        except ValueError as e:
            logger.warning(f"AES encryptor not available: {e}")
            return None

    return _aes_encryptor
