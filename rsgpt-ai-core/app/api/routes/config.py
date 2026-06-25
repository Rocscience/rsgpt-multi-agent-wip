"""Configuration management API endpoints"""

import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException

from app.services.config import ConfigService, get_config_service

logger = logging.getLogger(__name__)
config_router = APIRouter()


@config_router.get("/channels")
async def get_channel_configs(
    config_service: ConfigService = Depends(get_config_service),
) -> Dict[str, Any]:
    """
    Get all channel configurations.

    Returns the current channel configurations loaded from config.yml,
    including namespaces, index names, and settings for each channel.

    Returns:
        Dictionary with all channel configurations
    """
    try:
        logger.debug("Fetching all channel configurations")

        configs = config_service.get_all_context_store_configs()
        available_channels = config_service.get_available_channels()
        defaults = config_service.get_default_config()

        return {
            "channels": configs,
            "available_channels": available_channels,
            "defaults": defaults,
            "total_channels": len(available_channels),
        }

    except Exception as e:
        logger.error(f"Failed to get channel configs: {str(e)}")
        raise HTTPException(
            status_code=500, detail="Failed to retrieve channel configurations"
        )


@config_router.get("/channels/{channel}")
async def get_channel_config(
    channel: str, config_service: ConfigService = Depends(get_config_service)
) -> Dict[str, Any]:
    """
    Get configuration for a specific channel.

    Args:
        channel: Channel name (e.g., 'documentation', 'tech_support')

    Returns:
        Dictionary with channel configuration
    """
    try:
        logger.debug(f"Fetching configuration for channel: {channel}")

        config = config_service.get_context_store_config(channel)

        if not config or config == config_service._get_default_config():
            raise HTTPException(
                status_code=404, detail=f"Channel '{channel}' not found"
            )

        return {
            "channel": channel,
            "config": config,
            "namespace": config_service.get_channel_namespace(channel),
            "index_name": config_service.get_channel_index_name(channel),
            "top_k": config_service.get_channel_top_k(channel),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get config for channel {channel}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve configuration for channel '{channel}'",
        )


@config_router.post("/reload")
async def reload_config(
    config_service: ConfigService = Depends(get_config_service),
) -> Dict[str, str]:
    """
    Reload configuration from config.yml file.

    Useful for updating configurations without restarting the service.
    Note: This will affect all subsequent requests.

    Returns:
        Success message
    """
    try:
        logger.info("Reloading configuration from config.yml")

        config_service.reload_config()

        logger.info("Configuration reloaded successfully")
        return {"message": "Configuration reloaded successfully", "status": "success"}

    except Exception as e:
        logger.error(f"Failed to reload configuration: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to reload configuration")


@config_router.get("/health")
async def config_health_check(
    config_service: ConfigService = Depends(get_config_service),
) -> Dict[str, Any]:
    """
    Health check for configuration system.

    Returns:
        Configuration system health status
    """
    try:
        # Basic health check - get available channels
        available_channels = config_service.get_available_channels()

        return {
            "status": "healthy",
            "service": "config-service",
            "message": "Configuration service is operational",
            "channels_loaded": len(available_channels),
            "available_channels": available_channels,
        }

    except Exception as e:
        logger.error(f"Config service health check failed: {str(e)}")
        raise HTTPException(
            status_code=503, detail=f"Configuration service is unhealthy: {str(e)}"
        )
