"""Unified RAG (Retrieval-Augmented Generation) service combining context retrieval and reranking"""

import logging
from typing import Any, Dict, List, Optional

from app.models.channels import SourceChannel, UserPermission
from app.models.context import ContextRequest
from app.services.reranker import get_reranker_service
from app.services.search.context_service import get_context_service

logger = logging.getLogger(__name__)


class RAGResult:
    """Result from RAG pipeline containing reranked context"""

    def __init__(
        self,
        query: str,
        contexts: List[Dict[str, Any]],
        reranker_used: str,
        total_retrieved: int,
        channels_searched: List[str],
    ):
        self.query = query
        self.contexts = contexts
        self.reranker_used = reranker_used
        self.total_retrieved = total_retrieved
        self.channels_searched = channels_searched

    def _format_context_list(self, contexts: List[Dict[str, Any]]) -> str:
        """Helper to format a list of contexts into a prompt-ready string"""
        if not contexts:
            return ""

        formatted_string = ""
        # Iterate over each dictionary in the list
        for index, entry in enumerate(contexts):
            formatted_string += f"Entry {index + 1}:\n"
            if "Title" in entry and entry["Title"] is not None:
                formatted_string += f"Title: {entry['Title']}\n"
            if "text" in entry and entry["text"] is not None:
                formatted_string += f"Text: {entry['text'].strip()}\n"
            if "score" in entry and entry["score"] is not None:
                formatted_string += f"Score: {entry['score']}\n"
            if "rerank_score" in entry and entry["rerank_score"] is not None:
                formatted_string += f"Rerank Score: {entry['rerank_score']}\n"
            if "URL_Link" in entry and entry["URL_Link"] is not None:
                formatted_string += f"URL Link: {entry['URL_Link']}\n"
            if "file_name" in entry and entry["file_name"] is not None:
                formatted_string += f"File Name: {entry['file_name']}\n"
            if "software" in entry and entry["software"] is not None:
                formatted_string += f"Software: {entry['software']}\n"
            if "Page_Number" in entry and entry["Page_Number"] is not None:
                formatted_string += f"Page Number: {entry['Page_Number']}\n"
            if (
                "URL_Link_With_Page" in entry
                and entry["URL_Link_With_Page"] is not None
            ):
                formatted_string += (
                    f"URL Link With Page: {entry['URL_Link_With_Page']}\n"
                )
            if "source" in entry and entry["source"] is not None:
                formatted_string += f"Source: {entry['source']}\n"
            if "channel" in entry and entry["channel"] is not None:
                formatted_string += f"Channel: {entry['channel']}\n"
            formatted_string += "\n"  # Add a newline to separate entries
        return formatted_string

    def format_context(self) -> str:
        """Format the contexts into a prompt-ready string"""
        return self._format_context_list(self.contexts)

    def format_context_by_channel(
        self, tech_support_channel: str = "tech_support"
    ) -> tuple[str, str]:
        """
        Format contexts separated by channel type.

        Args:
            tech_support_channel: Name of the tech support channel to separate

        Returns:
            Tuple of (expert_opinion_context, other_context)
            - expert_opinion_context: Formatted string of tech support contexts
            - other_context: Formatted string of all other contexts
        """
        tech_support_contexts = []
        other_contexts = []

        for context in self.contexts:
            if context.get("channel") == tech_support_channel:
                tech_support_contexts.append(context)
            else:
                other_contexts.append(context)

        expert_opinion = self._format_context_list(tech_support_contexts)
        relevant_context = self._format_context_list(other_contexts)

        return expert_opinion, relevant_context


