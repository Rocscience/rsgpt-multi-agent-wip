from fastapi import APIRouter, Depends, HTTPException, Request
import logging
from typing import Dict, Any, Optional
from uuid import UUID

from app.models.devices import (
    RegisterDeviceRequest, 
    RegisterDeviceResponse,
    UpdateDeviceRequest,
    UpdateDeviceResponse,
    DeviceResponse,
    DeviceListResponse
)
from app.db_interface.devices import (
    get_device_by_token,
    get_device_by_id,
    get_user_devices,
    create_device,
    update_device,
    update_device_by_token,
    deactivate_device
)
from app.dependencies import get_current_user
from app.services.ai_core_client import ai_core_client

logger = logging.getLogger(__name__)

device_router = APIRouter()


@device_router.post("/register", response_model=RegisterDeviceResponse)
async def register_device(
    device_data: RegisterDeviceRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Register a new device or update existing device on handshake.
    Called when desktop app starts up or reconnects.
    
    - If device_token exists: updates metadata and reactivates
    - If device_token is new: creates new device entry
    
    Returns device_id and registration status
    """
    user_id = current_user["user_id"]
    
    try:
        # Check if device already exists
        existing_device = get_device_by_token(device_data.device_token)
        
        if existing_device:
            # Check if device is being transferred to a different user
            if existing_device.user_id != user_id:
                logger.info(
                    f"Device ownership transfer: device_token={device_data.device_token}, "
                    f"from_user={existing_device.user_id}, to_user={user_id}"
                )
            
            # Update existing device
            updated_device = update_device_by_token(
                device_data.device_token,
                user_id,
                device_data
            )
            
            return RegisterDeviceResponse(
                device_id=updated_device.id,
                status="updated",
                message="Device reconnected and updated successfully",
                is_new_device=False
            )
        else:
            # Create new device
            new_device = create_device(user_id, device_data)
            
            return RegisterDeviceResponse(
                device_id=new_device.id,
                status="registered",
                message="Device registered successfully",
                is_new_device=True
            )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error registering device for user {user_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to register device"
        )


@device_router.put("/{device_id}/status", response_model=UpdateDeviceResponse)
async def update_device_status(
    device_id: UUID,
    device_update: UpdateDeviceRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Update device status, MCP servers, or other metadata.
    Called periodically by desktop app or when MCP servers change.
    
    Verifies device belongs to authenticated user.
    """
    user_id = current_user["user_id"]
    
    try:
        # Get device and verify ownership
        device = get_device_by_id(device_id)
        
        if not device:
            raise HTTPException(
                status_code=404,
                detail="Device not found"
            )
        
        if device.user_id != user_id:
            raise HTTPException(
                status_code=403,
                detail="Device belongs to another user"
            )
        
        # Update device
        updated_device = update_device(device_id, device_update)
        
        return UpdateDeviceResponse(
            device_id=updated_device.id,
            last_active=updated_device.last_active,
            message="Device updated successfully"
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating device {device_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to update device"
        )


@device_router.get("/", response_model=DeviceListResponse)
async def list_user_devices(
    current_user: Dict[str, Any] = Depends(get_current_user),
    include_inactive: bool = False
):
    """
    List all devices for the authenticated user.
    Useful for a "My Devices" settings page in the app.
    
    Query params:
    - include_inactive: If true, includes deactivated devices
    """
    user_id = current_user["user_id"]
    
    try:
        devices = get_user_devices(user_id, include_inactive)
        
        device_responses = [
            DeviceResponse(
                device_id=d.id,
                device_token=d.device_token,
                device_name=d.device_name,
                device_type=d.device_type.value,
                os_name=d.os_name,
                os_version=d.os_version,
                app_version=d.app_version,
                mcp_servers=d.mcp_servers,
                last_active=d.last_active,
                is_active=d.is_active,
                created_at=d.created_at.isoformat()
            )
            for d in devices
        ]
        
        return DeviceListResponse(
            devices=device_responses,
            total_count=len(device_responses)
        )
    except Exception as e:
        logger.error(f"Error listing devices for user {user_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to list devices"
        )


@device_router.get("/{device_id}", response_model=DeviceResponse)
async def get_device_details(
    device_id: UUID,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Get details of a specific device.
    Desktop app can use this to verify its own registration status.
    """
    user_id = current_user["user_id"]
    
    try:
        # Get device and verify ownership
        device = get_device_by_id(device_id)
        
        if not device:
            raise HTTPException(
                status_code=404,
                detail="Device not found"
            )
        
        if device.user_id != user_id:
            raise HTTPException(
                status_code=403,
                detail="Device belongs to another user"
            )
        
        return DeviceResponse(
            device_id=device.id,
            device_token=device.device_token,
            device_name=device.device_name,
            device_type=device.device_type.value,
            os_name=device.os_name,
            os_version=device.os_version,
            app_version=device.app_version,
            mcp_servers=device.mcp_servers,
            last_active=device.last_active,
            is_active=device.is_active,
            created_at=device.created_at.isoformat()
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting device {device_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to get device"
        )


@device_router.delete("/{device_id}")
async def deactivate_device_endpoint(
    device_id: UUID,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Deactivate (soft delete) a device.
    Called when user logs out or uninstalls app.
    Sets is_active=False and deleted_at timestamp.
    """
    user_id = current_user["user_id"]
    
    try:
        # Get device and verify ownership
        device = get_device_by_id(device_id)
        
        if not device:
            raise HTTPException(
                status_code=404,
                detail="Device not found"
            )
        
        if device.user_id != user_id:
            raise HTTPException(
                status_code=403,
                detail="Device belongs to another user"
            )
        
        # Deactivate device
        deactivate_device(device_id)
        
        return {
            "message": "Device deactivated successfully",
            "device_id": str(device_id)
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deactivating device {device_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to deactivate device"
        )


@device_router.post("/{device_id}/file-path")
async def request_device_file_path(
    device_id: UUID,
    request: Request,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Request file path selection from a device via ai-core.
    Opens native file dialog on the device and returns selected file path.
    
    Verifies device belongs to authenticated user before making request.
    """
    user_id = current_user["user_id"]
    
    try:
        # Get device and verify ownership
        device = get_device_by_id(device_id)
        
        if not device:
            raise HTTPException(
                status_code=404,
                detail="Device not found"
            )
        
        if device.user_id != user_id:
            raise HTTPException(
                status_code=403,
                detail="Device belongs to another user"
            )
        
        # Extract screenInfo from request body (optional)
        screen_info: Optional[dict] = None
        try:
            body = await request.json()
            screen_info = body.get("screenInfo")
        except Exception:
            # No body or invalid JSON - that's okay, screenInfo is optional
            pass
        
        # Call ai-core to request file path from device
        try:
            response = await ai_core_client.request_file_path(
                device_id=str(device_id),
                screen_info=screen_info,
                timeout=90.0
            )
            
            return {
                "file_path": response.get("file_path"),
                "canceled": response.get("canceled", False),
                "error": response.get("error")
            }
            
        except ConnectionError as e:
            error_msg = str(e)
            logger.error(f"Error requesting file path from device {device_id}: {error_msg}")
            
            # Check for specific error messages to return appropriate status codes
            if "not connected" in error_msg.lower():
                raise HTTPException(
                    status_code=404,
                    detail="Device is not connected"
                )
            elif "did not respond" in error_msg.lower():
                raise HTTPException(
                    status_code=504,
                    detail="Device did not respond in time"
                )
            else:
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to request file path: {error_msg}"
                )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error requesting file path from device {device_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to request file path"
        )

