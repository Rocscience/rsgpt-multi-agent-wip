"""Raw semantic search API endpoint"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request

from app.dependencies import verify_service_auth
from app.models.context import RawSemanticSearchRequest, RawSemanticSearchResponse
from app.services.search import ContextService, get_context_service

logger = logging.getLogger(__name__)

search_router = APIRouter(prefix="/search", tags=["search"])


@search_router.post("/semantic", response_model=RawSemanticSearchResponse)
async def raw_semantic_search(
    search_request: RawSemanticSearchRequest,
    request: Request,
    context_service: ContextService = Depends(get_context_service),
    service_name: str = Depends(verify_service_auth),
) -> RawSemanticSearchResponse:
    """
    Perform raw semantic search on a specific Pinecone index and namespace.

    This endpoint bypasses the channel configuration and conductor system,
    allowing direct access to any Pinecone index and namespace.

    Args:
        search_request: Raw semantic search request with query, index, namespace, and top_k

    Returns:
        RawSemanticSearchResponse with matching results

    Raises:
        HTTPException: 400 for invalid requests, 500 for server errors

    Requires MCP service token authentication (X-Service-Token header).
    """
    try:
        logger.info(
            f"Raw semantic search request: query='{search_request.query[:50]}...', "
            f"index='{search_request.index_name}', namespace='{search_request.namespace}', "
            f"top_k={search_request.top_k}"
        )

        response = await context_service.raw_semantic_search(search_request)

        logger.info(
            f"Search completed: {response.total_results} results from "
            f"index '{response.index_name}', namespace '{response.namespace}'"
        )

        return response

    except ValueError as e:
        logger.error(f"Invalid search request: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Raw semantic search failed: {str(e)}")
        raise HTTPException(
            status_code=500, detail="Internal server error during semantic search"
        )
