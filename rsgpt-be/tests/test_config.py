"""Tests for configuration system"""

import os
import pytest
from unittest.mock import patch

from app.config import Settings, DevelopmentSettings, ProductionSettings, get_settings, Environment


class TestEnvironmentEnum:
    """Test Environment enum"""

    def test_environment_values(self):
        """Test that environment enum has correct values"""
        assert Environment.DEVELOPMENT == "development"
        assert Environment.PRODUCTION == "production"
        assert Environment.TESTING == "testing"


class TestSettings:
    """Test Settings class"""

    def test_default_settings(self):
        """Test default settings values"""
        settings = Settings()

        assert settings.environment == Environment.TESTING
        assert settings.api_title == "RSGPT Backend API"
        assert settings.api_version == "0.1.0"
        assert settings.host == "0.0.0.0"
        assert settings.port == 8080
        assert settings.debug is True
        assert settings.log_level == "DEBUG"

    def test_environment_properties(self):
        """Test environment check properties"""
        dev_settings = Settings(environment=Environment.DEVELOPMENT)
        prod_settings = Settings(environment=Environment.PRODUCTION)
        test_settings = Settings(environment=Environment.TESTING)
        
        assert dev_settings.is_development is True
        assert dev_settings.is_production is False
        assert dev_settings.is_testing is False
        
        assert prod_settings.is_development is False
        assert prod_settings.is_production is True
        assert prod_settings.is_testing is False
        
        assert test_settings.is_development is False
        assert test_settings.is_production is False
        assert test_settings.is_testing is True

    def test_cors_parsing(self):
        """Test CORS configuration parsing"""
        settings = Settings(
            cors_origins_env="http://localhost:3000,http://localhost:8080",
            cors_methods_env="GET,POST,PUT,DELETE",
            cors_headers_env="Content-Type,Authorization"
        )
        
        assert settings.cors_origins == ["http://localhost:3000", "http://localhost:8080"]
        assert settings.cors_methods == ["GET", "POST", "PUT", "DELETE"]
        assert settings.cors_headers == ["Content-Type", "Authorization"]

    def test_cors_wildcard_parsing(self):
        """Test CORS wildcard parsing"""
        settings = Settings(
            cors_origins_env="*",
            cors_methods_env="*", 
            cors_headers_env="*"
        )
        
        assert settings.cors_origins == ["*"]
        assert settings.cors_methods == ["*"]
        assert settings.cors_headers == ["*"]


class TestDevelopmentSettings:
    """Test DevelopmentSettings class"""

    def test_development_defaults(self):
        """Test development-specific defaults"""
        settings = DevelopmentSettings()
        
        assert settings.debug is True
        assert settings.log_level == "DEBUG"


class TestGetSettings:
    """Test get_settings function"""

    @patch.dict(os.environ, {"ENVIRONMENT": "development"})
    def test_get_development_settings(self):
        """Test getting development settings"""
        settings = get_settings()
        assert isinstance(settings, DevelopmentSettings)
        assert settings.is_development is True

    @patch.dict(os.environ, {"ENVIRONMENT": "production"})
    def test_get_production_settings(self):
        """Test getting production settings"""
        settings = get_settings()
        assert isinstance(settings, ProductionSettings)
        assert settings.is_production is True

    @patch.dict(os.environ, {"ENVIRONMENT": "testing"})
    def test_get_testing_settings(self):
        """Test getting testing settings"""
        settings = get_settings()
        assert isinstance(settings, Settings)
        assert settings.is_testing is True

    @patch.dict(os.environ, {}, clear=True)
    def test_get_default_settings(self):
        """Test getting default settings when no environment is set"""
        settings = get_settings()
        assert isinstance(settings, DevelopmentSettings)
