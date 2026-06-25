import logging
from datetime import datetime
from uuid import UUID
from typing import Optional, List

from app.db_models.devices import DevicesORM, DeviceType
from app.models.devices import RegisterDeviceRequest, UpdateDeviceRequest
from app.db_models.connection import Session, with_db_retry

logger = logging.getLogger(__name__)


@with_db_retry(max_retries=3, retry_delay=1.0)
def get_device_by_token(device_token: str) -> Optional[DevicesORM]:
    """Get device by device_token"""
    try:
        logger.info(f"Getting device by token: {device_token}")
        with Session() as session:
            device = session.query(DevicesORM).filter(
                DevicesORM.device_token == device_token
            ).first()
            if device:
                session.expunge(device)
            return device
    except Exception as e:
        logger.error(f"Error getting device by token: {e}")
        raise e


@with_db_retry(max_retries=3, retry_delay=1.0)
def get_device_by_id(device_id: UUID) -> Optional[DevicesORM]:
    """Get device by ID"""
    try:
        logger.info(f"Getting device by ID: {device_id}")
        with Session() as session:
            device = session.query(DevicesORM).filter(
                DevicesORM.id == device_id
            ).first()
            if device:
                session.expunge(device)
            return device
    except Exception as e:
        logger.error(f"Error getting device by ID: {e}")
        raise e


@with_db_retry(max_retries=3, retry_delay=1.0)
def get_user_devices(user_id: UUID, include_inactive: bool = False) -> List[DevicesORM]:
    """Get all devices for a user"""
    try:
        logger.info(f"Getting devices for user: {user_id}")
        with Session() as session:
            query = session.query(DevicesORM).filter(
                DevicesORM.user_id == user_id
            )
            if not include_inactive:
                query = query.filter(DevicesORM.is_active == True)
            
            devices = query.order_by(DevicesORM.last_active.desc()).all()
            for device in devices:
                session.expunge(device)
            return devices
    except Exception as e:
        logger.error(f"Error getting user devices: {e}")
        raise e


def create_device(user_id: UUID, device_request: RegisterDeviceRequest) -> DevicesORM:
    """Create a new device"""
    try:
        logger.info(f"Creating device for user {user_id}: {device_request.device_name}")
        with Session() as session:
            new_device = DevicesORM(
                user_id=user_id,
                device_token=device_request.device_token,
                device_name=device_request.device_name,
                device_type=DeviceType(device_request.device_type),
                os_name=device_request.os_name,
                os_version=device_request.os_version,
                app_version=device_request.app_version,
                mcp_servers=device_request.mcp_servers or [],
                last_active=datetime.utcnow().isoformat(),
                is_active=True
            )
            session.add(new_device)
            session.commit()
            session.refresh(new_device)
            logger.info(f"Device created: {new_device.id}")
            session.expunge(new_device)
            return new_device
    except Exception as e:
        logger.error(f"Error creating device: {e}")
        raise e


def update_device(device_id: UUID, device_update: UpdateDeviceRequest) -> DevicesORM:
    """Update an existing device"""
    try:
        logger.info(f"Updating device: {device_id}")
        with Session() as session:
            device = session.query(DevicesORM).filter(
                DevicesORM.id == device_id
            ).first()
            
            if not device:
                raise ValueError(f"Device {device_id} not found")
            
            # Update fields if provided
            if device_update.mcp_servers is not None:
                device.mcp_servers = device_update.mcp_servers
            if device_update.app_version is not None:
                device.app_version = device_update.app_version
            if device_update.os_version is not None:
                device.os_version = device_update.os_version
            
            device.last_active = datetime.utcnow().isoformat()
            
            session.commit()
            session.refresh(device)
            logger.info(f"Device updated: {device_id}")
            session.expunge(device)
            return device
    except Exception as e:
        logger.error(f"Error updating device: {e}")
        raise e


def update_device_by_token(device_token: str, user_id: UUID, device_request: RegisterDeviceRequest) -> DevicesORM:
    """Update device by token (for register endpoint)"""
    try:
        logger.info(f"Updating device by token: {device_token}")
        with Session() as session:
            device = session.query(DevicesORM).filter(
                DevicesORM.device_token == device_token
            ).first()
            
            if not device:
                raise ValueError(f"Device with token {device_token} not found")
            
            # Update all fields (including user_id for ownership transfer)
            device.user_id = user_id
            device.device_name = device_request.device_name
            device.device_type = DeviceType(device_request.device_type)
            device.os_name = device_request.os_name
            device.os_version = device_request.os_version
            device.app_version = device_request.app_version
            device.mcp_servers = device_request.mcp_servers or []
            device.last_active = datetime.utcnow().isoformat()
            device.is_active = True  # Reactivate if was inactive
            device.deleted_at = None  # Clear soft delete timestamp
            
            session.commit()
            session.refresh(device)
            logger.info(f"Device updated by token: {device_token}")
            session.expunge(device)
            return device
    except Exception as e:
        logger.error(f"Error updating device by token: {e}")
        raise e


def deactivate_device(device_id: UUID) -> DevicesORM:
    """Deactivate a device (soft delete)"""
    try:
        logger.info(f"Deactivating device: {device_id}")
        with Session() as session:
            device = session.query(DevicesORM).filter(
                DevicesORM.id == device_id
            ).first()
            
            if not device:
                raise ValueError(f"Device {device_id} not found")
            
            device.is_active = False
            device.deleted_at = datetime.utcnow()
            
            session.commit()
            session.refresh(device)
            logger.info(f"Device deactivated: {device_id}")
            session.expunge(device)
            return device
    except Exception as e:
        logger.error(f"Error deactivating device: {e}")
        raise e

