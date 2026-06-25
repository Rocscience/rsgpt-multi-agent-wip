"""
Quota management API endpoints for production monitoring
"""

import logging
from fastapi import APIRouter, HTTPException, Depends

from app.models.quota import SchedulerStatus
from app.scheduler import get_scheduler_status
from app.dependencies import get_current_user
from typing import Dict, Any

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/status", response_model=SchedulerStatus)
async def get_scheduler_status_endpoint(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Get the current status of the scheduler and scheduled jobs.
    Useful for monitoring the cron job system in production.
    """
    try:
        status = get_scheduler_status()
        return SchedulerStatus(**status)
    except Exception as e:
        logger.error(f"Error getting scheduler status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get scheduler status: {str(e)}")
