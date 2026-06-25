"""Backup reranker that keeps top K documents without reranking"""

import logging
from typing import List, Optional

from app.models.rerank import RerankResult

logger = logging.getLogger(__name__)


class KeepTopKReranker:
    """
    Backup reranker that returns documents in their original order.

    This is used as a fallback when the primary reranker (Cohere) fails.
    It simply returns the top K documents without any reranking logic.
    """

    def __init__(self):
        """Initialize KeepTopK reranker"""
        pass

    async def rerank(
        self, query: str, documents: List[str], top_k: Optional[int] = None
    ) -> List[RerankResult]:
        """
        Return documents in original order, limited to top_k.

        Args:
            query: The search query (not used in this implementation)
            documents: List of document texts
            top_k: Number of top results to return (None = return all)

        Returns:
            List of RerankResult objects in original order
        """
        if not documents:
            logger.warning("Empty documents list provided to KeepTopK reranker")
            return []

        # Determine how many results to return
        num_results = min(top_k, len(documents)) if top_k else len(documents)

        logger.debug(
            f"KeepTopK reranker returning {num_results} of {len(documents)} documents"
        )

        # Create results with artificial scores (decreasing from 1.0)
        results = []
        for i in range(num_results):
            # Assign decreasing scores from 1.0 to simulate ranking
            # This ensures consistent ordering
            score = 1.0 - (i * 0.01)

            results.append(
                RerankResult(
                    text=documents[i],
                    index=i,
                    relevance_score=score,
                )
            )

        return results


# Global instance for dependency injection
_keep_topk_reranker = None


def get_keep_topk_reranker() -> KeepTopKReranker:
    """Get the global KeepTopK reranker instance"""
    global _keep_topk_reranker
    if _keep_topk_reranker is None:
        _keep_topk_reranker = KeepTopKReranker()
    return _keep_topk_reranker
