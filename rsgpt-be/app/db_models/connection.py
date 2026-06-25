"""Database configuration and setup"""

import time
import logging
from typing import Callable, Any
from functools import wraps
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import OperationalError, DisconnectionError
from sqlalchemy.pool import Pool

from app.config import settings
from .base import BaseDbModel

logger = logging.getLogger(__name__)

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

# Add connection timeout for production
if settings.is_production:
    # Connection arguments for production (SSL mode is controlled via DATABASE_URL)
    engine_kwargs.update({
        "connect_args": {
            "connect_timeout": 10,
        }
    })

# Create SQLAlchemy engine
engine = create_engine(settings.database_url, **engine_kwargs)

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
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except (OperationalError, DisconnectionError) as e:
                    last_exception = e
                    error_msg = str(e).lower()
                    
                    # Check if it's an SSL connection error that should be retried
                    is_ssl_error = any(keyword in error_msg for keyword in [
                        'ssl connection has been closed',
                        'connection already closed',
                        'server closed the connection',
                        'lost connection',
                        'connection was killed'
                    ])
                    
                    if not is_ssl_error or attempt == max_retries:
                        # If it's not an SSL error or we've exhausted retries, re-raise
                        logger.error(f"Database operation failed after {attempt + 1} attempts: {e}")
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
            raise last_exception
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
    health_status = {
        "database": "healthy",
        "connection_pool": {},
        "error": None
    }
    
    try:
        # Test basic connection
        with Session() as session:
            result = session.execute(text("SELECT 1")).scalar()
            if result != 1:
                raise Exception("Basic query test failed")
        
        # Get connection pool information
        pool = engine.pool
        health_status["connection_pool"] = {
            "size": pool.size(),
            "checked_in": pool.checkedin(),
            "checked_out": pool.checkedout(),
            "overflow": pool.overflow(),
        }
        
        logger.info("Database health check passed")
        
    except Exception as e:
        health_status["database"] = "unhealthy"
        health_status["error"] = str(e)
        logger.error(f"Database health check failed: {e}")
    
    return health_status 