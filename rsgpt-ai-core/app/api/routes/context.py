"""Context retrieval API endpoints"""

import logging
from typing import Dict

from fastapi import APIRouter, Depends, HTTPException

from app.models.context import ContextRequest, ContextResponse
from app.services.search import ContextService, get_context_service

logger = logging.getLogger(__name__)
context_router = APIRouter()


@context_router.post("/search", response_model=ContextResponse)
async def search_context(
    request: ContextRequest,
    context_service: ContextService = Depends(get_context_service),
) -> ContextResponse:
    """
    Search for relevant context across available channels.

    This endpoint allows users to search for relevant context based on their query.
    The search is performed across channels that match the user's permission level.

    Args:
        request: Context search request with query and parameters

    Returns:
        ContextResponse with matching results

    Raises:
        HTTPException: 400 for invalid requests, 500 for server errors
    """
    try:
        logger.info(
            f"Context search request: query='{request.query[:50]}...', "
            f"source_channels={request.source_channels}, "
            f"permission={request.user_permission}"
        )

        response = await context_service.retrieve_context(request)

        logger.info(
            f"Search completed: {response.total_results} results from "
            f"{len(response.channels_searched)} channels"
        )

        return response

    except ValueError as e:
        logger.error(f"Invalid search request: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Context search failed: {str(e)}")
        raise HTTPException(
            status_code=500, detail="Internal server error during context search"
        )


@context_router.get("/stats", response_model=None)
async def get_context_stats(
    context_service: ContextService = Depends(get_context_service),
):
    """
    Get statistics about available channels and context data.

    Returns information about the available channels, permission levels,
    and current state of the vector database.

    Returns:
        Dictionary with channel and database statistics
    """
    try:
        logger.debug("Fetching context statistics")

        stats = await context_service.get_channel_stats()

        logger.debug("Context statistics retrieved successfully")
        return stats

    except Exception as e:
        logger.error(f"Failed to get context stats: {str(e)}")
        raise HTTPException(
            status_code=500, detail="Internal server error while fetching statistics"
        )


@context_router.get("/health")
async def context_health_check() -> Dict[str, str]:
    """
    Health check endpoint for context service.

    Returns:
        Simple health status for the context service
    """
    try:
        # Basic health check - try to get services
        get_context_service()

        return {
            "status": "healthy",
            "service": "context-service",
            "message": "Context service is operational",
        }

    except Exception as e:
        logger.error(f"Context service health check failed: {str(e)}")
        raise HTTPException(
            status_code=503, detail=f"Context service is unhealthy: {str(e)}"
        )
