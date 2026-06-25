"""Configuration settings for different environments"""

from enum import Enum
from typing import List
from pydantic import Field
from pydantic_settings import BaseSettings


class Environment(str, Enum):
    """Environment types"""
    DEVELOPMENT = "development"
    PRODUCTION = "production"
    TESTING = "testing"


class Settings(BaseSettings):
    """Application settings with environment-specific configurations"""
    
    # Environment
    environment: Environment = Field(default=Environment.DEVELOPMENT, env="ENVIRONMENT")
    
    # API Configuration
    api_title: str = "RSGPT Backend API"
    api_description: str = "API Gateway for RSGPT Backend Service"
    api_version: str = "0.1.0"
    
    # Server Configuration
    host: str = Field(default="0.0.0.0", env="HOST")
    port: int = Field(default=8080, env="PORT")
    debug: bool = Field(default=True, env="DEBUG")
    
    # CORS Configuration - stored as strings to avoid JSON parsing
    # No permissive default - must be explicitly configured
    cors_origins_env: str = Field(env="CORS_ORIGINS")
    cors_credentials: bool = Field(default=True, env="CORS_CREDENTIALS")
    cors_methods_env: str = Field(default="GET,POST,PUT,DELETE,OPTIONS", env="CORS_METHODS")
    cors_headers_env: str = Field(default="Content-Type,Authorization", env="CORS_HEADERS")
    
    @property
    def cors_origins(self) -> List[str]:
        """Parse CORS origins from comma-separated string"""
        if self.cors_origins_env == "*":
            return ["*"]
        return [origin.strip() for origin in self.cors_origins_env.split(',') if origin.strip()]
    
    @property
    def cors_methods(self) -> List[str]:
        """Parse CORS methods from comma-separated string"""
        if self.cors_methods_env == "*":
            return ["*"]
        return [method.strip() for method in self.cors_methods_env.split(',') if method.strip()]
    
    @property
    def cors_headers(self) -> List[str]:
        """Parse CORS headers from comma-separated string"""
        if self.cors_headers_env == "*":
            return ["*"]
        return [header.strip() for header in self.cors_headers_env.split(',') if header.strip()]
    
    # Database Configuration (for future use)
    database_url: str = Field(default="sqlite:///./rsgpt.db", env="DATABASE_URL")
    
    # Auth0 Configuration
    auth0_client_id: str = Field(default="", env="AUTH0_CLIENT_ID")
    auth0_client_secret: str = Field(default="", env="AUTH0_CLIENT_SECRET")
    auth0_domain: str = Field(default="", env="AUTH0_DOMAIN")
    auth0_audience: str = Field(default="", env="AUTH0_AUDIENCE")

    # Auth0 M2M Configuration (for BE -> AI-Core service communication)
    auth0_ai_core_audience: str = Field(default="", env="AUTH0_AI_CORE_AUDIENCE")

    # API Configuration
    user_license_api_url: str = Field(default="", env="USER_LICENSE_API_URL")
    user_org_license_api_token: str = Field(default="", env="USER_ORG_LICENSE_API_TOKEN")
        
    # Service Endpoints
    ai_core_url: str = Field(default="http://localhost:8090", env="AI_CORE_URL")

    # Service Authentication
    ai_core_service_token: str = Field(default="", env="AI_CORE_SERVICE_TOKEN")
    desktop_service_token: str = Field(default="", env="DESKTOP_SERVICE_TOKEN")
    github_actions_service_token: str = Field(default="", env="GITHUB_ACTIONS_SERVICE_TOKEN")

    # AWS S3 Configuration
    aws_region: str = Field(default="us-east-2", env="AWS_REGION")
    mcp_releases_s3_bucket: str = Field(default="rsinsight-mcp-releases-staging", env="MCP_RELEASES_S3_BUCKET")
    desktop_releases_s3_bucket: str = Field(default="rsinsight-desktop-releases-staging", env="DESKTOP_RELEASES_S3_BUCKET")
    
    # Admin API Configuration
    admin_api_token: str = Field(default="", env="ADMIN_API_TOKEN")

    # Logging
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    
    model_config = {
        "env_file": ".env",
        "case_sensitive": False,
        "env_ignore_empty": True,
        "extra": "ignore"
    }
    
    @property
    def is_development(self) -> bool:
        """Check if running in development mode"""
        return self.environment == Environment.DEVELOPMENT
    
    @property
    def is_production(self) -> bool:
        """Check if running in production mode"""
        return self.environment == Environment.PRODUCTION
    
    @property
    def is_testing(self) -> bool:
        """Check if running in testing mode"""
        return self.environment == Environment.TESTING


class DevelopmentSettings(Settings):
    """Development-specific settings"""
    debug: bool = True
    log_level: str = "DEBUG"
    # Allow localhost for development
    cors_origins_env: str = Field(default="http://localhost:3000,http://localhost:8080,http://127.0.0.1:3000", env="CORS_ORIGINS")


class ProductionSettings(Settings):
    """Production-specific settings"""
    debug: bool = False
    log_level: str = "WARNING"
    # Production requires explicit CORS configuration - no default


def get_settings() -> Settings:
    """Get settings based on current environment"""
    import os
    environment = Environment(os.getenv("ENVIRONMENT", Environment.DEVELOPMENT))
    
    if environment == Environment.PRODUCTION:
        return ProductionSettings()
    elif environment == Environment.DEVELOPMENT:
        return DevelopmentSettings()
    else:
        return Settings()


# Global settings instance
settings = get_settings() 