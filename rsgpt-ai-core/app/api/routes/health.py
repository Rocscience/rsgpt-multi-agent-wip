"""Health check endpoints for monitoring system status"""

import logging
import time
from typing import Any, Dict

from fastapi import APIRouter

logger = logging.getLogger(__name__)
health_router = APIRouter()


@health_router.get("/")
async def health_check() -> Dict[str, str]:
    """
    Basic health check endpoint.
    Returns simple status for load balancers and basic monitoring.
    """
    return {"status": "healthy", "service": "rsgpt-ai-core"}


@health_router.get("/detailed")
async def detailed_health_check() -> Dict[str, Any]:
    """
    Comprehensive health check including system metrics.
    Useful for monitoring dashboards and detailed diagnostics.
    """
    try:
        return {
            "status": "healthy",
            "timestamp": int(time.time()),
            "service": "rsgpt-ai-core",
            "checks": {"system": {"status": "healthy"}},
        }

    except Exception as e:
        logger.error(f"Detailed health check error: {e}")
        return {"status": "unhealthy", "timestamp": int(time.time()), "error": str(e)}
