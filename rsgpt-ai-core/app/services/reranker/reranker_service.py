"""Unified reranker service with fallback logic"""

import logging
from typing import List

from app.models.rerank import RerankResult
from app.services.reranker.cohere_reranker import get_cohere_reranker
from app.services.reranker.keep_topk_reranker import get_keep_topk_reranker

logger = logging.getLogger(__name__)


class RerankerService:
    """
    Unified reranker service with automatic fallback.

    Uses Cohere reranker as primary, falls back to KeepTopK if Cohere fails.
    """

    def __init__(self):
        """Initialize reranker service with primary and backup rerankers"""
        self.cohere_reranker = get_cohere_reranker()
        self.backup_reranker = get_keep_topk_reranker()

    async def rerank(
        self, query: str, documents: List[str], top_k: int = 10
    ) -> tuple[List[RerankResult], str]:
        """
        Rerank documents with automatic fallback to backup reranker.

        Args:
            query: The search query
            documents: List of document texts to rerank
            top_k: Number of top results to return

        Returns:
            Tuple of (reranked results, reranker_used)
            - results: List of RerankResult objects
            - reranker_used: "cohere" or "backup"
        """
        if not documents:
            logger.warning("Empty documents list provided to reranker")
            return [], "none"

        # Try Cohere reranker first
        try:
            logger.info(f"Attempting to rerank {len(documents)} documents with Cohere")
            results = await self.cohere_reranker.rerank(query, documents, top_k)
            logger.info(f"Successfully reranked with Cohere: {len(results)} results")
            return results, "cohere"

        except ValueError as e:
            # API key not configured - use backup immediately
            logger.warning(
                f"Cohere reranker not available: {str(e)}. Using backup reranker."
            )
            results = await self.backup_reranker.rerank(query, documents, top_k)
            return results, "backup"

        except Exception as e:
            # API call failed - fall back to backup
            logger.error(
                f"Cohere reranker failed: {str(e)}. Falling back to backup reranker."
            )
            try:
                results = await self.backup_reranker.rerank(query, documents, top_k)
                logger.info(f"Backup reranker returned {len(results)} results")
                return results, "backup"
            except Exception as backup_error:
                logger.error(f"Backup reranker also failed: {str(backup_error)}")
                # Return empty list if both fail
                return [], "failed"


# Global instance for dependency injection
_reranker_service = None


def get_reranker_service() -> RerankerService:
    """Get the global reranker service instance"""
    global _reranker_service
    if _reranker_service is None:
        _reranker_service = RerankerService()
    return _reranker_service
