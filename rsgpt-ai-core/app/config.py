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
    environment: Environment = Field(  # type: ignore[call-overload]
        Environment.DEVELOPMENT, env="ENVIRONMENT"
    )

    # API Configuration
    api_title: str = "RSGPT AI Core API"
    api_description: str = "AI Core Service for RSGPT"
    api_version: str = "0.1.0"

    # Server Configuration
    host: str = Field("0.0.0.0", env="HOST")  # type: ignore[call-overload]
    port: int = Field(8080, env="PORT")  # type: ignore[call-overload]
    debug: bool = Field(True, env="DEBUG")  # type: ignore[call-overload]

    # Uvicorn Configuration
    workers: int = Field(1, validation_alias="UVICORN_WORKERS")  # type: ignore[call-overload]

    # CORS Configuration - stored as strings to avoid JSON parsing
    cors_origins_env: str = Field(  # type: ignore[call-overload]
        "*", validation_alias="CORS_ORIGINS"
    )
    cors_credentials: bool = Field(  # type: ignore[call-overload]
        True, validation_alias="CORS_CREDENTIALS"
    )
    cors_methods_env: str = Field(  # type: ignore[call-overload]
        "GET,POST,PUT,DELETE,OPTIONS", validation_alias="CORS_METHODS"
    )
    cors_headers_env: str = Field(  # type: ignore[call-overload]
        "Content-Type,Authorization", validation_alias="CORS_HEADERS"
    )

    @property
    def cors_origins(self) -> List[str]:
        """Parse CORS origins from comma-separated string"""
        if self.cors_origins_env == "*":
            return ["*"]
        return [
            origin.strip()
            for origin in self.cors_origins_env.split(",")
            if origin.strip()
        ]

    @property
    def cors_methods(self) -> List[str]:
        """Parse CORS methods from comma-separated string"""
        if self.cors_methods_env == "*":
            return ["*"]
        return [
            method.strip()
            for method in self.cors_methods_env.split(",")
            if method.strip()
        ]

    @property
    def cors_headers(self) -> List[str]:
        """Parse CORS headers from comma-separated string"""
        if self.cors_headers_env == "*":
            return ["*"]
        return [
            header.strip()
            for header in self.cors_headers_env.split(",")
            if header.strip()
        ]

    # Security
    secret_key: str = Field(  # type: ignore[call-overload]
        "dev-secret-key-change-in-production", env="SECRET_KEY"
    )

    # Auth0 Configuration
    auth0_domain: str = Field("", env="AUTH0_DOMAIN")  # type: ignore[call-overload]
    auth0_audience: str = Field("", env="AUTH0_AUDIENCE")  # type: ignore[call-overload]
    auth0_algorithms: str = Field("RS256", env="AUTH0_ALGORITHMS")  # type: ignore[call-overload]
    # Accepted audiences for JWT validation (comma-separated, REQUIRED)
    # Allows both Desktop (rsgpt-be-test-identifier) and BE M2M (rsgpt-ai-core-test-identifier) JWTs
    auth0_accepted_audiences_env: str = Field(  # type: ignore[call-overload]
        validation_alias="AUTH0_ACCEPTED_AUDIENCES"
    )

    @property
    def auth0_accepted_audiences(self) -> List[str]:
        """Parse accepted audiences from comma-separated string"""
        return [
            aud.strip()
            for aud in self.auth0_accepted_audiences_env.split(",")
            if aud.strip()
        ]

    # Service-to-Service Authentication
    be_service_token: str = Field("", env="BE_SERVICE_TOKEN")  # type: ignore[call-overload]
    # Unified MCP token for all MCP servers (RS2, RSPile, etc.)
    mcp_service_token: str = Field("", env="MCP_SERVICE_TOKEN")  # type: ignore[call-overload]

    # Logging
    log_level: str = Field("INFO", env="LOG_LEVEL")  # type: ignore[call-overload]

    # LLM API Keys
    openai_api_key: str = Field("", env="OPENAI_API_KEY")  # type: ignore[call-overload]
    anthropic_api_key: str = Field("", env="ANTHROPIC_API_KEY")  # type: ignore[call-overload]
    perplexity_api_key: str = Field("", env="PERPLEXITY_API_KEY")  # type: ignore[call-overload]
    xai_api_key: str = Field("", env="XAI_API_KEY")  # type: ignore[call-overload]
    google_api_key: str = Field("", env="GOOGLE_API_KEY")  # type: ignore[call-overload]

    # LLM Configuration
    default_llm_provider: str = Field(  # type: ignore[call-overload]
        "openai", env="DEFAULT_LLM_PROVIDER"
    )

    # Reranker API Keys
    cohere_api_key: str = Field("", env="COHERE_API_KEY")  # type: ignore[call-overload]

    # Encryption Configuration
    aes_encryptor_key: str = Field("", env="AES_ENCRYPTOR_KEY")  # type: ignore[call-overload]

    # Pinecone Configuration
    pinecone_api_key: str = Field(  # type: ignore[call-overload]
        "", env="PINECONE_API_KEY"
    )
    pinecone_index_name: str = Field(  # type: ignore[call-overload]
        "rsgpt-ai-core", env="PINECONE_INDEX_NAME"
    )
    pinecone_default_top_k: int = Field(  # type: ignore[call-overload]
        20, env="PINECONE_DEFAULT_TOP_K"
    )

    # RSLog MCP Server Configuration
    rslog_mcp_url: str = Field("", env="RSLOG_MCP_URL")  # type: ignore[call-overload]
    rslog_mcp_timeout: int = Field(  # type: ignore[call-overload]
        30, env="RSLOG_MCP_TIMEOUT"
    )

    # Database Configuration
    database_url: str = Field(  # type: ignore[call-overload]
        "postgresql://rsgpt_ai_core_user:rsgpt_ai_core_password@localhost:5433/rsgpt_ai_core_db",
        env="DATABASE_URL",
    )

    # Multi-agent orchestration (demo v2 port)
    multi_agent_enabled: bool = Field(True, env="MULTI_AGENT_ENABLED")  # type: ignore[call-overload]

    model_config = {
        "env_file": ".env",
        "case_sensitive": False,
        "env_ignore_empty": True,
        "extra": "ignore",
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

    @property
    def is_service_auth_enabled(self) -> bool:
        """Check if service authentication is enabled (requires both BE and MCP tokens)"""
        return bool(self.be_service_token) and bool(self.mcp_service_token)

    @property
    def service_tokens(self) -> dict[str, list[str]]:
        """
        Map service tokens to allowed endpoints.
        Returns dict of {token: [allowed_endpoints]}

        Token Scoping:
        - BE token: /chat/stream, /agent/stream, /ws/request_file_path (NOT search/rerank)
        - MCP token: /search/semantic, /rerank (unified for all MCP servers)
        """
        tokens = {}

        # BE token: chat, agent, and websocket operations (NOT search/rerank)
        if self.be_service_token:
            tokens[self.be_service_token] = [
                "/api/v1/chat/stream",
                "/api/v1/chat/",
                "/api/v1/agent/stream",
                "/api/v1/ws/request_file_path",  # For file path selection
            ]

        # Unified MCP token: search, rerank, and chat (for all MCP servers: RS2, Settle3, etc.)
        if self.mcp_service_token:
            tokens[self.mcp_service_token] = [
                "/api/v1/search/semantic",
                "/api/v1/rerank/",
                "/api/v1/chat/",  # Non-streaming chat for Settle3 and other MCP servers
            ]

        return tokens


class DevelopmentSettings(Settings):
    """Development-specific settings"""

    debug: bool = True
    log_level: str = "DEBUG"
    # Allow localhost for development
    cors_origins_env: str = Field(  # type: ignore[call-overload]
        "http://localhost:3000,http://localhost:8080,http://127.0.0.1:3000",
        validation_alias="CORS_ORIGINS",
    )


class ProductionSettings(Settings):
    """Production-specific settings"""

    debug: bool = False
    log_level: str = "WARNING"
    # Production requires explicit CORS configuration - no default


class TestingSettings(Settings):
    """Testing-specific settings"""

    debug: bool = True
    log_level: str = "DEBUG"
    # Default CORS for testing
    cors_origins_env: str = Field(  # type: ignore[call-overload]
        "http://localhost:3000", validation_alias="CORS_ORIGINS"
    )
    # Default accepted audiences for testing
    auth0_accepted_audiences_env: str = Field(  # type: ignore[call-overload]
        "test-audience", validation_alias="AUTH0_ACCEPTED_AUDIENCES"
    )


def get_settings() -> Settings:
    """Get settings based on current environment"""
    import os

    environment = Environment(os.getenv("ENVIRONMENT", Environment.DEVELOPMENT))

    if environment == Environment.PRODUCTION:
        return ProductionSettings()  # type: ignore[call-arg]
    elif environment == Environment.DEVELOPMENT:
        return DevelopmentSettings()  # type: ignore[call-arg]
    elif environment == Environment.TESTING:
        return TestingSettings()  # type: ignore[call-arg]
    else:
        return Settings()  # type: ignore[call-arg]


# Global settings instance
settings = get_settings()
