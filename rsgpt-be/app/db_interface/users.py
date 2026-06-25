import logging
from datetime import datetime, timezone
from app.db_models.users import (
    UsersORM,
    UserSettingsORM,
    AgentModeOptInHistoryORM
)
from app.models.users import (
    CreateUserRequest,
    CreateUserResponse,
    UserSettingsRequest,
    UserSettingsResponse
)
from app.models.consts import DEFAULT_AGENT_QUOTA
from uuid import UUID

from app.db_models.connection import Session, with_db_retry

logger = logging.getLogger(__name__)

def create_user(user_request: CreateUserRequest) -> UsersORM:
    """Create a new user"""
    try:
        logger.info(f"Creating user: {user_request}")
        with Session() as session:
            new_user = UsersORM(
                auth0_sub=user_request.auth0_sub,
                email=user_request.email,
                name=user_request.name,
                first_name=user_request.first_name,
                last_name=user_request.last_name,
                profile_picture_url=user_request.profile_picture_url,
                last_login=user_request.last_login,
                is_active=user_request.is_active
            )
            session.add(new_user)
            session.commit()
            session.refresh(new_user)
            logger.info(f"User created: {new_user}")
            session.expunge(new_user)
            return new_user
    except Exception as e:
        logger.error(f"Error creating user: {e}")
        raise e

@with_db_retry(max_retries=3, retry_delay=1.0)
def get_user_id_by_auth0_sub(auth0_sub: str) -> UUID:
    """Get a user by auth0_sub"""
    try:
        logger.info(f"Getting user by auth0_sub: {auth0_sub}")
        with Session() as session:
            user_id = session.query(UsersORM.id).filter(
                UsersORM.auth0_sub == auth0_sub
            ).scalar()

            logger.info(f"User ID found: {user_id}")
            return user_id
    except Exception as e:
        logger.error(f"Error getting user by auth0_sub: {e}")
        raise e

@with_db_retry(max_retries=3, retry_delay=1.0)
def get_user_by_auth0_sub(auth0_sub: str) -> UsersORM:
    """Get full user data by auth0_sub"""
    try:
        logger.info(f"Getting full user data by auth0_sub: {auth0_sub}")
        with Session() as session:
            user = session.query(UsersORM).filter(
                UsersORM.auth0_sub == auth0_sub
            ).first()
            
            logger.info(f"User found: {user}")
            if user:
                session.expunge(user)
            return user
    except Exception as e:
        logger.error(f"Error getting user by auth0_sub: {e}")
        raise e
    
def get_user_settings_by_user_id(user_id: UUID) -> UserSettingsORM:
    """Get user settings by user_id"""
    try:
        logger.info(f"Getting user settings by user_id: {user_id}")
        with Session() as session:
            user_settings = session.query(UserSettingsORM).filter(
                UserSettingsORM.user_id == user_id
            ).first()
            if user_settings:
                session.expunge(user_settings)
            return user_settings
    except Exception as e:
        logger.error(f"Error getting user settings by user_id: {e}")
        raise e


def log_agent_mode_opt_in_change(user_id: UUID, opt_in_status: bool) -> AgentModeOptInHistoryORM:
    """Log a change to the user's agent mode opt-in status for compliance tracking"""
    try:
        logger.info(f"Logging agent mode opt-in change for user {user_id}: {opt_in_status}")
        with Session() as session:
            history_entry = AgentModeOptInHistoryORM(
                user_id=user_id,
                opt_in_status=opt_in_status,
                changed_at=datetime.now(timezone.utc)
            )
            session.add(history_entry)
            session.commit()
            session.refresh(history_entry)
            logger.info(f"Agent mode opt-in history logged: {history_entry}")
            session.expunge(history_entry)
            return history_entry
    except Exception as e:
        logger.error(f"Error logging agent mode opt-in change: {e}")
        raise e

    
def create_user_settings(user_id: UUID, user_settings: UserSettingsRequest) -> UserSettingsORM:
    """Create a new user settings"""
    try:
        logger.info(f"Creating user settings: {user_settings}")
        with Session() as session:
            new_user_settings = UserSettingsORM(
                user_id=user_id,
                preferred_sources=user_settings.preferred_sources,
                theme=user_settings.theme,
                language=user_settings.language,
                timezone=user_settings.timezone,
                agent_mode_opt_in=user_settings.agent_mode_opt_in
            )
            session.add(new_user_settings)
            session.commit()
            session.refresh(new_user_settings)
            logger.info(f"User settings created: {new_user_settings}")
            session.expunge(new_user_settings)
            
            # Log the initial opt-in status if user opted in
            if user_settings.agent_mode_opt_in:
                log_agent_mode_opt_in_change(user_id, user_settings.agent_mode_opt_in)
            
            return new_user_settings
    except Exception as e:
        logger.error(f"Error creating user settings: {e}")
        raise e
    
