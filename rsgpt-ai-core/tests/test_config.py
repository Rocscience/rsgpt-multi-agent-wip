"""Tests for app.config module"""

import os
from unittest.mock import patch

import pytest

from app.config import (
    DevelopmentSettings,
    Environment,
    ProductionSettings,
    Settings,
    TestingSettings,
    get_settings,
)


class TestEnvironment:
    """Test environment enum"""

    def test_environment_values(self):
        """Test that environment values are correct"""
        assert Environment.DEVELOPMENT == "development"
        assert Environment.PRODUCTION == "production"
        assert Environment.TESTING == "testing"


class TestSettings:
    """Test settings configuration"""

    @patch.dict(os.environ, {"AUTH0_ACCEPTED_AUDIENCES": "test-audience"}, clear=True)
    def test_default_settings(self):
        """Test default settings values"""
        # Create settings without loading .env file
        settings = Settings(_env_file=None)

        assert settings.environment == Environment.DEVELOPMENT
        assert settings.api_title == "RSGPT AI Core API"
        assert settings.api_description == "AI Core Service for RSGPT"
        assert settings.api_version == "0.1.0"
        assert settings.host == "0.0.0.0"
        assert settings.port == 8080
        assert settings.debug is True
        assert settings.log_level == "INFO"

    @patch.dict(os.environ, {"AUTH0_ACCEPTED_AUDIENCES": "test-audience"})
    def test_environment_properties(self):
        """Test environment property methods"""
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


class TestDevelopmentSettings:
    """Test development-specific settings"""

    @patch.dict(os.environ, {"AUTH0_ACCEPTED_AUDIENCES": "test-audience"})
    def test_development_overrides(self):
        """Test development settings override defaults correctly"""
        settings = DevelopmentSettings()

        assert settings.debug is True
        assert settings.log_level == "DEBUG"
        # Test that CORS origins has a default for development
        assert "localhost" in settings.cors_origins_env


class TestTestingSettings:
    """Test testing-specific settings"""

    def test_testing_overrides(self):
        """Test testing settings override defaults correctly"""
        settings = TestingSettings()

        assert settings.debug is True
        assert settings.log_level == "DEBUG"
        assert settings.cors_origins_env == "http://localhost:3000"


class TestProductionSettings:
    """Test production-specific settings"""

    def test_production_overrides(self):
        """Test production settings override defaults correctly"""
        with patch.dict(
            os.environ,
            {
                "CORS_ORIGINS": "https://example.com",
                "AUTH0_ACCEPTED_AUDIENCES": "test-audience",
            },
            clear=True,
        ):
            settings = ProductionSettings(_env_file=None)

            assert settings.debug is False
            assert settings.log_level == "WARNING"


class TestGetSettings:
    """Test settings factory function"""

    @patch.dict(os.environ, {"ENVIRONMENT": "development", "AUTH0_ACCEPTED_AUDIENCES": "test-audience"})
    def test_get_development_settings(self):
        """Test getting development settings from environment"""
        settings = get_settings()
        assert isinstance(settings, DevelopmentSettings)
        assert settings.environment == Environment.DEVELOPMENT

    @patch.dict(
        os.environ, {"ENVIRONMENT": "production", "CORS_ORIGINS": "https://example.com", "AUTH0_ACCEPTED_AUDIENCES": "test-audience"}
    )
    def test_get_production_settings(self):
        """Test getting production settings from environment"""
        settings = get_settings()
        assert isinstance(settings, ProductionSettings)
        assert settings.environment == Environment.PRODUCTION

    @patch.dict(
        os.environ, {"ENVIRONMENT": "testing", "CORS_ORIGINS": "http://localhost:3000"}
    )
    def test_get_testing_settings(self):
        """Test getting testing settings from environment"""
        settings = get_settings()
        assert isinstance(settings, TestingSettings)
        assert settings.environment == Environment.TESTING
