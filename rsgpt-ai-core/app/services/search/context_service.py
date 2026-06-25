"""Unified context retrieval service combining embedding and Pinecone operations"""

import logging
from typing import Any, Dict

from app.models.channels import Channel, UserPermission
from app.models.context import (
    ContextRequest,
    ContextResponse,
    RawSemanticSearchRequest,
    RawSemanticSearchResponse,
)
from app.services.config import get_conductor_service

from .embedding_service import get_embedding_service
from .pinecone_service import get_pinecone_service

logger = logging.getLogger(__name__)


class ContextService:
    """Unified service for context retrieval and storage operations"""

    def __init__(self):
        """Initialize context service with embedding, Pinecone, and conductor services"""
        self.embedding_service = get_embedding_service()
        self.pinecone_service = get_pinecone_service()
        self.conductor_service = get_conductor_service()

    async def retrieve_context(self, request: ContextRequest) -> ContextResponse:
        """
        Retrieve relevant context based on the request.

        Uses conductor service to map source_channels to internal channels based on user permission.
        Matches the behavior of the original RSGPT-App channel system.

        Args:
            request: ContextRequest with query and search parameters

        Returns:
            ContextResponse with retrieved context items
        """
        try:
            # Use conductor to map source_channels -> internal channels
            # This matches the SimpleConductor logic from RSGPT-App
            search_channels = self.conductor_service.conduct(
                user_permission=request.user_permission,
                source_channels=request.source_channels,
            )
            logger.info(
                f"Conductor mapped source_channels={request.source_channels} "
                f"with permission={request.user_permission} to channels={search_channels}"
            )

            if not search_channels:
                logger.warning("No accessible channels found for user permission")
                return ContextResponse(
                    query=request.query,
                    results=[],
                    channels_searched=[],
                    total_results=0,
                )

            # Generate embedding for the query
            logger.debug(f"Generating embedding for query: {request.query[:100]}...")
            query_vector = await self.embedding_service.embed_text(request.query)

            # Search across channels
            all_results = []
            channels_searched = []

            for channel in search_channels:
                try:
                    channel_results = await self.pinecone_service.search_context(
                        query_vector=query_vector, channel=channel, top_k=request.top_k
                    )

                    # Set the channel on each result
                    for result in channel_results:
                        result.channel = channel.value

                    all_results.extend(channel_results)
                    channels_searched.append(channel)
                    logger.debug(
                        f"Found {len(channel_results)} results in channel {channel}"
                    )

                except Exception as e:
                    logger.error(f"Failed to search channel {channel}: {str(e)}")
                    # Continue with other channels

            # Sort results by relevance score (descending)
            all_results.sort(key=lambda x: x.score, reverse=True)

            # Apply top_k limit if specified
            if request.top_k:
                all_results = all_results[: request.top_k]

            logger.info(
                f"Retrieved {len(all_results)} context items across "
                f"{len(channels_searched)} channels"
            )

            return ContextResponse(
                query=request.query,
                results=all_results,
                channels_searched=channels_searched,
                total_results=len(all_results),
            )

        except Exception as e:
            logger.error(f"Context retrieval failed: {str(e)}")
            raise

    async def raw_semantic_search(
        self, request: RawSemanticSearchRequest
    ) -> RawSemanticSearchResponse:
        """
        Perform raw semantic search on a specific Pinecone index and namespace.
        This bypasses the channel configuration and conductor system.

        Args:
            request: RawSemanticSearchRequest with query and target parameters

        Returns:
            RawSemanticSearchResponse with search results

        Raises:
            Exception: If search fails
        """
        try:
            logger.info(
                f"Raw semantic search: query='{request.query[:50]}...', "
                f"index='{request.index_name}', namespace='{request.namespace}', "
                f"top_k={request.top_k}"
            )

            # Generate embedding for the query
            query_vector = await self.embedding_service.embed_text(request.query)

            # Perform raw search
            results = await self.pinecone_service.raw_search(
                query_vector=query_vector,
                index_name=request.index_name,
                namespace=request.namespace,
                top_k=request.top_k,
            )

            logger.info(f"Raw search completed: {len(results)} results found")

            return RawSemanticSearchResponse(
                query=request.query,
                results=results,
                namespace=request.namespace,
                index_name=request.index_name,
                total_results=len(results),
            )

        except Exception as e:
            logger.error(f"Raw semantic search failed: {str(e)}")
            raise

    async def get_channel_stats(self) -> Dict[str, Any]:
        """Get statistics about available channels and content"""
        try:
            pinecone_stats = self.pinecone_service.get_index_stats()

            return {
                "available_channels": [channel.value for channel in Channel],
                "permission_levels": [perm.value for perm in UserPermission],
                "pinecone_stats": pinecone_stats,
                "embedding_model": self.embedding_service.model,
            }

        except Exception as e:
            logger.error(f"Failed to get channel stats: {str(e)}")
            return {}


# Global instance for dependency injection
_context_service = None


def get_context_service() -> ContextService:
    """Get the global context service instance"""
    global _context_service
    if _context_service is None:
        _context_service = ContextService()
    return _context_service
