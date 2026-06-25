from fastapi import APIRouter, Depends, HTTPException
import logging
from typing import Dict, Any
from app.models.auth import AuthResponse, RocportalStatusResponse, QuotaInfoResponse
from app.models.users import UserSettingsRequest, UserSettingsResponse
from app.models.quota_requests import QuotaRequestCreate, QuotaRequestResponse
from app.services.user_service import UserService
from app.db_interface.organizations import get_organization_by_user_id
from app.db_interface.users import get_user_by_id
from app.db_interface.quota_requests import create_quota_request
from app.dependencies import get_current_user
from app.models.consts import DEFAULT_AGENT_QUOTA

logger = logging.getLogger(__name__)

user_router = APIRouter()

@user_router.get("/", response_model=AuthResponse)
async def auth(
    current_user: Dict[str, Any] = Depends(get_current_user)
    ):
    logger.info(f"User ID: {current_user['user_id']}")
    logger.info(f"User Email: {current_user['user_email']}")
    logger.info(f"User Sub: {current_user['user_sub']}")
    return AuthResponse(message=f"User authenticated: {current_user['user_sub']}")

"""
    This is the rocportal status route that is used to check if user has
    access to rocportal. It first checks the database, and if no organization
    exists, it fetches from the rocportal API and creates the organization.
    @param request: Request
    @return: JSON response with the rocportal status
"""
@user_router.get("/rocportal-status", response_model=RocportalStatusResponse)
async def rocportal_status_from_db(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    user_id = current_user["user_id"]
    user_sub = current_user["user_sub"]

    # Get the rocportal status using the service method
    try:
        user_service = UserService()
        rocportal_status = user_service.get_rocportal_status(user_id, user_sub)

        return RocportalStatusResponse(rocportal_status=rocportal_status)
    except Exception as e:
        logger.error(f"Error getting rocportal status for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail={"message": "Internal server error"})

"""
    This is the rocportal status route that is used to update
    the rocportal information from the rocportal server
    @param request: Request
    @return: JSON response with the rocportal status
"""
@user_router.put("/rocportal-status", response_model=RocportalStatusResponse)
async def rocportal_status(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    user_sub = current_user["user_sub"]
    user_id = current_user["user_id"]

    # Update rocportal status using the service method (always calls API)
    try:
        user_service = UserService()
        rocportal_result = user_service.update_rocportal_status(user_id, user_sub)

        return RocportalStatusResponse(
            rocportal_status=rocportal_result, 
            message="Rocportal status updated successfully"
        )
    except Exception as e:
        logger.error(f"Error updating rocportal status for user {user_id}: {e}")
        # Re-raise the HTTPException if it's already one, otherwise create a generic 500
        if isinstance(e, HTTPException):
            raise e
        else:
            raise HTTPException(status_code=500, detail="Rocportal status request failed")

"""
    This is the quota info route that is used to get the quota info for the user
    @return: JSON response with the quota info
"""
@user_router.get("/quota-info", response_model=QuotaInfoResponse)
async def quota_info(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    # similar to the django implemenation of the quota info
    user_id = current_user["user_id"]

    # Get the quota info for the user
    try: 
        organization = get_organization_by_user_id(user_id)
        user = get_user_by_id(user_id)

        if organization is None:
            raise HTTPException(status_code=404, detail={"message": "Organization not found for user"})

        return QuotaInfoResponse(
            organization_name=organization.name,
            question_quota=organization.question_quota,
            questions_used=organization.questions_used,
            quota_reset_date=organization.quota_reset_date,
            agent_quota=user.agent_quota if user else DEFAULT_AGENT_QUOTA,
            agent_quota_used=user.agent_quota_used if user else 0
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting quota info for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail={"message": "Internal server error"})
    
"""This is the user settings route that is used to write the user settings to the database
    It will create a new user settings object if it doesn't exist and update it if it does
    @param request: Request
    @return: JSON response with the user settings
"""
@user_router.put("/settings", response_model=UserSettingsResponse)
async def user_settings(
    user_settings: UserSettingsRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    user_id = current_user["user_id"]
    user_service = UserService()
    user_settings_obj = user_service.create_or_update_user_settings(user_id, user_settings)
    return UserSettingsResponse(
        preferred_sources=user_settings_obj.preferred_sources,
        theme=user_settings_obj.theme,
        language=user_settings_obj.language,
        timezone=user_settings_obj.timezone,
        agent_mode_opt_in=user_settings_obj.agent_mode_opt_in
    )

"""This is the user settings route that is used to get the user settings from the database
    @return: JSON response with the user settings
"""
@user_router.get("/settings", response_model=UserSettingsResponse)
async def user_settings(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    user_id = current_user["user_id"]
    user_service = UserService()
    user_settings_obj = user_service.get_user_settings(user_id)
    
    return UserSettingsResponse(
        preferred_sources=user_settings_obj.preferred_sources,
        theme=user_settings_obj.theme,
        language=user_settings_obj.language,
        timezone=user_settings_obj.timezone,
        agent_mode_opt_in=user_settings_obj.agent_mode_opt_in
    )


"""
    This endpoint allows users to request additional agent quota.
    Creates a database record for admin review.
    @param request_body: QuotaRequestCreate with requested_quota and reason
    @return: QuotaRequestResponse with success status
"""
@user_router.post("/quota-request", response_model=QuotaRequestResponse)
async def request_quota(
    request_body: QuotaRequestCreate,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    user_id = current_user["user_id"]
    
    try:
        # Create the quota request in the database
        quota_request = create_quota_request(
            user_id=user_id,
            requested_quota=request_body.requested_quota,
            reason=request_body.reason
        )
        
        return QuotaRequestResponse(
            success=True,
            message="Your quota request has been submitted. We will review it and get back to you.",
            request_id=quota_request.id
        )
        
    except Exception as e:
        logger.error(f"Error creating quota request for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail={"message": "Failed to submit quota request"})
