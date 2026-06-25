"""Database configuration and setup"""

import logging
import ssl
import time
from functools import wraps
from typing import Any, Callable, Dict

from sqlalchemy import create_engine, event, text
from sqlalchemy.exc import DisconnectionError, OperationalError
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import Pool

from app.config import settings

from .base import BaseDbModel

logger = logging.getLogger(__name__)


def _get_async_database_url() -> str:
    """
    Convert sync database URL to async (asyncpg) URL.

    Also strips query parameters like sslmode that asyncpg doesn't understand.
    asyncpg uses different SSL configuration via connect_args.
    """
    url = settings.database_url

    # Convert to asyncpg driver
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    elif url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+asyncpg://", 1)

    # Strip query parameters that asyncpg doesn't understand (sslmode, channel_binding)
    # asyncpg uses 'ssl' parameter in connect_args instead
    if "?" in url:
        base_url = url.split("?")[0]
        return base_url

    return url


# Database engine configuration with SSL-friendly connection pooling
engine_kwargs = {
    "echo": settings.is_development,  # Show SQL queries in development
    # Connection pool settings optimized for production SSL connections
    "pool_size": 10,  # Number of connections to keep open
    "max_overflow": 20,  # Additional connections beyond pool_size
    "pool_pre_ping": True,  # Verify connections before use
    "pool_recycle": 3600,  # Recycle connections after 1 hour
    "pool_timeout": 30,  # Timeout for getting connection from pool
}

# Add SSL-specific connection arguments for production
if settings.is_production:
    # SSL connection arguments to handle production database connections
    engine_kwargs.update(
        {
            "connect_args": {  # type: ignore[dict-item]
                "sslmode": "require",
                "connect_timeout": 10,
            }
        }
    )

# Create SQLAlchemy sync engine
engine = create_engine(settings.database_url, **engine_kwargs)

# Async engine configuration (for SDK sessions)
# Note: asyncpg uses different SSL parameters than psycopg2
async_engine_kwargs: Dict[str, Any] = {
    "echo": settings.is_development,
    "pool_size": 10,
    "max_overflow": 20,
    "pool_pre_ping": True,
    "pool_recycle": 3600,
}

if settings.is_production:
    # Create SSL context for asyncpg (requires SSL but doesn't verify cert for NeonDB)
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE

    async_engine_kwargs["connect_args"] = {
        "ssl": ssl_context,  # asyncpg uses 'ssl' not 'sslmode'
        "timeout": 10,
    }

# Create SQLAlchemy async engine for SDK sessions
async_engine: AsyncEngine = create_async_engine(
    _get_async_database_url(), **async_engine_kwargs
)


# Add connection pool event listeners for better SSL handling
@event.listens_for(Pool, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """Set connection parameters on new connections"""
    if settings.is_production:
        logger.debug("New database connection established")


@event.listens_for(Pool, "checkout")
def receive_checkout(dbapi_connection, connection_record, connection_proxy):
    """Log when connections are checked out"""
    logger.debug("Database connection checked out from pool")


@event.listens_for(Pool, "checkin")
def receive_checkin(dbapi_connection, connection_record):
    """Log when connections are returned to pool"""
    logger.debug("Database connection returned to pool")


# Create Session class
Session = sessionmaker(bind=engine)

# Use BaseDbModel as the base class for all models
Base = BaseDbModel


def with_db_retry(max_retries: int = 3, retry_delay: float = 1.0):
    """
    Decorator to retry database operations on SSL connection failures.

    Args:
        max_retries: Maximum number of retry attempts
        retry_delay: Delay between retries in seconds
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception: Exception | None = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except (OperationalError, DisconnectionError) as e:
                    last_exception = e
                    error_msg = str(e).lower()

                    # Check if it's an SSL connection error that should be retried
                    is_ssl_error = any(
                        keyword in error_msg
                        for keyword in [
                            "ssl connection has been closed",
                            "connection already closed",
                            "server closed the connection",
                            "lost connection",
                            "connection was killed",
                        ]
                    )

                    if not is_ssl_error or attempt == max_retries:
                        # If it's not an SSL error or we've exhausted retries, re-raise
                        logger.error(
                            f"Database operation failed after {attempt + 1} attempts: {e}"
                        )
                        raise e

                    # Log the retry attempt
                    logger.warning(
                        f"SSL connection error on attempt {attempt + 1}/{max_retries + 1}. "
                        f"Retrying in {retry_delay}s... Error: {e}"
                    )

                    # Wait before retrying
                    time.sleep(retry_delay)

                    # Dispose of the engine connection pool to force new connections
                    engine.dispose()

            # This shouldn't be reached, but just in case
            if last_exception is not None:
                raise last_exception
            raise RuntimeError("Unexpected error: no exception to raise")

        return wrapper

    return decorator


def execute_with_retry(func: Callable, *args, **kwargs) -> Any:
    """
    Execute a database function with retry logic for SSL connection errors.

    Args:
        func: Function to execute
        *args: Arguments to pass to the function
        **kwargs: Keyword arguments to pass to the function

    Returns:
        Result of the function execution
    """

    @with_db_retry(max_retries=3, retry_delay=1.0)
    def _wrapped_execution():
        return func(*args, **kwargs)

    return _wrapped_execution()


def get_db():
    """Dependency to get database session"""
    db = Session()
    try:
        yield db
    finally:
        db.close()


def check_database_health() -> dict:
    """
    Check database connection health and return status information.

    Returns:
        Dict with health status information
    """
    health_status: Dict[str, Any] = {
        "database": "healthy",
        "connection_pool": {},
        "error": None,
    }

    try:
        # Test basic connection
        with Session() as session:
            result = session.execute(text("SELECT 1")).scalar()
            if result != 1:
                raise Exception("Basic query test failed")

        # Get connection pool information
        pool = engine.pool
        # Note: Pool statistics access may vary by SQLAlchemy version
        health_status["connection_pool"] = {
            "size": getattr(pool, "size", lambda: "unknown")(),
            "checked_in": getattr(pool, "checkedin", lambda: "unknown")(),
            "checked_out": getattr(pool, "checkedout", lambda: "unknown")(),
            "overflow": getattr(pool, "overflow", lambda: "unknown")(),
        }

        logger.info("Database health check passed")

    except Exception as e:
        health_status["database"] = "unhealthy"
        health_status["error"] = str(e)
        logger.error(f"Database health check failed: {e}")

    return health_status
