"""Pinecone vector database service for context storage and retrieval"""

import logging
from typing import Any, Dict, List, Optional

from pinecone import Pinecone

from app.config import settings
from app.models.channels import CHANNEL_CONFIG_KEYS, Channel
from app.models.context import ContextItem, RawSearchResultItem
from app.services.config import get_config_service
from app.services.search.encryption_service import get_aes_encryptor

logger = logging.getLogger(__name__)


class PineconeService:
    """Service for interacting with Pinecone vector database"""

    def __init__(self):
        """Initialize Pinecone service with API key"""
        if not settings.pinecone_api_key:
            raise ValueError("Pinecone API key is required")

        self.client = Pinecone(api_key=settings.pinecone_api_key)
        self.config_service = get_config_service()
        self.default_top_k = settings.pinecone_default_top_k
        self.encryptor = get_aes_encryptor()

        # Cache for index connections
        self._indexes = {}

    def _get_index(self, index_name: str):
        """Get or create index connection for the given index name"""
        if index_name not in self._indexes:
            try:
                # Check if index exists
                existing_indexes = self.client.list_indexes()
                available_names = [idx["name"] for idx in existing_indexes.indexes]

                if index_name not in available_names:
                    logger.warning(
                        f"Index '{index_name}' not found. Available: {available_names}"
                    )
                    raise ValueError(f"Index '{index_name}' does not exist")

                self._indexes[index_name] = self.client.Index(index_name)
                logger.debug(f"Connected to Pinecone index: {index_name}")

            except Exception as e:
                logger.error(f"Failed to connect to index '{index_name}': {str(e)}")
                raise

        return self._indexes[index_name]

    async def raw_search(
        self,
        query_vector: List[float],
        index_name: str,
        namespace: str,
        top_k: int,
    ) -> List[RawSearchResultItem]:
        """
        Perform raw semantic search on a specific Pinecone index and namespace.
        This bypasses the channel configuration system and returns raw metadata as-is.

        Args:
            query_vector: Embedding vector for the search query
            index_name: Name of the Pinecone index
            namespace: Namespace to search in
            top_k: Number of results to return

        Returns:
            List of RawSearchResultItem objects with raw metadata

        Raises:
            ValueError: If index does not exist
            Exception: For other Pinecone API errors
        """
        try:
            logger.debug(
                f"Raw search in index '{index_name}', namespace '{namespace}' "
                f"with top_k={top_k}"
            )

            index = self._get_index(index_name)
            response = index.query(
                vector=query_vector,
                top_k=top_k,
                include_metadata=True,
                namespace=namespace,
            )

            results = self._process_raw_search_results(response.matches)
            logger.debug(f"Found {len(results)} results")

            return results

        except Exception as e:
            logger.error(
                f"Raw search failed in index '{index_name}', namespace '{namespace}': {str(e)}"
            )
            raise

    async def search_context(
        self, query_vector: List[float], channel: Channel, top_k: Optional[int] = None
    ) -> List[ContextItem]:
        """
        Search for similar contexts in the specified channel namespace.

        Args:
            query_vector: Embedding vector for the search query
            channel: Channel to search in
            top_k: Number of results to return (defaults to configured value)

        Returns:
            List of ContextItem objects with search results

        Raises:
            ValueError: If channel is not supported or query fails
            Exception: For other Pinecone API errors
        """
        if channel not in CHANNEL_CONFIG_KEYS:
            raise ValueError(f"Unsupported channel: {channel}")

        # Get channel configuration
        config_key = CHANNEL_CONFIG_KEYS[channel]
        namespace = self.config_service.get_channel_namespace(config_key)
        index_name = self.config_service.get_channel_index_name(config_key)
        search_top_k = top_k or self.config_service.get_channel_top_k(config_key)

        try:
            logger.debug(
                f"Searching in index '{index_name}', namespace '{namespace}' "
                f"with top_k={search_top_k} for channel {channel}"
            )

            index = self._get_index(index_name)
            response = index.query(
                vector=query_vector,
                top_k=search_top_k,
                include_metadata=True,
                namespace=namespace,
            )

            results = self._process_search_results(response.matches)

            # Decrypt text if channel is encrypted
            if self.config_service.is_channel_encrypted(config_key):
                results = self._decrypt_results(results, channel)

            logger.debug(f"Found {len(results)} results in channel {channel}")

            return results

        except Exception as e:
            logger.error(f"Search failed in channel {channel}: {str(e)}")
            raise

    async def search_multiple_channels(
        self,
        query_vector: List[float],
        channels: List[Channel],
        top_k_per_channel: Optional[int] = None,
    ) -> Dict[Channel, List[ContextItem]]:
        """
        Search for contexts across multiple channel namespaces.

        Args:
            query_vector: Embedding vector for the search query
            channels: List of channels to search in
            top_k_per_channel: Number of results per channel

        Returns:
            Dictionary mapping channels to their search results
        """
        results = {}

        for channel in channels:
            try:
                channel_results = await self.search_context(
                    query_vector, channel, top_k_per_channel
                )
                results[channel] = channel_results

            except Exception as e:
                logger.error(f"Failed to search channel {channel}: {str(e)}")
                results[channel] = []  # Return empty list on error

        return results

    async def store_context(
        self,
        text_id: str,
        vector: List[float],
        channel: Channel,
        metadata: Dict[str, Any],
    ) -> bool:
        """
        Store a context vector in the specified channel namespace.

        Args:
            text_id: Unique identifier for the text
            vector: Embedding vector
            channel: Channel to store in
            metadata: Additional metadata to store

        Returns:
            True if successful, False otherwise
        """
        if channel not in CHANNEL_CONFIG_KEYS:
            raise ValueError(f"Unsupported channel: {channel}")

        # Get channel configuration
        config_key = CHANNEL_CONFIG_KEYS[channel]
        namespace = self.config_service.get_channel_namespace(config_key)
        index_name = self.config_service.get_channel_index_name(config_key)

        try:
            # Add text content to metadata for retrieval
            full_metadata = {
                "text": metadata.get("text", ""),
                "channel": channel.value,
                **metadata,
            }

            index = self._get_index(index_name)
            index.upsert(
                vectors=[(text_id, vector, full_metadata)], namespace=namespace
            )

            logger.debug(f"Stored context {text_id} in channel {channel}")
            return True

        except Exception as e:
            logger.error(f"Failed to store context: {str(e)}")
            return False

    def _process_raw_search_results(
        self, matches: List[Dict]
    ) -> List[RawSearchResultItem]:
        """
        Process Pinecone search results into RawSearchResultItem objects.
        Returns raw metadata as-is without any assumptions about structure.

        Args:
            matches: Raw matches from Pinecone query response

        Returns:
            List of RawSearchResultItem objects with raw metadata
        """
        results = []

        for match in matches:
            metadata = match.get("metadata", {})

            # Create RawSearchResultItem with full metadata
            result_item = RawSearchResultItem(
                id=match.get("id", ""),
                score=match.get("score", 0.0),
                metadata=metadata,
            )

            results.append(result_item)

        return results

    def _process_search_results(self, matches: List[Dict]) -> List[ContextItem]:
        """
        Process Pinecone search results into ContextItem objects.

        Args:
            matches: Raw matches from Pinecone query response

        Returns:
            List of processed ContextItem objects
        """
        results = []

        for match in matches:
            metadata = match.get("metadata", {})

            # Extract text content (required field)
            text = metadata.get("text", "")
            if not text:
                logger.warning(f"Skipping match {match.get('id')} - no text content")
                continue

            # Create ContextItem with available metadata
            context_item = ContextItem(
                id=match.get("id", ""),
                text=text,
                score=match.get("score", 0.0),
                url_link=metadata.get("URL Link") or metadata.get("url"),
                file_name=metadata.get("file name") or metadata.get("file_name"),
                software=metadata.get("software"),
                title=metadata.get("Title") or metadata.get("title"),
                page_number=(
                    str(metadata.get("Page_Number", ""))
                    if metadata.get("Page_Number")
                    else None
                ),
                source=metadata.get("source"),
                channel=metadata.get("channel"),
            )

            results.append(context_item)

        return results

    def _decrypt_results(
        self, results: List[ContextItem], channel: Channel
    ) -> List[ContextItem]:
        """
        Decrypt text content for results from encrypted channels.

        Args:
            results: List of ContextItem objects with encrypted text
            channel: The channel these results came from (for logging)

        Returns:
            List of ContextItem objects with decrypted text
        """
        if not self.encryptor:
            logger.warning(
                f"Encryptor not available for encrypted channel {channel}. "
                "Text will remain encrypted."
            )
            return results

        decrypted_results = []
        for result in results:
            try:
                decrypted_text = self.encryptor.decrypt_text(result.text)
                # Create new ContextItem with decrypted text
                decrypted_result = result.model_copy(update={"text": decrypted_text})
                decrypted_results.append(decrypted_result)
            except Exception as e:
                logger.error(
                    f"Failed to decrypt result {result.id} from channel {channel}: {e}"
                )
                # Keep original encrypted result on failure
                decrypted_results.append(result)

        return decrypted_results

    def get_index_stats(self) -> Dict[str, Any]:
        """Get statistics about all Pinecone indexes used by channels"""
        try:
            all_configs = self.config_service.get_all_context_store_configs()
            stats = {}

            # Get unique index names
            index_names = set()
            for config in all_configs.values():
                index_names.add(config.get("index_name", settings.pinecone_index_name))

            # Get stats for each index
            for index_name in index_names:
                try:
                    index = self._get_index(index_name)
                    index_stats = index.describe_index_stats()

                    # Convert namespaces to serializable format
                    namespaces = {}
                    if index_stats.namespaces:
                        for ns_name, ns_data in index_stats.namespaces.items():
                            namespaces[ns_name] = {
                                "vector_count": (
                                    ns_data.vector_count
                                    if hasattr(ns_data, "vector_count")
                                    else 0
                                )
                            }

                    stats[index_name] = {
                        "total_vector_count": index_stats.total_vector_count,
                        "namespaces": namespaces,
                        "dimension": index_stats.dimension,
                    }
                except Exception as e:
                    logger.error(f"Failed to get stats for index {index_name}: {e}")
                    stats[index_name] = {"error": str(e)}

            return stats

        except Exception as e:
            logger.error(f"Failed to get index stats: {str(e)}")
            return {}


# Global instance for dependency injection
_pinecone_service = None


def get_pinecone_service() -> PineconeService:
    """Get the global Pinecone service instance"""
    global _pinecone_service
    if _pinecone_service is None:
        _pinecone_service = PineconeService()
    return _pinecone_service
