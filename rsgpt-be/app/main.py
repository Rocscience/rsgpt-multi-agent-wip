"""Main FastAPI application entry point"""

# Load environment variables first, before any other imports
from dotenv import load_dotenv
load_dotenv()

import logging
import subprocess
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.models.system import RootResponse, HealthResponse, ConfigResponse, VersionResponse
from fastapi import HTTPException
from app.api.main import api_app
from app.config import settings
from app.scheduler import setup_scheduler, start_scheduler, stop_scheduler
import uvicorn

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)


def get_git_sha() -> str:
    """Get the current Git commit SHA"""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"], 
            capture_output=True, 
            text=True, 
            check=True
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    logger.info(f"Starting RSGPT Backend API in {settings.environment} mode")
    logger.info(f"Debug mode: {settings.debug}")
    logger.info(f"CORS origins: {settings.cors_origins}")
    
    # Setup and start the scheduler
    try:
        setup_scheduler()
        start_scheduler()
        logger.info("Scheduler started successfully")
    except Exception as e:
        logger.error(f"Failed to start scheduler: {str(e)}")
        # Don't fail the entire application if scheduler fails
        # The API can still work without the cron job
    
    yield
    
    # Shutdown
    logger.info("Shutting down RSGPT Backend API")
    
    # Stop the scheduler gracefully
    try:
        stop_scheduler()
        logger.info("Scheduler stopped successfully")
    except Exception as e:
        logger.error(f"Error stopping scheduler: {str(e)}")


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
        message="RSGPT Backend API is running",
        environment=settings.environment,
        version=settings.api_version,
        docs_url="/docs" if settings.is_development else None
    )

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint for load balancers"""
    return HealthResponse(
        message="Service is healthy",
        status="healthy",
        service="rsgpt-backend",
        environment=settings.environment,
        debug=settings.debug
    )

@app.get("/config", response_model=ConfigResponse)
async def get_config():
    """Get non-sensitive configuration information (development only)"""
    
    if not settings.is_development:
        raise HTTPException(
            status_code=403,
            detail="Configuration endpoint only available in development mode"
        )
    
    return ConfigResponse(
        message="Configuration data retrieved successfully",
        environment=settings.environment,
        debug=settings.debug,
        host=settings.host,
        port=settings.port,
        cors_origins=settings.cors_origins,
        log_level=settings.log_level
    )


@app.get("/version", response_model=VersionResponse)
async def get_version():
    """Get version information including Git commit SHA"""
    return VersionResponse(
        message="Version information retrieved successfully",
        service="rsgpt-backend",
        version=settings.api_version,
        git_sha=get_git_sha(),
        environment=settings.environment
    )


def start():
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.is_development,
        log_level=settings.log_level.lower()
    )


if __name__ == "__main__":
    start()