"""
Quota management service with daily cron job functionality
"""

import logging
from datetime import date, datetime, timedelta
from typing import List
from app.db_models.organizations import OrganizationsORM
from app.db_interface.organizations import (
    get_organizations_for_quota_reset,
    reset_organization_quota,
    get_organization_by_id_for_quota
)
from app.db_interface.users import reset_all_users_agent_quota

logger = logging.getLogger(__name__)


class QuotaService:
    """Service for managing organization quotas and automated resets"""
    
    @staticmethod
    def get_organizations_for_quota_reset(target_date: date = None) -> List[OrganizationsORM]:
        """
        Get all organizations that have a pending quota renewal for the specified date.
        
        Args:
            target_date: Date to check for quota resets (defaults to today)
            
        Returns:
            List of organizations that need quota reset
        """
        try:
            organizations = get_organizations_for_quota_reset(target_date)
            logger.info(f"Found {len(organizations)} organizations with quota reset date: {target_date}")
            return organizations
                
        except Exception as e:
            logger.error(f"Error fetching organizations for quota reset: {str(e)}")
            raise
    
    @staticmethod
    def reset_organization_quota(organization: OrganizationsORM) -> bool:
        """
        Reset an organization's quota by setting questions_used to 0
        and updating the next reset date.
        
        Args:
            organization: Organization to reset quota for
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Calculate new reset date (30 days from today)
            new_reset_date = date.today() + timedelta(days=30)
            
            # Use DB interface to reset quota
            updated_org = reset_organization_quota(str(organization.id), new_reset_date)
            
            if updated_org:
                logger.info(
                    f"Reset quota for organization '{organization.name}' (ID: {organization.id}). "
                    f"Questions used: {organization.questions_used} -> 0. "
                    f"Next reset: {new_reset_date}"
                )
                return True
            else:
                logger.warning(f"Failed to reset quota for organization {organization.id}")
                return False
                
        except Exception as e:
            logger.error(f"Error resetting quota for organization {organization.id}: {str(e)}")
            return False
    
    @staticmethod
    def process_daily_quota_resets() -> dict:
        """
        Main function for the daily cron job.
        Finds all organizations with quota renewal due today and resets their quotas.
        
        Returns:
            Dictionary with processing results
        """
        start_time = datetime.now()
        logger.info(f"Starting daily quota reset process at {start_time}")
        
        try:
            # Get organizations that need quota reset today
            organizations = QuotaService.get_organizations_for_quota_reset()
            
            if not organizations:
                logger.info("No organizations found with quota reset due today")
                return {
                    "status": "success",
                    "message": "No organizations required quota reset",
                    "organizations_processed": 0,
                    "organizations_successful": 0,
                    "organizations_failed": 0,
                    "duration_seconds": (datetime.now() - start_time).total_seconds()
                }
            
            successful_resets = 0
            failed_resets = 0
            
            # Process each organization
            for org in organizations:
                logger.info(f"Processing quota reset for organization: {org.name} (ID: {org.id})")
                
                if QuotaService.reset_organization_quota(org):
                    successful_resets += 1
                else:
                    failed_resets += 1
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            result = {
                "status": "success" if failed_resets == 0 else "partial_success",
                "message": f"Processed {len(organizations)} organizations",
                "organizations_processed": len(organizations),
                "organizations_successful": successful_resets,
                "organizations_failed": failed_resets,
                "duration_seconds": duration,
                "processed_at": start_time.isoformat(),
                "completed_at": end_time.isoformat()
            }
            
            logger.info(
                f"Daily quota reset completed. "
                f"Processed: {len(organizations)}, "
                f"Successful: {successful_resets}, "
                f"Failed: {failed_resets}, "
                f"Duration: {duration:.2f}s"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error in daily quota reset process: {str(e)}")
            return {
                "status": "error",
                "message": str(e),
                "organizations_processed": 0,
                "organizations_successful": 0,
                "organizations_failed": 0,
                "duration_seconds": (datetime.now() - start_time).total_seconds()
            }
    
    @staticmethod
    def get_organization_by_id(organization_id: str) -> OrganizationsORM:
        """
        Get organization by ID for quota operations.
        
        Args:
            organization_id: ID of the organization to retrieve
            
        Returns:
            OrganizationORM object or None if not found
        """
        try:
            return get_organization_by_id_for_quota(organization_id)
        except Exception as e:
            logger.error(f"Error getting organization {organization_id}: {str(e)}")
            raise
    
    @staticmethod
    def reset_all_agent_quotas() -> dict:
        """
        Reset agent quota for all users.
        Sets agent_quota to 10 and agent_quota_used to 0.
        
        Returns:
            Dictionary with processing results
        """
        start_time = datetime.now()
        logger.info(f"Starting agent quota reset for all users at {start_time}")
        
        try:
            users_reset = reset_all_users_agent_quota()
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            result = {
                "status": "success",
                "message": f"Reset agent quota for {users_reset} users",
                "users_reset": users_reset,
                "duration_seconds": duration,
                "processed_at": start_time.isoformat(),
                "completed_at": end_time.isoformat()
            }
            
            logger.info(f"Agent quota reset completed. Users reset: {users_reset}, Duration: {duration:.2f}s")
            return result
            
        except Exception as e:
            logger.error(f"Error in agent quota reset: {str(e)}")
            return {
                "status": "error",
                "message": str(e),
                "users_reset": 0,
                "duration_seconds": (datetime.now() - start_time).total_seconds()
            }


# Standalone function for the cron job
def daily_quota_reset_job():
    """
    Standalone function to be called by the cron scheduler.
    This is the entry point for the daily quota reset job.
    
    Processes:
    1. Organization quota resets (based on quota_reset_date)
    2. Agent quota resets (on the 1st of each month)
    """
    try:
        result = QuotaService.process_daily_quota_resets()
        logger.info(f"Daily quota reset job completed with status: {result['status']}")
        
        # Reset agent quotas on the 1st of each month
        today = date.today()
        if today.day == 1:
            logger.info("First of the month - resetting agent quotas for all users")
            agent_result = QuotaService.reset_all_agent_quotas()
            result["agent_quota_reset"] = agent_result
            logger.info(f"Agent quota reset completed with status: {agent_result['status']}")
        
        return result
    except Exception as e:
        logger.error(f"Unhandled error in daily quota reset job: {str(e)}")
        raise
