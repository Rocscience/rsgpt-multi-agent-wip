"""Database interface for RSLog user settings"""

import logging
from typing import Optional
from uuid import UUID
from datetime import datetime, timezone

from app.db_models.users import RSLogUserSettingsORM
from app.models.rslog import CreateRSLogSettingsRequest, UpdateRSLogSettingsRequest
from app.db_models.connection import Session, with_db_retry

logger = logging.getLogger(__name__)


@with_db_retry(max_retries=3, retry_delay=1.0)
def get_rslog_settings_by_user_id(user_id: UUID) -> Optional[RSLogUserSettingsORM]:
    """Get RSLog settings for a user"""
    try:
        with Session() as session:
            settings = session.query(RSLogUserSettingsORM).filter(
                RSLogUserSettingsORM.user_id == user_id,
                RSLogUserSettingsORM.deleted_at.is_(None)
            ).first()
            if settings:
                session.expunge(settings)
            return settings
    except Exception as e:
        logger.error(f"Error getting RSLog settings for user {user_id}: {e}")
        raise e


@with_db_retry(max_retries=3, retry_delay=1.0)
def create_rslog_settings(user_id: UUID, settings_request: CreateRSLogSettingsRequest) -> RSLogUserSettingsORM:
    """Create RSLog settings for a user"""
    try:
        logger.info(f"Creating RSLog settings for user: {user_id}")
        with Session() as session:
            settings = session.query(RSLogUserSettingsORM).filter(
                RSLogUserSettingsORM.user_id == user_id
            ).first()

            if settings:
                settings.company = settings_request.company
                settings.username = settings_request.username
                settings.access_token = settings_request.access_token
                settings.refresh_token = settings_request.refresh_token
                settings.expires_in = settings_request.expires_in
                settings.token_created_at = datetime.now(timezone.utc)
                settings.is_connected = settings_request.is_connected
                settings.deleted_at = None
            else:
                settings = RSLogUserSettingsORM(
                    user_id=user_id,
                    company=settings_request.company,
                    username=settings_request.username,
                    access_token=settings_request.access_token,
                    refresh_token=settings_request.refresh_token,
                    expires_in=settings_request.expires_in,
                    token_created_at=datetime.now(timezone.utc),
                    is_connected=settings_request.is_connected
                )
                session.add(settings)

            session.commit()
            session.refresh(settings)
            logger.info(f"RSLog settings stored: {settings}")
            session.expunge(settings)
            return settings
    except Exception as e:
        logger.error(f"Error creating RSLog settings for user {user_id}: {e}")
        raise e


@with_db_retry(max_retries=3, retry_delay=1.0)
def update_rslog_settings(user_id: UUID, settings_request: UpdateRSLogSettingsRequest) -> Optional[RSLogUserSettingsORM]:
    """Update RSLog settings for a user"""
    try:
        logger.info(f"Updating RSLog settings for user: {user_id}")
        with Session() as session:
            settings = session.query(RSLogUserSettingsORM).filter(
                RSLogUserSettingsORM.user_id == user_id,
                RSLogUserSettingsORM.deleted_at.is_(None)
            ).first()
            
            if not settings:
                logger.warning(f"No RSLog settings found for user {user_id}")
                return None
            
            # Update fields if provided
            if settings_request.access_token is not None:
                settings.access_token = settings_request.access_token
                settings.token_created_at = datetime.now(timezone.utc)
            
            if settings_request.refresh_token is not None:
                settings.refresh_token = settings_request.refresh_token
            
            if settings_request.expires_in is not None:
                settings.expires_in = settings_request.expires_in
            
            if settings_request.is_connected is not None:
                settings.is_connected = settings_request.is_connected
            
            session.commit()
            session.refresh(settings)
            logger.info(f"RSLog settings updated: {settings}")
            session.expunge(settings)
            return settings
    except Exception as e:
        logger.error(f"Error updating RSLog settings for user {user_id}: {e}")
        raise e


@with_db_retry(max_retries=3, retry_delay=1.0)
def delete_rslog_settings(user_id: UUID) -> bool:
    """Delete (soft delete) RSLog settings for a user"""
    try:
        logger.info(f"Deleting RSLog settings for user: {user_id}")
        with Session() as session:
            settings = session.query(RSLogUserSettingsORM).filter(
                RSLogUserSettingsORM.user_id == user_id,
                RSLogUserSettingsORM.deleted_at.is_(None)
            ).first()
            
            if not settings:
                logger.warning(f"No RSLog settings found for user {user_id}")
                return False
            
            settings.deleted_at = datetime.now(timezone.utc)
            settings.is_connected = False
            session.commit()
            logger.info(f"RSLog settings deleted for user: {user_id}")
            return True
    except Exception as e:
        logger.error(f"Error deleting RSLog settings for user {user_id}: {e}")
        raise e
