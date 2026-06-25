"""Main FastAPI application entry point"""

# Load environment variables first, before any other imports
from dotenv import load_dotenv

load_dotenv()

import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.api.main import api_app
from app.config import settings
from app.models.system import ConfigResponse, HealthResponse, RootResponse

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    logger.info(f"Starting RSGPT AI Core API in {settings.environment} mode")
    logger.info(f"Debug mode: {settings.debug}")
    logger.info(f"CORS origins: {settings.cors_origins}")

    # Configure tracing for non-OpenAI models
    # This enables free tracing to OpenAI dashboard even when using Anthropic/other models
    if settings.openai_api_key:
        try:
            from agents import set_tracing_export_api_key

            set_tracing_export_api_key(settings.openai_api_key)
            logger.info("✓ Tracing configured for all models (including non-OpenAI)")
        except ImportError:
            logger.warning("agents package not available - tracing not configured")
        except Exception as e:
            logger.error(f"Failed to configure tracing: {e}")
    else:
        logger.warning(
            "OpenAI API key not set - tracing will be disabled for non-OpenAI models"
        )

    yield

    # Shutdown
    logger.info("Shutting down RSGPT AI Core API")


# Create FastAPI instance with environment-specific configuration
app = FastAPI(
    title=settings.api_title,
    description=settings.api_description,
    version=settings.api_version,
    debug=False,  # Always set to False to prevent default error handling
    docs_url="/docs" if settings.is_development else None,
    redoc_url="/redoc" if settings.is_development else None,
    lifespan=lifespan,
)

# Configure CORS with environment-specific settings
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=settings.cors_credentials,
    allow_methods=settings.cors_methods,
    allow_headers=settings.cors_headers,
)

# Include API routers
app.mount("/api/v1", api_app)


@app.get("/", response_model=RootResponse)
async def root():
    """Root endpoint - API information"""
    return RootResponse(
        message="RSGPT AI Core API is running",
        environment=settings.environment,
        version=settings.api_version,
        docs_url="/docs" if settings.is_development else None,
    )


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint for load balancers"""
    return HealthResponse(
        message="Service is healthy",
        status="healthy",
        service="rsgpt-ai-core",
        environment=settings.environment,
        debug=settings.debug,
    )


@app.get("/config", response_model=ConfigResponse)
async def get_config():
    """Get non-sensitive configuration information (development only)"""

    if not settings.is_development:
        raise HTTPException(
            status_code=403,
            detail="Configuration endpoint only available in development mode",
        )

    return ConfigResponse(
        message="Configuration data retrieved successfully",
        environment=settings.environment,
        debug=settings.debug,
        host=settings.host,
        port=settings.port,
        cors_origins=settings.cors_origins,
        log_level=settings.log_level,
    )


def start():
    """
    Start the uvicorn server.

    Worker Configuration:
    - Development: Single worker with hot reload
    - Production: Multiple workers (configurable via UVICORN_WORKERS env var)

    IMPORTANT: WebSocket scaling limitation
    - The ConnectionManager uses in-memory storage for WebSocket connections
    - With multiple workers, WebSocket connections are NOT shared between workers
    - For WebSocket endpoints, AWS ALB sticky sessions are REQUIRED
    - Configure ALB with: stickiness.enabled=true, stickiness.type=lb_cookie

    For true horizontal scaling of WebSockets, consider:
    - Redis pub/sub for inter-worker communication
    - Or run WebSocket handler as a separate single-worker service
    """
    logger.info(f"Starting with {settings.workers} workers")

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        workers=settings.workers,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    start()
