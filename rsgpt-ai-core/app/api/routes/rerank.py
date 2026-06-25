"""Reranking API endpoints"""

import logging
from typing import Dict

from fastapi import APIRouter, Depends, HTTPException, Request

from app.dependencies import verify_service_auth
from app.models.rerank import RerankRequest, RerankResponse
from app.services.reranker import RerankerService, get_reranker_service

logger = logging.getLogger(__name__)
rerank_router = APIRouter()


@rerank_router.post("/", response_model=RerankResponse)
async def rerank_documents(
    rerank_request: RerankRequest,
    request: Request,
    reranker_service: RerankerService = Depends(get_reranker_service),
    service_name: str = Depends(verify_service_auth),
) -> RerankResponse:
    """
    Rerank a list of documents based on relevance to a query.

    Uses Cohere reranker as primary, falls back to KeepTopK if Cohere fails.

    Args:
        rerank_request: Rerank request with query and documents

    Returns:
        RerankResponse with reranked documents ordered by relevance

    Raises:
        HTTPException: 400 for invalid requests, 500 for server errors

    Requires MCP service token authentication (X-Service-Token header).
    """
    try:
        logger.info(
            f"Rerank request: query='{rerank_request.query[:50]}...', "
            f"documents={len(rerank_request.documents)}, top_k={rerank_request.top_k}"
        )

        results, reranker_used = await reranker_service.rerank(
            query=rerank_request.query,
            documents=rerank_request.documents,
            top_k=rerank_request.top_k,
        )

        logger.info(
            f"Reranking completed: {len(results)} results using {reranker_used} reranker"
        )

        return RerankResponse(
            query=rerank_request.query,
            results=results,
            total_results=len(results),
            reranker_used=reranker_used,
        )

    except ValueError as e:
        logger.error(f"Invalid rerank request: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Reranking failed: {str(e)}")
        raise HTTPException(
            status_code=500, detail="Internal server error during reranking"
        )


@rerank_router.get("/health")
async def rerank_health_check() -> Dict[str, str]:
    """
    Health check endpoint for reranker service.

    Returns:
        Simple health status for the reranker service
    """
    try:
        # Basic health check - try to get service
        get_reranker_service()

        return {
            "status": "healthy",
            "service": "reranker-service",
            "message": "Reranker service is operational",
        }

    except Exception as e:
        logger.error(f"Reranker service health check failed: {str(e)}")
        raise HTTPException(
            status_code=503, detail=f"Reranker service is unhealthy: {str(e)}"
        )
