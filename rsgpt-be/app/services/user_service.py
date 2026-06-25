from app.db_interface.users import get_user_id_by_auth0_sub, create_user
from app.models.users import CreateUserRequest
from datetime import datetime
from app.db_models.users import UsersORM
from app.db_models.organizations import OrganizationsORM
from app.db_interface.organizations import get_organization_by_user_id, create_organization, add_user_to_organization, update_organization_quota, get_organization_by_id, reassign_user_organization
from app.models.organizations import CreateOrganizationRequest
from datetime import timedelta
import logging
from app.models.consts import QUESTIONS_PER_FCL_LICENSE, QUESTIONS_PER_PCL_LICENSE, QUESTIONS_FOR_NO_LICENSE
from app.models.enums import User_Permission_Enum
from dataclasses import dataclass
from uuid import UUID
from fastapi import Response
from app.db_interface.users import get_user_settings_by_user_id, create_user_settings, update_user_settings
from app.db_models.users import UserSettingsORM
from app.models.users import UserSettingsRequest, UserSettingsResponse

logger = logging.getLogger(__name__)

@dataclass
class OrganizationInformation:
    organization_id: str
    organization_name:str
    question_quota: int
    questions_used: int
    access_level: User_Permission_Enum
    rocportal_status: bool

class UserService: 
    def __init__(self):
        pass

    def get_or_create_user(self, user_data: dict):
        # Check if the user exists in the database
        user_id = get_user_id_by_auth0_sub(user_data.get("sub"))

        if user_id is None:
            user_request = CreateUserRequest(
                auth0_sub=user_data.get("sub"),
                email=user_data.get("email"),
                name=user_data.get("name"),
                first_name=user_data.get("given_name"),
                last_name=user_data.get("family_name"),
                profile_picture_url=user_data.get("picture"),
                last_login=datetime.now().isoformat(),
                is_active=True
            )
            user_id = create_user(user_request).id
        return user_id
 
    def update_organization_and_quota(self, user_id: UUID, rocportal_status: dict) -> OrganizationsORM:
        """Sync the rocportal organization for a user.

        Key behaviour (RSI-218):
        1. Always update an existing org's quota, access_level, and rocportal_status from
           the latest rocportal data — not just at creation time.
        2. If the user is currently assigned to a *different* org than the one rocportal
           says they belong to (e.g. a self-created BASIC org), reassign user_organizations
           to point to the correct licensed org. This prevents users from being stuck in
           their own low-quota org when they have a FLEXIBLE licence on a company org.
        """

        organization_data = self.extract_organization_data(user_id, rocportal_status)

        # Ensure the rocportal org exists in our DB (create if first time)
        organization = get_organization_by_id(organization_data.organization_id)

        if organization is None:
            organization_request = CreateOrganizationRequest(
                id=organization_data.organization_id,
                name=organization_data.organization_name,
                question_quota=organization_data.question_quota,
                access_level=organization_data.access_level,
                quota_reset_date=(datetime.now() + timedelta(days=30)).date(),
                rocportal_status=organization_data.rocportal_status
            )
            organization = create_organization(organization_request)
            logger.info(f"Created new organization {organization.id} for user {user_id}")

        else:
            # Update quota, rocportal_status, AND access_level from the latest rocportal data
            organization = update_organization_quota(
                organization.id,
                organization_data.question_quota,
                organization_data.rocportal_status,
                access_level=organization_data.access_level
            )
            logger.info(f"Updated organization {organization.id} quota={organization_data.question_quota} access_level={organization_data.access_level}")

        # Check whether the user is already assigned to the correct org
        current_org = get_organization_by_user_id(user_id)

        if current_org is None:
            # No org assigned yet — add the user
            add_user_to_organization(user_id, organization.id)
            logger.info(f"Assigned user {user_id} to organization {organization.id}")

        elif str(current_org.id) != str(organization.id):
            # User is in the wrong org (e.g. their self-created BASIC org).
            # Reassign them to the correct licensed org from rocportal.
            logger.info(
                f"User {user_id} is in org {current_org.id} (access_level={current_org.access_level}) "
                f"but rocportal says they belong to org {organization.id} "
                f"(access_level={organization_data.access_level}). Reassigning."
            )
            reassign_user_organization(user_id, organization.id)

        return organization
    
    def extract_organization_data(self, user_id: UUID, rocportal_status: dict) -> OrganizationInformation:
        """Calculate the question quota for a user"""

        # Get the organization data
        try:
            organizationData = rocportal_status.get("data", {}).get("current_organization", {})
        except Exception as e:
            logger.error(f"Error parsing rocportal status: {e}")
            raise ValueError(f"Error parsing rocportal status: {e}")
        
        # Get the organization id
        try:
            organizationId = organizationData.get("id", None)
            if organizationId is None:
                logger.error("Organization ID not found in rocportal status")
                raise ValueError("Organization ID not found in rocportal status")
        except ValueError:
            raise  # Re-raise ValueError as-is
        except Exception as e:
            logger.error(f"Error parsing rocportal status: {e}")
            raise ValueError(f"Error parsing organization ID from rocportal status: {e}")
        
        try:
            organizationName = organizationData.get("name", None)
            if organizationName == None:
                logger.error("Organization name not found in rocportal status")
                raise ValueError("Organization name not found in rocportal status")
        except Exception as e:
            logger.error(f"Error parsing rocportal status: {e}")
            raise ValueError(f"Error parsing organization name from rocportal status: {e}")
        
        # Get the licenses
        try:
            licenses = organizationData.get("licenses", [])
        except Exception as e:
            logger.error(f"Error getting licenses from organizationData for user: {user_id}. organization data: {organizationData}. Error: {str(e)}")
            raise ValueError(f"Error extracting licenses from organization data: {str(e)}")
        
        # Get the rocportal status
        try:
            rocportalStatus = rocportal_status.get("result", False)
        except Exception as e:
            logger.error(f"Error parsing rocportal status: {e}")
            raise ValueError(f"Error parsing rocportal status: {e}")
        
        # Get the quota and access level
        try:
            organizationQuestionQuota, accessLevel = self.get_quota_and_access_level_from_license_data(licenses)
        except Exception as e:
            logger.error(f"Error getting quota and access level from licenses for user: {user_id}. licenses: {licenses}. Error: {str(e)}")
            raise ValueError(f"Error calculating quota and access level from licenses: {str(e)}")
        
        return OrganizationInformation(organization_id=organizationId, 
                                       question_quota=organizationQuestionQuota, 
                                       questions_used=0, 
                                       access_level=accessLevel,
                                       organization_name=organizationName,
                                       rocportal_status=rocportalStatus
        )
    
    def get_quota_and_access_level_from_license_data(self, licenses : list):
        """Get the quota and access level from the license data"""

        active_fcl_licenses = sum(license["num_seats"] for license in licenses if license["type"] == "FCL" and license["status"] == "Active")
        active_pcl_licenses = sum(license["num_seats"] for license in licenses if license["type"] == "PCL" and license["status"] == "Active")
        organizationQuestionQuota = QUESTIONS_PER_FCL_LICENSE * active_fcl_licenses + QUESTIONS_PER_PCL_LICENSE * active_pcl_licenses
        accessLevel = User_Permission_Enum.FLEXIBLE
        
        if active_fcl_licenses == 0 and active_pcl_licenses == 0:
            organizationQuestionQuota = QUESTIONS_FOR_NO_LICENSE
            accessLevel = User_Permission_Enum.BASIC
            
        return organizationQuestionQuota, accessLevel

    def create_or_update_user_settings(self, user_id: UUID, user_settings: UserSettingsRequest) -> UserSettingsORM:
        """Create or update user settings"""
        user_settings_obj = get_user_settings_by_user_id(user_id)
        if user_settings_obj is None:
            user_settings_obj = create_user_settings(user_id, user_settings)
        else:
            user_settings_obj = update_user_settings(user_id, user_settings)
        return user_settings_obj
    
    def get_user_settings(self, user_id: UUID) -> UserSettingsORM:
        """Get user settings"""
        user_settings_obj = get_user_settings_by_user_id(user_id)

        if user_settings_obj is None:
            user_settings_obj = create_user_settings(user_id, UserSettingsRequest(
                preferred_sources=["ROC"],
                theme="system",
                language="en",
                timezone="America/New_York",
                agent_mode_opt_in=False
            ))

        return user_settings_obj
    
    def get_rocportal_status(self, user_id: UUID, user_sub: str) -> bool:
        """Get rocportal status for user, fetching from API if not in database"""
        from app.clients.rocportal_client import RocportalClient
        from app.config import settings
        import json
        
        # First try to get from database
        organization = get_organization_by_user_id(user_id)
        
        if organization is not None:
            return organization.rocportal_status
        
        # If no organization exists, fetch from rocportal API
        logger.info(f"No organization found for user {user_id}, fetching from rocportal API")
        
        rocportal_client = RocportalClient()
        
        # Use mock data in non-production environments
        if settings.environment != "production":
            rocportal_response = rocportal_client.get_moc_status(user_sub)
        else:
            rocportal_response = rocportal_client.get_rocportal_status(user_sub)
        
        if rocportal_response.status_code == 200:
            response_data = json.loads(rocportal_response._content.decode('utf-8'))

            # Check if the user is in the Rocportal
            in_rocportal = response_data.get("result", False)
            
            if not in_rocportal:
                logger.info(f"User {user_id} not found in Rocportal: {response_data.get('msg', 'User must be added to Rocportal to use the application')}")
                return False
            
            # Check if user has an organization assigned
            user_data = response_data.get("data", {})
            current_organization = user_data.get("current_organization")
            
            if current_organization is None:
                logger.info(f"User {user_id} found in Rocportal but has no organization assigned")
                return False
            
            # User has both ROC Portal access AND an organization - update quota
            self.update_organization_and_quota(user_id, response_data)
            return True

        else:
            logger.error(f"Failed to fetch rocportal status for user {user_id}: {rocportal_response.status_code}")
            # Return False as default if API call fails
            return False

    def update_rocportal_status(self, user_id: UUID, user_sub: str) -> bool:
        """Update rocportal status by always calling the rocportal API"""
        from app.clients.rocportal_client import RocportalClient
        from app.config import settings
        import json
        from fastapi import HTTPException
        
        logger.info(f"Updating rocportal status for user {user_id} from API")
        
        rocportal_client = RocportalClient()
        
        # Use mock data in non-production environments
        if settings.environment != "production":
            rocportal_response = rocportal_client.get_moc_status(user_sub)
        else:
            logger.info(f"Fetching rocportal status for user {user_id} from API")
            rocportal_response = rocportal_client.get_rocportal_status(user_sub)
        
        if rocportal_response.status_code == 200:
            response_data = json.loads(rocportal_response._content.decode('utf-8'))

            # Check if the user is in the Rocportal
            in_rocportal = response_data.get("result", False)
            
            if not in_rocportal:
                logger.info(f"User {user_id} not found in Rocportal: {response_data.get('msg', 'User must be added to Rocportal to use the application')}")
                return False
            
            # Check if user has an organization assigned
            user_data = response_data.get("data", {})
            current_organization = user_data.get("current_organization")
            
            if current_organization is None:
                logger.info(f"User {user_id} found in Rocportal but has no organization assigned")
                return False
            
            # User has both ROC Portal access AND an organization - update quota
            self.update_organization_and_quota(user_id, response_data)
            return True
        else:
            logger.error(f"Failed to update rocportal status for user {user_id}: {rocportal_response.status_code}")
            raise HTTPException(
                status_code=rocportal_response.status_code,
                detail="Rocportal status request failed"
            )