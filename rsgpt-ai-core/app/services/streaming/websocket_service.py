"""WebSocket connection manager service"""

import asyncio
import json
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, Optional, Set

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections for devices"""

    def __init__(self):
        # Maps device_id to WebSocket connection
        self.connected_devices: Dict[str, WebSocket] = {}
        # Maps user_id to set of device_ids
        self.user_devices: Dict[str, Set[str]] = {}
        # Maps device_id to user_id for reverse lookup
        self.device_users: Dict[str, str] = {}
        # Connection metadata
        self.connection_metadata: Dict[str, dict] = {}
        # Pending requests: message_id -> asyncio.Future
        self.pending_requests: Dict[str, asyncio.Future] = {}

    async def connect(self, websocket: WebSocket, device_id: str, user_id: str) -> None:
        """Accept a new WebSocket connection and register the device"""
        await websocket.accept()

        # If device already connected, disconnect the old connection
        if device_id in self.connected_devices:
            await self.disconnect_device(
                device_id, reason="New connection from same device"
            )

        # Store the connection
        self.connected_devices[device_id] = websocket
        self.device_users[device_id] = user_id

        # Track user devices
        if user_id not in self.user_devices:
            self.user_devices[user_id] = set()
        self.user_devices[user_id].add(device_id)

        # Store connection metadata
        self.connection_metadata[device_id] = {
            "connected_at": datetime.utcnow().isoformat(),
            "user_id": user_id,
            "last_heartbeat": datetime.utcnow().isoformat(),
        }

        logger.info(f"Device {device_id} connected for user {user_id}")

        # Send connection confirmation
        await self.send_to_device(
            device_id,
            {
                "type": "connection_established",
                "device_id": device_id,
                "timestamp": datetime.utcnow().isoformat(),
            },
        )

    async def disconnect_device(
        self, device_id: str, reason: str = "Normal disconnection"
    ) -> None:
        """Disconnect a specific device"""
        if device_id in self.connected_devices:
            websocket = self.connected_devices[device_id]
            user_id = self.device_users.get(device_id)

            try:
                # Send disconnect message before closing
                await websocket.send_text(
                    json.dumps(
                        {
                            "type": "disconnect",
                            "reason": reason,
                            "timestamp": datetime.utcnow().isoformat(),
                        }
                    )
                )
                await websocket.close()
            except Exception as e:
                logger.warning(f"Error sending disconnect message to {device_id}: {e}")

            # Clean up mappings
            del self.connected_devices[device_id]
            del self.device_users[device_id]
            del self.connection_metadata[device_id]

            if user_id and user_id in self.user_devices:
                self.user_devices[user_id].discard(device_id)
                if not self.user_devices[user_id]:
                    del self.user_devices[user_id]

            logger.info(f"Device {device_id} disconnected: {reason}")

    async def disconnect_user_devices(
        self, user_id: str, reason: str = "User logout"
    ) -> None:
        """Disconnect all devices for a specific user"""
        if user_id in self.user_devices:
            device_ids = self.user_devices[user_id].copy()
            for device_id in device_ids:
                await self.disconnect_device(device_id, reason)

    async def send_to_device(self, device_id: str, message: dict) -> bool:
        """Send a message to a specific device"""
        if device_id not in self.connected_devices:
            logger.warning(f"Device {device_id} not connected")
            return False

        websocket = self.connected_devices[device_id]
        try:
            await websocket.send_text(json.dumps(message))
            return True
        except WebSocketDisconnect:
            logger.info(f"Device {device_id} disconnected while sending message")
            await self.disconnect_device(device_id, "Connection lost")
            return False
        except Exception as e:
            logger.error(f"Error sending message to device {device_id}: {e}")
            await self.disconnect_device(device_id, f"Send error: {str(e)}")
            return False

    async def send_to_user(self, user_id: str, message: dict) -> int:
        """Send a message to all devices for a specific user"""
        sent_count = 0
        if user_id in self.user_devices:
            device_ids = self.user_devices[user_id].copy()
            for device_id in device_ids:
                if await self.send_to_device(device_id, message):
                    sent_count += 1
        return sent_count

    async def broadcast(
        self, message: dict, exclude_devices: Optional[Set[str]] = None
    ) -> int:
        """Broadcast a message to all connected devices"""
        sent_count = 0
        exclude_devices = exclude_devices or set()

        device_ids = list(self.connected_devices.keys())
        for device_id in device_ids:
            if device_id not in exclude_devices:
                if await self.send_to_device(device_id, message):
                    sent_count += 1
        return sent_count

    async def handle_heartbeat(self, device_id: str) -> None:
        """Update heartbeat timestamp for a device"""
        if device_id in self.connection_metadata:
            self.connection_metadata[device_id][
                "last_heartbeat"
            ] = datetime.utcnow().isoformat()

    def get_connected_devices(self) -> Dict[str, dict]:
        """Get information about all connected devices"""
        return {
            device_id: {**metadata, "is_connected": True}
            for device_id, metadata in self.connection_metadata.items()
        }

    def get_user_devices(self, user_id: str) -> Set[str]:
        """Get all connected devices for a user"""
        return self.user_devices.get(user_id, set())

    def is_device_connected(self, device_id: str) -> bool:
        """Check if a device is currently connected"""
        return device_id in self.connected_devices

    def get_device_user(self, device_id: str) -> Optional[str]:
        """Get the user_id for a connected device"""
        return self.device_users.get(device_id)

    async def request_list_tools(
        self, device_id: str, timeout: float = 30.0
    ) -> Dict[str, Any]:
        """Request list of tools from a device"""
        if not self.is_device_connected(device_id):
            raise ValueError(f"Device {device_id} not connected")

        message_id = str(uuid.uuid4())
        future = asyncio.get_event_loop().create_future()
        self.pending_requests[message_id] = future

        try:
            # Send request
            success = await self.send_to_device(
                device_id,
                {
                    "type": "list_tools",
                    "id": message_id,
                    "timestamp": datetime.utcnow().isoformat(),
                },
            )

            if not success:
                raise RuntimeError(f"Failed to send message to device {device_id}")

            # Wait for response with timeout
            response = await asyncio.wait_for(future, timeout=timeout)
            return response

        except asyncio.TimeoutError:
            logger.error(
                f"Timeout waiting for list_tools response from device {device_id}"
            )
            raise TimeoutError(
                f"Device {device_id} did not respond within {timeout} seconds"
            )
        finally:
            # Clean up pending request
            self.pending_requests.pop(message_id, None)

    async def request_invoke_tool(
        self,
        device_id: str,
        tool_name: str,
        tool_args: Optional[Dict[str, Any]] = None,
        timeout: float = 60.0,
    ) -> Dict[str, Any]:
        """Request tool invocation on a device"""
        if not self.is_device_connected(device_id):
            raise ValueError(f"Device {device_id} not connected")

        message_id = str(uuid.uuid4())
        future = asyncio.get_event_loop().create_future()
        self.pending_requests[message_id] = future

        try:
            # Send request
            success = await self.send_to_device(
                device_id,
                {
                    "type": "invoke_tool",
                    "id": message_id,
                    "tool_name": tool_name,
                    "tool_args": tool_args or {},
                    "timestamp": datetime.utcnow().isoformat(),
                },
            )

            if not success:
                raise RuntimeError(f"Failed to send message to device {device_id}")

            # Wait for response with timeout
            response = await asyncio.wait_for(future, timeout=timeout)
            return response

        except asyncio.TimeoutError:
            logger.error(
                f"Timeout waiting for invoke_tool response from device {device_id}"
            )
            raise TimeoutError(
                f"Device {device_id} did not respond within {timeout} seconds"
            )
        finally:
            # Clean up pending request
            self.pending_requests.pop(message_id, None)

    def handle_response(self, message_id: str, response_data: Dict[str, Any]) -> None:
        """Handle a response from a device"""
        future = self.pending_requests.get(message_id)
        if future and not future.done():
            future.set_result(response_data)
        else:
            logger.warning(
                f"Received response for unknown or expired request: {message_id}"
            )

    async def request_file_path(
        self, device_id: str, timeout: float = 90.0, screen_info: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Request file path selection from a device"""
        if not self.is_device_connected(device_id):
            raise ValueError(f"Device {device_id} not connected")

        message_id = str(uuid.uuid4())
        future = asyncio.get_event_loop().create_future()
        self.pending_requests[message_id] = future

        try:
            # Send request with optional screen info
            message: Dict[str, Any] = {
                "type": "request_file_path",
                "id": message_id,
                "timestamp": datetime.utcnow().isoformat(),
            }
            if screen_info:
                message["screen_info"] = screen_info
                
            success = await self.send_to_device(device_id, message)

            if not success:
                raise RuntimeError(f"Failed to send message to device {device_id}")

            # Wait for response with timeout
            response = await asyncio.wait_for(future, timeout=timeout)
            return response

        except asyncio.TimeoutError:
            logger.error(
                f"Timeout waiting for file_path_response from device {device_id}"
            )
            raise TimeoutError(
                f"Device {device_id} did not respond within {timeout} seconds"
            )
        finally:
            # Clean up pending request
            self.pending_requests.pop(message_id, None)

    async def send_agent_response(
        self, device_id: str, response_data: Dict[str, Any]
    ) -> bool:
        """Send an agent response to a device"""
        return await self.send_to_device(
            device_id,
            {
                "type": "agent_response",
                "data": response_data,
                "timestamp": datetime.utcnow().isoformat(),
            },
        )


# Global connection manager instance
connection_manager = ConnectionManager()
