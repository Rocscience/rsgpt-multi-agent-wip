"""Database interface for quota requests"""

import logging
from typing import List, Dict, Any
from uuid import UUID

from sqlalchemy.orm import joinedload

from app.db_models.quota_requests import QuotaRequestsORM, QuotaRequestStatus
from app.db_models.users import UsersORM
from app.db_models.connection import Session

logger = logging.getLogger(__name__)


def create_quota_request(user_id: UUID, requested_quota: int, reason: str) -> QuotaRequestsORM:
    """Create a new quota request"""
    try:
        logger.info(f"Creating quota request for user_id: {user_id}, requested_quota: {requested_quota}")
        with Session() as session:
            quota_request = QuotaRequestsORM(
                user_id=user_id,
                requested_quota=requested_quota,
                reason=reason,
                status=QuotaRequestStatus.PENDING.value
            )
            session.add(quota_request)
            session.commit()
            session.refresh(quota_request)
            logger.info(f"Quota request created: {quota_request.id}")
            session.expunge(quota_request)
            return quota_request
    except Exception as e:
        logger.error(f"Error creating quota request: {e}")
        raise e


def get_quota_requests_by_user_id(user_id: UUID) -> list[QuotaRequestsORM]:
    """Get all quota requests for a user"""
    try:
        logger.info(f"Getting quota requests for user_id: {user_id}")
        with Session() as session:
            requests = session.query(QuotaRequestsORM).filter(
                QuotaRequestsORM.user_id == user_id,
                QuotaRequestsORM.deleted_at.is_(None)
            ).order_by(QuotaRequestsORM.created_at.desc()).all()
            for req in requests:
                session.expunge(req)
            return requests
    except Exception as e:
        logger.error(f"Error getting quota requests: {e}")
        raise e


def get_pending_quota_requests() -> list[QuotaRequestsORM]:
    """Get all pending quota requests"""
    try:
        logger.info("Getting all pending quota requests")
        with Session() as session:
            requests = session.query(QuotaRequestsORM).filter(
                QuotaRequestsORM.status == QuotaRequestStatus.PENDING.value,
                QuotaRequestsORM.deleted_at.is_(None)
            ).order_by(QuotaRequestsORM.created_at.asc()).all()
            for req in requests:
                session.expunge(req)
            return requests
    except Exception as e:
        logger.error(f"Error getting pending quota requests: {e}")
        raise e


def get_pending_quota_requests_with_users() -> List[Dict[str, Any]]:
    """Get all pending quota requests with user information for admin dashboard"""
    try:
        logger.info("Getting pending quota requests with user info")
        with Session() as session:
            requests = session.query(QuotaRequestsORM).options(
                joinedload(QuotaRequestsORM.users_orm)
            ).filter(
                QuotaRequestsORM.status == QuotaRequestStatus.PENDING.value,
                QuotaRequestsORM.deleted_at.is_(None)
            ).order_by(QuotaRequestsORM.created_at.asc()).all()
            
            result = []
            for req in requests:
                user = req.users_orm
                result.append({
                    "id": str(req.id),
                    "user_id": str(req.user_id),
                    "user_name": user.name if user else None,
                    "user_email": user.email if user else None,
                    "current_quota": user.agent_quota if user else 10,
                    "current_used": user.agent_quota_used if user else 0,
                    "requested_quota": req.requested_quota,
                    "reason": req.reason,
                    "status": req.status,
                    "created_at": req.created_at.isoformat() if req.created_at else None
                })
            
            logger.info(f"Found {len(result)} pending quota requests")
            return result
    except Exception as e:
        logger.error(f"Error getting pending quota requests with users: {e}")
        raise e


