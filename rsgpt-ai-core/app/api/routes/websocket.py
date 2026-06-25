"""WebSocket routes for device connections"""

import json
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from app.dependencies import verify_be_auth
from app.models.consts import CLIENT_TYPE_DESKTOP
from app.services.auth import auth_service
from app.services.streaming import connection_manager
from app.models.file_path import FilePathRequest
from app.config import settings

logger = logging.getLogger(__name__)

websocket_router = APIRouter()


class WebSocketMessage(BaseModel):
    """WebSocket message model"""

    type: str
    data: Optional[dict] = None
    timestamp: Optional[str] = None


async def verify_websocket_token(token: str) -> dict:
    """Verify JWT token for WebSocket authentication"""
    return await auth_service.verify_token(token)


@websocket_router.websocket("/device/{device_id}")
async def websocket_endpoint(websocket: WebSocket, device_id: str):
    """
    WebSocket endpoint for device connections (Desktop only)

    Each device connects with:
    - device_id: Unique device identifier
    - Authorization header: Bearer token for authentication
    - X-Client-Type header: Must be "desktop" (production only)
    """
    try:
        # RSI-140: Log incoming WebSocket connection attempt
        logger.info(f"[RSI-140] WebSocket connection attempt for device {device_id}")
        logger.info(
            f"[RSI-140] Environment: is_development={settings.is_development}, "
            f"is_testing={settings.is_testing}, env={settings.environment}"
        )

        # Log all headers for debugging (excluding sensitive Authorization value)
        header_names = list(websocket.headers.keys())
        logger.info(f"[RSI-140] Received headers: {header_names}")

        # Extract and validate X-Client-Type header (production only)
        if not settings.is_development and not settings.is_testing:
            client_type = websocket.headers.get("x-client-type") or websocket.headers.get("X-Client-Type")
            logger.info(
                f"[RSI-140] X-Client-Type check: received='{client_type}', expected='{CLIENT_TYPE_DESKTOP}'"
            )
            if client_type != CLIENT_TYPE_DESKTOP:
                logger.warning(
                    f"[RSI-140] X-Client-Type FAILED for device {device_id}: "
                    f"expected '{CLIENT_TYPE_DESKTOP}', got '{client_type}'"
                )
                await websocket.close(code=4003, reason=f"This endpoint requires X-Client-Type: {CLIENT_TYPE_DESKTOP}")
                return
            logger.info(f"[RSI-140] X-Client-Type PASSED")
        else:
            logger.info(f"[RSI-140] Skipping X-Client-Type check (dev/test mode)")

        # Extract token from Authorization header
        auth_header = websocket.headers.get("authorization") or websocket.headers.get(
            "Authorization"
        )
        if not auth_header:
            logger.error(f"[RSI-140] Missing authorization header for device {device_id}")
            raise HTTPException(status_code=401, detail="Missing authorization header")

        if not auth_header.startswith("Bearer "):
            logger.error(f"[RSI-140] Invalid auth header format for device {device_id}")
            raise HTTPException(
                status_code=401,
                detail="Invalid authorization header format. Expected 'Bearer <token>'",
            )

        token = auth_header[7:]  # Remove "Bearer " prefix
        logger.info(f"[RSI-140] Verifying Bearer token...")

        # Verify authentication
        user_info = await verify_websocket_token(token)
        user_id = user_info["user_id"]
        logger.info(f"[RSI-140] Token verified for user {user_id}")

        # Connect the device
        await connection_manager.connect(websocket, device_id, user_id)

        logger.info(
            f"WebSocket connection established for device {device_id}, user {user_id}"
        )

        try:
            while True:
                # Receive messages from the client
                data = await websocket.receive_text()

                try:
                    message = json.loads(data)
                    message_type = message.get("type")

                    if message_type == "heartbeat":
                        # Handle heartbeat
                        await connection_manager.handle_heartbeat(device_id)
                        await websocket.send_text(
                            json.dumps(
                                {
                                    "type": "heartbeat_ack",
                                    "timestamp": datetime.utcnow().isoformat(),
                                }
                            )
                        )

                    elif message_type == "ping":
                        # Handle ping/pong
                        await websocket.send_text(
                            json.dumps(
                                {
                                    "type": "pong",
                                    "timestamp": datetime.utcnow().isoformat(),
                                }
                            )
                        )

                    elif message_type == "status_update":
                        # Handle device status updates
                        logger.info(
                            f"Status update from device {device_id}: {message.get('data', {})}"
                        )
                        # You can add custom logic here to handle status updates

                    elif message_type == "list_tools_response":
                        # Handle list_tools response
                        message_id = message.get("id")
                        if message_id:
                            connection_manager.handle_response(
                                message_id, message.get("data", {})
                            )
                        else:
                            logger.warning(
                                f"list_tools_response missing message id from device {device_id}"
                            )

                    elif message_type == "invoke_tool_response":
                        # Handle invoke_tool response
                        message_id = message.get("id")
                        if message_id:
                            connection_manager.handle_response(
                                message_id, message.get("data", {})
                            )
                        else:
                            logger.warning(
                                f"invoke_tool_response missing message id from device {device_id}"
                            )

                    elif message_type == "file_path_response":
                        # Handle file_path_response
                        message_id = message.get("id")
                        if message_id:
                            connection_manager.handle_response(
                                message_id, message.get("data", {})
                            )
                        else:
                            logger.warning(
                                f"file_path_response missing message id from device {device_id}"
                            )

                    else:
                        logger.warning(
                            f"Unknown message type from device {device_id}: {message_type}"
                        )

                except json.JSONDecodeError:
                    logger.error(f"Invalid JSON from device {device_id}: {data}")
                    await websocket.send_text(
                        json.dumps(
                            {
                                "type": "error",
                                "message": "Invalid JSON format",
                                "timestamp": datetime.utcnow().isoformat(),
                            }
                        )
                    )

        except WebSocketDisconnect:
            logger.info(f"Device {device_id} disconnected normally")

        except Exception as e:
            logger.error(f"Error in WebSocket connection for device {device_id}: {e}")
            await websocket.send_text(
                json.dumps(
                    {
                        "type": "error",
                        "message": "Internal server error",
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                )
            )

    except HTTPException as e:
        logger.error(f"Authentication failed for device {device_id}: {e.detail}")
        await websocket.close(code=1008, reason=e.detail)  # Policy violation

    except Exception as e:
        logger.error(f"Unexpected error for device {device_id}: {e}")
        await websocket.close(code=1011, reason="Internal server error")

    finally:
        # Clean up connection
        if connection_manager.is_device_connected(device_id):
            await connection_manager.disconnect_device(device_id, "Connection closed")


@websocket_router.get("/devices")
async def get_connected_devices():
    """Get information about all connected devices (for debugging/monitoring)"""
    return {
        "connected_devices": connection_manager.get_connected_devices(),
        "total_connections": len(connection_manager.connected_devices),
    }


@websocket_router.post("/send/{device_id}")
async def send_to_device(device_id: str, message: WebSocketMessage):
    """
    Send a message to a specific device (for backend events)
    This endpoint allows backend services to send messages to connected devices
    """
    message_dict = {
        "type": message.type,
        "data": message.data,
        "timestamp": message.timestamp or datetime.utcnow().isoformat(),
    }

    success = await connection_manager.send_to_device(device_id, message_dict)

    if not success:
        raise HTTPException(status_code=404, detail=f"Device {device_id} not connected")

    return {"message": "Message sent successfully", "device_id": device_id}


@websocket_router.post("/send/user/{user_id}")
async def send_to_user(user_id: str, message: WebSocketMessage):
    """
    Send a message to all devices for a specific user
    """
    message_dict = {
        "type": message.type,
        "data": message.data,
        "timestamp": message.timestamp or datetime.utcnow().isoformat(),
    }

    sent_count = await connection_manager.send_to_user(user_id, message_dict)

    return {
        "message": "Message sent to user devices",
        "user_id": user_id,
        "devices_reached": sent_count,
    }


@websocket_router.post("/broadcast")
async def broadcast_message(message: WebSocketMessage):
    """
    Broadcast a message to all connected devices
    """
    message_dict = {
        "type": message.type,
        "data": message.data,
        "timestamp": message.timestamp or datetime.utcnow().isoformat(),
    }

    sent_count = await connection_manager.broadcast(message_dict)

    return {"message": "Message broadcasted", "devices_reached": sent_count}


@websocket_router.post("/list_tools/{device_id}")
async def list_tools(device_id: str, timeout: float = 30.0):
    """
    Request list of available tools from a device
    """
    try:
        response = await connection_manager.request_list_tools(device_id, timeout)
        return {
            "message": "Tools list retrieved",
            "device_id": device_id,
            "tools": response.get("tools", []),
            "error": response.get("error"),
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except TimeoutError as e:
        raise HTTPException(status_code=504, detail=str(e))
    except Exception as e:
        logger.error(f"Error requesting tools list from device {device_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


class InvokeToolRequest(BaseModel):
    """Request model for tool invocation"""

    tool_name: str
    tool_args: Optional[dict] = None
    timeout: float = 60.0


@websocket_router.post("/invoke_tool/{device_id}")
async def invoke_tool(device_id: str, request: InvokeToolRequest):
    """
    Invoke a tool on a device
    """
    try:
        response = await connection_manager.request_invoke_tool(
            device_id, request.tool_name, request.tool_args, request.timeout
        )
        return {
            "message": "Tool invoked",
            "device_id": device_id,
            "tool_name": request.tool_name,
            "result": response.get("result"),
            "error": response.get("error"),
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except TimeoutError as e:
        raise HTTPException(status_code=504, detail=str(e))
    except Exception as e:
        logger.error(
            f"Error invoking tool {request.tool_name} on device {device_id}: {e}"
        )
        raise HTTPException(status_code=500, detail="Internal server error")


class AgentResponseMessage(BaseModel):
    """Agent response message model"""

    response_data: dict


@websocket_router.post("/agent_response/{device_id}")
async def send_agent_response_to_device(device_id: str, message: AgentResponseMessage):
    """
    Send an agent response to a specific device
    """
    success = await connection_manager.send_agent_response(
        device_id, message.response_data
    )

    if not success:
        raise HTTPException(status_code=404, detail=f"Device {device_id} not connected")

    return {
        "message": "Agent response sent successfully",
        "device_id": device_id,
    }



@websocket_router.post("/request_file_path/{device_id}")
async def request_file_path(
    device_id: str,
    file_path_request: Optional[FilePathRequest] = None,
    auth_info: dict = Depends(verify_be_auth)
):
    """
    Request file path selection from a device
    Opens native file dialog on the device and returns selected file path
    
    Requires BE service token authentication (X-Service-Token header).
    """
    try:
        timeout = file_path_request.timeout if file_path_request else 90.0
        screen_info = file_path_request.screenInfo if file_path_request else None

        service_name = auth_info.get("service", "unknown")
        logger.debug(f"Service {service_name} requesting file path from device {device_id}")
        
        response = await connection_manager.request_file_path(
            device_id, timeout, screen_info
        )
        
        return {
            "message": "File path request completed",
            "device_id": device_id,
            "file_path": response.get("filePath"),
            "canceled": response.get("canceled", False),
            "error": response.get("error"),
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except TimeoutError as e:
        raise HTTPException(status_code=504, detail=str(e))
    except Exception as e:
        logger.error(f"Error requesting file path from device {device_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
