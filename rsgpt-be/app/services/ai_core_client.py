"""AI Core client service for streaming chat and agent responses"""

import logging
from typing import AsyncGenerator, List, Optional
import httpx
from app.config import settings
from app.models.enums import User_Permission_Enum
from app.models.consts import CLIENT_TYPE_BACKEND
from app.services.auth0_m2m_service import m2m_token_service


logger = logging.getLogger(__name__)


class AICoreClient:
    """Client for communicating with rsgpt-ai-core streaming service"""
    
    def __init__(self):
        self.base_url = settings.ai_core_url
        self.timeout = httpx.Timeout(300.0, connect=10.0)  # 5 minute timeout for streaming, 10s for connection
    
    async def stream_chat_completion(
        self,
        messages: List[dict],
        provider: str,
        model: str,
        session_id: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        use_rag: bool = True,
        rag_source_channels: Optional[List[str]] = None,
        rag_user_permission: str = User_Permission_Enum.BASIC,
        reasoning_level: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        """
        Stream chat completion from AI core service.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            provider: LLM provider (openai, anthropic, perplexity)
            model: Specific model to use
            session_id: Chat session ID for context management
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            use_rag: Whether to use RAG for context retrieval
            rag_source_channels: Source channels for RAG
            rag_user_permission: User permission level for RAG
            reasoning_level: Reasoning level (minimal, medium, high) for GPT-5
            
        Yields:
            Raw SSE event strings from the ai-core service
        """
        url = f"{self.base_url}/api/v1/chat/stream"
        
        # Prepare request body
        body = {
            "messages": messages,
            "provider": provider,
            "model": model,
            "use_rag": use_rag,
            "rag_user_permission": rag_user_permission.lower() if isinstance(rag_user_permission, str) else rag_user_permission
        }
        
        if session_id:
            body["session_id"] = session_id
        if max_tokens:
            body["max_tokens"] = max_tokens
        if temperature:
            body["temperature"] = temperature
        if rag_source_channels:
            body["rag_source_channels"] = rag_source_channels
        if reasoning_level:
            body["reasoning_effort"] = reasoning_level
        
        logger.debug(f"Sending chat request to AI core: {url}")
        logger.debug(f"Request body: {body}")

        # Prepare headers with authentication
        # X-Client-Type identifies this as a Backend client (vs Desktop)
        headers = {
            "X-Client-Type": CLIENT_TYPE_BACKEND
        }
        if settings.is_development:
            # Development: Use static service token
            if settings.ai_core_service_token:
                headers["X-Service-Token"] = settings.ai_core_service_token
                logger.debug("DEV MODE: Using X-Service-Token for authentication")
        else:
            # Production: Use M2M JWT
            try:
                m2m_token = await m2m_token_service.get_token()
                headers["Authorization"] = f"Bearer {m2m_token}"
                logger.debug("PROD MODE: Using M2M JWT for authentication")
            except Exception as e:
                logger.error(f"Failed to get M2M token: {e}")
                raise ConnectionError(f"M2M authentication error: {e}")

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                async with client.stream("POST", url, json=body, headers=headers) as response:
                    try:
                        response.raise_for_status()
                    except httpx.HTTPStatusError as e:
                        # Read the error response body before raising
                        error_body = await response.aread()
                        logger.error(f"HTTP error from AI core service: {e.response.status_code} - {error_body.decode()}")
                        raise ConnectionError(f"AI core service error {e.response.status_code}: {error_body.decode()}")
                    
                    async for chunk in response.aiter_text():
                        if chunk:
                            yield chunk
                            
        except httpx.TimeoutException as e:
            logger.error(f"Timeout connecting to AI core service: {e}")
            raise ConnectionError(f"AI core service timeout: {e}")
        except ConnectionError:
            # Re-raise ConnectionError from above
            raise
        except Exception as e:
            logger.error(f"Unexpected error streaming from AI core: {e}")
            raise ConnectionError(f"AI core service error: {e}")
    
    async def stream_agent_completion(
        self,
        input: str,
        session_id: str,
        mode: str = "agent",
        provider: str = "openai",
        model: str = "gpt-5",
        device_id: Optional[str] = None,
        user_permission: str = User_Permission_Enum.BASIC,
        source_channels: Optional[List[str]] = None,
        reasoning_effort: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """
        Stream agent completion from AI core service.
        
        Args:
            input: User's input message
            session_id: Chat session ID (required - SDK session handles history)
            mode: Agent mode ("ask" for knowledge-only, "agent" for full tools)
            provider: LLM provider (openai, anthropic, perplexity)
            model: Model to use
            device_id: Device ID for device-specific tool operations (agent mode only)
            user_permission: User permission level for tools
            source_channels: Source channels for knowledge search
            reasoning_effort: Reasoning effort level (low, medium, high)
            
        Yields:
            Raw SSE event strings from the ai-core service
        """
        url = f"{self.base_url}/api/v1/agent/stream"

        formatted_model = f"{provider}/{model}" if "/" not in model else model
        
        # Prepare request body
        body = {
            "input": input,
            "session_id": session_id,
            "mode": mode,
            "model": formatted_model,
            "user_permission": user_permission.lower() if isinstance(user_permission, str) else user_permission,
            "source_channels": source_channels or ["ROC"],
            "use_sdk_session": True,
        }
        
        if device_id:
            body["device_id"] = device_id
        if reasoning_effort:
            body["reasoning_effort"] = reasoning_effort
        
        logger.debug(f"Sending agent request to AI core: {url}")
        logger.debug(f"Request body: {body}")

        # Prepare headers with authentication
        # X-Client-Type identifies this as a Backend client (vs Desktop)
        headers = {
            "X-Client-Type": CLIENT_TYPE_BACKEND
        }
        if settings.is_development:
            # Development: Use static service token
            if settings.ai_core_service_token:
                headers["X-Service-Token"] = settings.ai_core_service_token
                logger.debug("DEV MODE: Using X-Service-Token for authentication")
        else:
            # Production: Use M2M JWT
            try:
                m2m_token = await m2m_token_service.get_token()
                headers["Authorization"] = f"Bearer {m2m_token}"
                logger.debug("PROD MODE: Using M2M JWT for authentication")
            except Exception as e:
                logger.error(f"Failed to get M2M token: {e}")
                raise ConnectionError(f"M2M authentication error: {e}")

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                async with client.stream("POST", url, json=body, headers=headers) as response:
                    try:
                        response.raise_for_status()
                    except httpx.HTTPStatusError as e:
                        # Read the error response body before raising
                        error_body = await response.aread()
                        logger.error(f"HTTP error from AI core service: {e.response.status_code} - {error_body.decode()}")
                        raise ConnectionError(f"AI core service error {e.response.status_code}: {error_body.decode()}")
                    
                    async for chunk in response.aiter_text():
                        if chunk:
                            yield chunk
                            
        except httpx.TimeoutException as e:
            logger.error(f"Timeout connecting to AI core service: {e}")
            raise ConnectionError(f"AI core service timeout: {e}")
        except ConnectionError:
            # Re-raise ConnectionError from above
            raise
        except Exception as e:
            logger.error(f"Unexpected error streaming from AI core: {e}")
            raise ConnectionError(f"AI core service error: {e}")
    
    async def request_file_path(
        self,
        device_id: str,
        screen_info: Optional[dict] = None,
        timeout: float = 30.0
    ) -> dict:
        """
        Request file path selection from a device via ai-core WebSocket.
        
        Args:
            device_id: Device ID to request file path from
            screen_info: Optional screen position info for dialog placement
            timeout: Timeout for waiting for device response
            
        Returns:
            Dict with file_path, canceled, or error fields
        """
        url = f"{self.base_url}/api/v1/ws/request_file_path/{device_id}"
        
        # Prepare request body
        body = {"timeout": timeout}
        if screen_info:
            body["screenInfo"] = screen_info
        
        logger.debug(f"Requesting file path from device {device_id} via AI core")

        # Prepare headers with authentication
        headers = {
            "Content-Type": "application/json",
            "X-Client-Type": CLIENT_TYPE_BACKEND
        }
        if settings.is_development:
            # Development: Use static service token
            if settings.ai_core_service_token:
                headers["X-Service-Token"] = settings.ai_core_service_token
                logger.debug("DEV MODE: Using X-Service-Token for authentication")
        else:
            # Production: Use M2M JWT
            try:
                m2m_token = await m2m_token_service.get_token()
                headers["Authorization"] = f"Bearer {m2m_token}"
                logger.debug("PROD MODE: Using M2M JWT for authentication")
            except Exception as e:
                logger.error(f"Failed to get M2M token: {e}")
                raise ConnectionError(f"M2M authentication error: {e}")
        
        # Use shorter timeout for file path selection
        file_path_timeout = httpx.Timeout(timeout + 5.0, connect=10.0)
        
        try:
            async with httpx.AsyncClient(timeout=file_path_timeout) as client:
                response = await client.post(url, json=body, headers=headers)
                
                try:
                    response.raise_for_status()
                except httpx.HTTPStatusError as e:
                    error_body = await response.aread()
                    logger.error(f"HTTP error from AI core service: {e.response.status_code} - {error_body.decode()}")
                    
                    # Pass through specific error codes
                    if e.response.status_code == 404:
                        raise ConnectionError(f"Device {device_id} not connected")
                    elif e.response.status_code == 504:
                        raise ConnectionError(f"Device {device_id} did not respond in time")
                    else:
                        raise ConnectionError(f"AI core service error {e.response.status_code}: {error_body.decode()}")
                
                # Parse and return response
                return response.json()
                
        except httpx.TimeoutException as e:
            logger.error(f"Timeout requesting file path from device {device_id}: {e}")
            raise ConnectionError(f"Device {device_id} did not respond in time")
        except ConnectionError:
            # Re-raise ConnectionError from above
            raise
        except Exception as e:
            logger.error(f"Unexpected error requesting file path: {e}")
            raise ConnectionError(f"Failed to request file path: {e}")


# Singleton instance
ai_core_client = AICoreClient()