def get_quota_request_by_id(request_id: UUID) -> QuotaRequestsORM:
    """Get a quota request by ID"""
    try:
        logger.info(f"Getting quota request by id: {request_id}")
        with Session() as session:
            request = session.query(QuotaRequestsORM).filter(
                QuotaRequestsORM.id == request_id,
                QuotaRequestsORM.deleted_at.is_(None)
            ).first()
            if request:
                session.expunge(request)
            return request
    except Exception as e:
        logger.error(f"Error getting quota request by id: {e}")
        raise e


def approve_quota_request(request_id: UUID) -> Dict[str, Any]:
    """
    Approve a quota request and add the requested amount to user's agent_quota.
    Returns the updated request info.
    """
    try:
        logger.info(f"Approving quota request: {request_id}")
        with Session() as session:
            # Get the request with user
            request = session.query(QuotaRequestsORM).options(
                joinedload(QuotaRequestsORM.users_orm)
            ).filter(
                QuotaRequestsORM.id == request_id,
                QuotaRequestsORM.deleted_at.is_(None)
            ).first()
            
            if not request:
                raise ValueError(f"Quota request not found: {request_id}")
            
            if request.status != QuotaRequestStatus.PENDING.value:
                raise ValueError(f"Quota request is not pending: {request.status}")
            
            # Update request status
            request.status = QuotaRequestStatus.APPROVED.value
            
            # Update user's agent quota
            user = session.query(UsersORM).filter(
                UsersORM.id == request.user_id
            ).first()
            
            if user:
                old_quota = user.agent_quota
                user.agent_quota += request.requested_quota
                logger.info(f"Updated user {user.id} agent_quota: {old_quota} -> {user.agent_quota}")
            
            session.commit()
            
            return {
                "id": str(request.id),
                "status": request.status,
                "user_id": str(request.user_id),
                "new_quota": user.agent_quota if user else None
            }
    except Exception as e:
        logger.error(f"Error approving quota request: {e}")
        raise e


def deny_quota_request(request_id: UUID) -> Dict[str, Any]:
    """
    Deny a quota request.
    Returns the updated request info.
    """
    try:
        logger.info(f"Denying quota request: {request_id}")
        with Session() as session:
            request = session.query(QuotaRequestsORM).filter(
                QuotaRequestsORM.id == request_id,
                QuotaRequestsORM.deleted_at.is_(None)
            ).first()
            
            if not request:
                raise ValueError(f"Quota request not found: {request_id}")
            
            if request.status != QuotaRequestStatus.PENDING.value:
                raise ValueError(f"Quota request is not pending: {request.status}")
            
            # Update request status
            request.status = QuotaRequestStatus.DENIED.value
            session.commit()
            
            return {
                "id": str(request.id),
                "status": request.status,
                "user_id": str(request.user_id)
            }
    except Exception as e:
        logger.error(f"Error denying quota request: {e}")
        raise e

def get_quota_requests_by_status_with_users(status: str) -> List[Dict[str, Any]]:
    """Get quota requests by status with user information for admin dashboard"""
    try:
        logger.info(f"Getting quota requests with status: {status}")
        with Session() as session:
            requests = session.query(QuotaRequestsORM).options(
                joinedload(QuotaRequestsORM.users_orm)
            ).filter(
                QuotaRequestsORM.status == status,
                QuotaRequestsORM.deleted_at.is_(None)
            ).order_by(QuotaRequestsORM.created_at.desc()).all()
            
            result = []
            for req in requests:
                user = req.users_orm
                result.append({
                    "id": str(req.id),
                    "user_id": str(req.user_id),
                    "user_name": user.name if user else None,
                    "user_email": user.email if user else None,
                    "current_quota": user.agent_quota if user else 10,
                    "current_used": user.agent_quota_used if user else 0,
                    "requested_quota": req.requested_quota,
                    "reason": req.reason,
                    "status": req.status,
                    "created_at": req.created_at.isoformat() if req.created_at else None
                })
            
            logger.info(f"Found {len(result)} quota requests with status {status}")
            return result
    except Exception as e:
        logger.error(f"Error getting quota requests by status: {e}")
        raise e