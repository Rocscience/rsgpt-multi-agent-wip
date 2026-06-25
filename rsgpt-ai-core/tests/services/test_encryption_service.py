"""Unit tests for encryption service"""

from unittest.mock import MagicMock, patch

import pytest
from cryptography.fernet import Fernet

from app.services.search.encryption_service import AESEncryptor, get_aes_encryptor


class TestAESEncryptor:
    """Test AESEncryptor functionality"""

    @pytest.fixture
    def test_key(self):
        """Generate a test Fernet key"""
        return Fernet.generate_key().decode("utf-8")

    @pytest.fixture
    def encryptor(self, test_key):
        """Create an AESEncryptor instance with test key"""
        return AESEncryptor(key=test_key)

    def test_initialization_with_key(self, test_key):
        """Test encryptor initializes with provided key"""
        encryptor = AESEncryptor(key=test_key)
        assert encryptor.cipher is not None
        assert encryptor.key is not None

    def test_initialization_from_env(self, test_key):
        """Test encryptor initializes from settings"""
        with patch("app.services.search.encryption_service.settings") as mock_settings:
            mock_settings.aes_encryptor_key = test_key
            encryptor = AESEncryptor()
            assert encryptor.cipher is not None

    def test_initialization_fails_without_key(self):
        """Test encryptor raises error without key"""
        with patch("app.services.search.encryption_service.settings") as mock_settings:
            mock_settings.aes_encryptor_key = ""
            with pytest.raises(ValueError, match="AES encryption key not found"):
                AESEncryptor()

    def test_decrypt_text_success(self, encryptor):
        """Test successful text decryption"""
        # Encrypt a test message using the same cipher
        test_text = "This is a test message"
        encrypted = encryptor.cipher.encrypt(test_text.encode()).decode("utf-8")

        # Decrypt using the service
        decrypted = encryptor.decrypt_text(encrypted)

        assert decrypted == test_text

    def test_decrypt_text_unicode(self, encryptor):
        """Test decryption with unicode characters"""
        test_text = "Test with unicode: 你好世界 🔒"
        encrypted = encryptor.cipher.encrypt(test_text.encode()).decode("utf-8")

        decrypted = encryptor.decrypt_text(encrypted)

        assert decrypted == test_text

    def test_decrypt_text_empty_string(self, encryptor):
        """Test decryption of empty string"""
        test_text = ""
        encrypted = encryptor.cipher.encrypt(test_text.encode()).decode("utf-8")

        decrypted = encryptor.decrypt_text(encrypted)

        assert decrypted == test_text

    def test_decrypt_text_invalid_data(self, encryptor):
        """Test decryption fails with invalid data"""
        with pytest.raises(Exception):
            encryptor.decrypt_text("invalid_encrypted_data")

    def test_bytes_to_str_conversion(self, encryptor):
        """Test bytes to string conversion"""
        test_bytes = b"test data"
        result = encryptor._bytes_to_str(test_bytes)
        assert result == "test data"
        assert isinstance(result, str)

    def test_str_to_bytes_conversion(self, encryptor):
        """Test string to bytes conversion"""
        test_str = "test data"
        result = encryptor._str_to_bytes(test_str)
        assert result == b"test data"
        assert isinstance(result, bytes)


class TestGetAESEncryptor:
    """Test get_aes_encryptor global singleton"""

    def test_get_encryptor_with_key(self):
        """Test getting encryptor when key is configured"""
        test_key = Fernet.generate_key().decode("utf-8")

        with patch("app.services.search.encryption_service.settings") as mock_settings:
            mock_settings.aes_encryptor_key = test_key

            # Clear the global instance
            import app.services.search.encryption_service as enc_module

            enc_module._aes_encryptor = None

            # Get encryptor
            encryptor = get_aes_encryptor()

            assert encryptor is not None
            assert isinstance(encryptor, AESEncryptor)

            # Verify singleton behavior (get again with same mock)
            encryptor2 = get_aes_encryptor()
            assert encryptor2 is encryptor

    def test_get_encryptor_without_key(self):
        """Test getting encryptor when key is not configured (graceful degradation)"""
        with patch("app.services.search.encryption_service.settings") as mock_settings:
            mock_settings.aes_encryptor_key = ""

            # Clear the global instance
            import app.services.search.encryption_service as enc_module

            enc_module._aes_encryptor = None

            # Get encryptor - should return None
            encryptor = get_aes_encryptor()

            assert encryptor is None
