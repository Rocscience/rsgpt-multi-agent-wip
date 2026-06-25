"""Admin API routes for managing quota requests"""

import logging
from uuid import UUID
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query

from app.dependencies import verify_admin_token
from app.db_interface.quota_requests import (
    get_pending_quota_requests_with_users,
    approve_quota_request,
    get_quota_requests_by_status_with_users,
    deny_quota_request
)
from app.models.quota_requests import (
    AdminQuotaRequestItem,
    AdminQuotaRequestsListResponse,
    AdminQuotaRequestActionResponse
)

logger = logging.getLogger(__name__)

admin_router = APIRouter()


@admin_router.get("/quota-requests", response_model=AdminQuotaRequestsListResponse)
async def list_quota_requests(
        status: Optional[str] = Query(None, description="Filter by status: pending, approved, denied"),
    _: bool = Depends(verify_admin_token)
):
    """
    List quota requests with user information.
    Optionally filter by status (pending, approved, denied).
    Defaults to pending if no status specified.
    """
    try:
        filter_status = status if status else "pending"
        requests = get_quota_requests_by_status_with_users(filter_status)
        items = [AdminQuotaRequestItem(**req) for req in requests]
        
        return AdminQuotaRequestsListResponse(
            requests=items,
            total=len(items)
        )
    except Exception as e:
        logger.error(f"Error listing quota requests: {e}")
        raise HTTPException(status_code=500, detail="Failed to list quota requests")


@admin_router.post("/quota-requests/{request_id}/approve", response_model=AdminQuotaRequestActionResponse)
async def approve_request(
    request_id: UUID,
    _: bool = Depends(verify_admin_token)
):
    """
    Approve a quota request and add the requested amount to the user's quota.
    Requires X-Admin-Token header.
    """
    try:
        result = approve_quota_request(request_id)
        
        return AdminQuotaRequestActionResponse(
            success=True,
            message="Quota request approved successfully",
            id=result["id"],
            status=result["status"],
            new_quota=result.get("new_quota")
        )
    except ValueError as e:
        logger.warning(f"Invalid quota request approval: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error approving quota request: {e}")
        raise HTTPException(status_code=500, detail="Failed to approve quota request")


@admin_router.post("/quota-requests/{request_id}/deny", response_model=AdminQuotaRequestActionResponse)
async def deny_request(
    request_id: UUID,
    _: bool = Depends(verify_admin_token)
):
    """
    Deny a quota request.
    Requires X-Admin-Token header.
    """
    try:
        result = deny_quota_request(request_id)
        
        return AdminQuotaRequestActionResponse(
            success=True,
            message="Quota request denied",
            id=result["id"],
            status=result["status"]
        )
    except ValueError as e:
        logger.warning(f"Invalid quota request denial: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error denying quota request: {e}")
        raise HTTPException(status_code=500, detail="Failed to deny quota request")
