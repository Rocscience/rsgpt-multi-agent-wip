"""
APScheduler configuration for automated cron jobs
"""

import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.executors.asyncio import AsyncIOExecutor
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR
from app.services.quota_service import daily_quota_reset_job
from app.config import settings

logger = logging.getLogger(__name__)

# Configure job stores and executors
jobstores = {
    'default': MemoryJobStore()
}

executors = {
    'default': AsyncIOExecutor()
}

job_defaults = {
    'coalesce': False,
    'max_instances': 1,  # Prevent overlapping executions
    'misfire_grace_time': 1800  # 30 minutes grace period for missed executions
}

# Create the scheduler
scheduler = AsyncIOScheduler(
    jobstores=jobstores,
    executors=executors,
    job_defaults=job_defaults,
    timezone='UTC'
)


def job_listener(event):
    """Handle job execution events"""
    if event.exception:
        logger.error(f"Job {event.job_id} failed with exception: {event.exception}")
    else:
        logger.info(f"Job {event.job_id} executed successfully")


def setup_scheduler():
    """Configure and start the scheduler with quota reset job"""
    
    # Add event listeners
    scheduler.add_listener(job_listener, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)
    
    # Add the daily quota reset job
    # Runs at 2:00 AM UTC daily (off-peak hours)
    scheduler.add_job(
        func=daily_quota_reset_job,
        trigger=CronTrigger(hour=2, minute=0, timezone='UTC'),
        id='daily_quota_reset',
        name='Daily Organization Quota Reset',
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=1800  # 30 minutes grace period
    )
    
    logger.info("Scheduler configured with daily quota reset job at 2:00 AM UTC")


def start_scheduler():
    """Start the scheduler"""
    try:
        scheduler.start()
        logger.info("APScheduler started successfully")
        
        # Log scheduled jobs
        jobs = scheduler.get_jobs()
        logger.info(f"Scheduled jobs: {[job.name for job in jobs]}")
        
    except Exception as e:
        logger.error(f"Failed to start scheduler: {str(e)}")
        raise


def stop_scheduler():
    """Stop the scheduler gracefully"""
    try:
        scheduler.shutdown(wait=True)
        logger.info("APScheduler stopped successfully")
    except Exception as e:
        logger.error(f"Error stopping scheduler: {str(e)}")


def get_scheduler_status() -> dict:
    """Get scheduler status and job information"""
    try:
        jobs = scheduler.get_jobs()
        job_info = []
        
        for job in jobs:
            job_info.append({
                'id': job.id,
                'name': job.name,
                'next_run_time': job.next_run_time.isoformat() if job.next_run_time else None,
                'trigger': str(job.trigger)
            })
        
        return {
            'scheduler_running': scheduler.running,
            'jobs': job_info,
            'job_count': len(jobs)
        }
        
    except Exception as e:
        logger.error(f"Error getting scheduler status: {str(e)}")
        return {
            'scheduler_running': False,
            'error': str(e),
            'jobs': [],
            'job_count': 0
        }


