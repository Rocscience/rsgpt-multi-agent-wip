"""
Quota management models for production monitoring
"""

from typing import List, Optional
from pydantic import BaseModel


class SchedulerStatus(BaseModel):
    """Scheduler status information for production monitoring"""
    scheduler_running: bool
    job_count: int
    jobs: List[dict]
    error: Optional[str] = None