def update_user_settings(user_id: UUID, user_settings: UserSettingsRequest) -> UserSettingsORM:
    """Update user settings"""
    try:
        logger.info(f"Updating user settings: {user_settings}")
        with Session() as session:
            user_settings_obj = session.query(UserSettingsORM).filter(
                UserSettingsORM.user_id == user_id
            ).first()
            
            # Check if agent_mode_opt_in is changing and log history
            if user_settings_obj.agent_mode_opt_in != user_settings.agent_mode_opt_in:
                log_agent_mode_opt_in_change(user_id, user_settings.agent_mode_opt_in)
            
            user_settings_obj.preferred_sources = user_settings.preferred_sources
            user_settings_obj.theme = user_settings.theme
            user_settings_obj.language = user_settings.language
            user_settings_obj.timezone = user_settings.timezone
            user_settings_obj.agent_mode_opt_in = user_settings.agent_mode_opt_in
            session.commit()
            session.refresh(user_settings_obj)
            logger.info(f"User settings updated: {user_settings_obj}")
            session.expunge(user_settings_obj)
            return user_settings_obj
    except Exception as e:
        logger.error(f"Error updating user settings: {e}")
        raise e


@with_db_retry(max_retries=3, retry_delay=1.0)
def get_user_by_id(user_id: UUID) -> UsersORM:
    """Get user by user_id"""
    try:
        logger.info(f"Getting user by user_id: {user_id}")
        with Session() as session:
            user = session.query(UsersORM).filter(
                UsersORM.id == user_id
            ).first()
            
            if user:
                session.expunge(user)
            return user
    except Exception as e:
        logger.error(f"Error getting user by user_id: {e}")
        raise e


def increment_user_agent_quota_used(user_id: UUID, amount: int = 1) -> UsersORM:
    """Increment a user's agent quota used count"""
    try:
        logger.info(f"Incrementing agent quota used for user_id: {user_id}")
        with Session() as session:
            user = session.query(UsersORM).filter(
                UsersORM.id == user_id
            ).first()
            if user:
                user.agent_quota_used += amount
                session.commit()
                session.refresh(user)
                logger.info(f"Agent quota used incremented for user {user_id}: {user.agent_quota_used}")
                session.expunge(user)
            return user
    except Exception as e:
        logger.error(f"Error incrementing agent quota used: {e}")
        raise e


def reset_user_agent_quota(user_id: UUID) -> UsersORM:
    """Reset a user's agent quota used count to 0 and set quota to 10"""
    try:
        logger.info(f"Resetting agent quota for user_id: {user_id}")
        with Session() as session:
            user = session.query(UsersORM).filter(
                UsersORM.id == user_id
            ).first()
            if user:
                user.agent_quota = DEFAULT_AGENT_QUOTA
                user.agent_quota_used = 0
                session.commit()
                session.refresh(user)
                logger.info(f"Agent quota reset for user {user_id}")
                session.expunge(user)
            return user
    except Exception as e:
        logger.error(f"Error resetting agent quota: {e}")
        raise e


def get_all_users_for_agent_quota_reset() -> list[UsersORM]:
    """Get all active users who have used agent quota (agent_quota_used > 0)"""
    try:
        logger.info("Getting all users for agent quota reset")
        with Session() as session:
            users = session.query(UsersORM).filter(
                UsersORM.is_active == True,
                UsersORM.agent_quota_used > 0
            ).all()
            for user in users:
                session.expunge(user)
            logger.info(f"Found {len(users)} users for agent quota reset")
            return users
    except Exception as e:
        logger.error(f"Error getting users for agent quota reset: {e}")
        raise e


def reset_all_users_agent_quota() -> int:
    """Reset agent quota for all users (bulk update). Returns count of updated users."""
    try:
        logger.info("Resetting agent quota for all users")
        with Session() as session:
            result = session.query(UsersORM).filter(
                UsersORM.is_active == True,
                UsersORM.agent_quota_used > 0
            ).update({
                UsersORM.agent_quota: DEFAULT_AGENT_QUOTA,
                UsersORM.agent_quota_used: 0
            })
            session.commit()
            logger.info(f"Reset agent quota for {result} users")
            return result
    except Exception as e:
        logger.error(f"Error resetting all users agent quota: {e}")
        raise e
