"""Cohere reranker service for document reranking"""

import logging
from typing import List, Optional

from cohere import ClientV2

from app.config import settings
from app.models.rerank import RerankResult

logger = logging.getLogger(__name__)


class CohereReranker:
    """Reranker using Cohere's rerank API"""

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Cohere reranker.

        Args:
            api_key: Cohere API key. If None, uses settings.cohere_api_key
        """
        self.api_key = api_key if api_key is not None else settings.cohere_api_key
        self.model = "rerank-v3.5"  # Updated to match main branch toolrag

        if not self.api_key:
            logger.warning(
                "Cohere API key not configured. Reranker will not be available."
            )
            self.client = None
        else:
            self.client = ClientV2(api_key=self.api_key)

    async def rerank(
        self, query: str, documents: List[str], top_k: Optional[int] = None
    ) -> List[RerankResult]:
        """
        Rerank documents using Cohere's API.

        Args:
            query: The search query
            documents: List of document texts to rerank
            top_k: Number of top results to return (None = return all)

        Returns:
            List of RerankResult objects, ordered by relevance (highest first)

        Raises:
            ValueError: If API key is not configured or documents list is empty
            Exception: If API call fails
        """
        if not self.client:
            raise ValueError("Cohere API key is not configured")

        if not documents:
            logger.warning("Empty documents list provided to Cohere reranker")
            return []

        try:
            logger.debug(
                f"Reranking {len(documents)} documents with query: {query[:50]}..."
            )

            response = self.client.rerank(
                model=self.model,
                query=query,
                documents=documents,
                top_n=top_k if top_k else len(documents),
            )

            # Process results
            results = []
            for result in response.results:
                results.append(
                    RerankResult(
                        text=documents[result.index],
                        index=result.index,
                        relevance_score=result.relevance_score,
                    )
                )

            logger.debug(f"Successfully reranked to {len(results)} results")
            return results

        except Exception as e:
            logger.error(f"Cohere reranking error: {str(e)}")
            raise


# Global instance for dependency injection
_cohere_reranker = None


def get_cohere_reranker() -> CohereReranker:
    """Get the global Cohere reranker instance"""
    global _cohere_reranker
    if _cohere_reranker is None:
        _cohere_reranker = CohereReranker()
    return _cohere_reranker