class RAGService:
    """
    Unified RAG service combining context retrieval and reranking.

    This service encapsulates the entire RAG pipeline:
    1. Generate embeddings
    2. Search Pinecone for relevant context
    3. Rerank results using Cohere or fallback reranker
    """

    def __init__(self):
        """Initialize RAG service with context and reranker services"""
        self.context_service = get_context_service()
        self.reranker_service = get_reranker_service()

    async def retrieve_and_rerank(
        self,
        query: str,
        source_channels: Optional[List[SourceChannel]] = None,
        user_permission: UserPermission = UserPermission.BASIC,
        top_k: int = 5,
        initial_retrieval_k: Optional[int] = None,
    ) -> RAGResult:
        """
        Execute the full RAG pipeline: retrieve context and rerank.

        Args:
            query: The search query
            source_channels: Source channels to search (defaults to [ROC])
            user_permission: User's permission level
            top_k: Final number of results to return after reranking
            initial_retrieval_k: Number of results to retrieve before reranking
                                (defaults to top_k * 3 for better reranking)

        Returns:
            RAGResult with reranked contexts and metadata
        """
        try:
            # Default to retrieving 3x the final top_k for better reranking
            if initial_retrieval_k is None:
                initial_retrieval_k = top_k * 3

            # Use default source channels if not provided
            if source_channels is None:
                source_channels = [SourceChannel.ROC]

            logger.info(
                f"Starting RAG pipeline: query='{query[:50]}...', "
                f"channels={source_channels}, top_k={top_k}"
            )

            # 1. Retrieve context from Pinecone
            context_request = ContextRequest(
                query=query,
                source_channels=source_channels,
                user_permission=user_permission,
                top_k=initial_retrieval_k,
            )

            context_response = await self.context_service.retrieve_context(
                context_request
            )

            if not context_response.results:
                logger.warning(f"No context retrieved for query: {query[:50]}...")
                return RAGResult(
                    query=query,
                    contexts=[],
                    reranker_used="none",
                    total_retrieved=0,
                    channels_searched=[
                        ch.value for ch in context_response.channels_searched
                    ],
                )

            logger.info(
                f"Retrieved {len(context_response.results)} contexts from "
                f"{len(context_response.channels_searched)} channels"
            )

            # 2. Keep original results list for stable index-based lookup
            results = list(context_response.results)

            # 3. Prepare documents for reranking
            documents = [item.text for item in results]

            # 4. Rerank the documents
            reranked_results, reranker_used = await self.reranker_service.rerank(
                query=query, documents=documents, top_k=top_k
            )

            # 5. Build context dictionaries with full metadata using index-based lookup
            context_dicts = []
            for result in reranked_results:
                # Use the stable index from reranker to fetch original item
                if not (0 <= result.index < len(results)):
                    logger.warning(
                        f"Reranker returned invalid index {result.index} "
                        f"(valid range: 0-{len(results)-1}), skipping result"
                    )
                    continue
                original_item = results[result.index]

                context_dict = {
                    "text": result.text,
                    "score": original_item.score,
                    "rerank_score": result.relevance_score,
                    "Title": original_item.title,
                    "URL_Link": original_item.url_link,
                    "file_name": original_item.file_name,
                    "software": original_item.software,
                    "Page_Number": original_item.page_number,
                    "source": original_item.source,
                    "channel": original_item.channel,
                }
                # Add URL_Link_With_Page if we have both URL and page number
                if original_item.url_link and original_item.page_number:
                    context_dict["URL_Link_With_Page"] = (
                        f"{original_item.url_link}#page={original_item.page_number}"
                    )
                else:
                    context_dict["URL_Link_With_Page"] = None

                context_dicts.append(context_dict)

            logger.info(
                f"RAG pipeline completed: {len(context_dicts)} contexts returned "
                f"(reranker: {reranker_used})"
            )

            return RAGResult(
                query=query,
                contexts=context_dicts,
                reranker_used=reranker_used,
                total_retrieved=len(context_response.results),
                channels_searched=[
                    ch.value for ch in context_response.channels_searched
                ],
            )

        except Exception as e:
            logger.error(f"RAG pipeline failed: {str(e)}")
            raise


# Global instance for dependency injection
_rag_service = None


def get_rag_service() -> RAGService:
    """Get the global RAG service instance"""
    global _rag_service
    if _rag_service is None:
        _rag_service = RAGService()
    return _rag_service
