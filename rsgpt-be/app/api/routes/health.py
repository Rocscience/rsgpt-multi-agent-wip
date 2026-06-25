"""Health check endpoints for monitoring database and system status"""

import time
import logging
from typing import Dict, Any
from fastapi import APIRouter, HTTPException

from app.db_models.connection import check_database_health

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/health", tags=["health"])


@router.get("/")
async def health_check() -> Dict[str, str]:
    """
    Basic health check endpoint.
    Returns simple status for load balancers and basic monitoring.
    """
    return {"status": "healthy", "service": "rsgpt-backend"}


@router.get("/database")
async def database_health_check() -> Dict[str, Any]:
    """
    Detailed database health check.
    Returns database connection status and pool information.
    """
    try:
        health_status = check_database_health()
        
        # Return 503 if database is unhealthy
        if health_status["database"] != "healthy":
            logger.warning(f"Database health check failed: {health_status['error']}")
            raise HTTPException(
                status_code=503,
                detail={
                    "status": "unhealthy",
                    "error": health_status["error"],
                    "connection_pool": health_status.get("connection_pool", {})
                }
            )
        
        return {
            "status": "healthy",
            "database": health_status["database"],
            "connection_pool": health_status["connection_pool"]
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Health check endpoint error: {e}")
        raise HTTPException(
            status_code=500,
            detail={"status": "error", "message": "Health check failed"}
        )


@router.get("/detailed")
async def detailed_health_check() -> Dict[str, Any]:
    """
    Comprehensive health check including database and system metrics.
    Useful for monitoring dashboards and detailed diagnostics.
    """
    try:
        # Get database health
        db_health = check_database_health()
        
        # You can add more health checks here
        # For example: Redis, external APIs, disk space, etc.
        
        overall_status = "healthy"
        if db_health["database"] != "healthy":
            overall_status = "degraded"
        
        return {
            "status": overall_status,
            "timestamp": int(time.time()),
            "checks": {
                "database": {
                    "status": db_health["database"],
                    "connection_pool": db_health["connection_pool"],
                    "error": db_health["error"]
                }
            }
        }
    
    except Exception as e:
        logger.error(f"Detailed health check error: {e}")
        return {
            "status": "unhealthy",
            "timestamp": int(time.time()),
            "error": str(e)
        }
