"""Base agent tools for knowledge and web search"""

import json
import logging
from typing import List, Optional

from agents import RunContextWrapper, function_tool
from perplexity import AsyncPerplexity

from app.config import settings
from app.models.agent import AgentContext
from app.models.channels import SourceChannel
from app.models.context import (
    SearchKnowledgeResult,
    SearchResultContext,
    SearchResultMetadata,
    SearchResultSource,
)
from app.services.search.rag_service import get_rag_service

logger = logging.getLogger(__name__)


@function_tool()
async def search_knowledge(
    wrapper: RunContextWrapper[AgentContext],
    query: str,
    channels: Optional[List[str]] = None,
    top_k: int = 5,
) -> str:
    """
    Search the knowledge base using RAG (Retrieval-Augmented Generation).

    This tool searches through documentation and context using semantic search
    and returns relevant information with reranking. User permissions are
    automatically applied from the agent context.

    Args:
        query: The search query to look up information.
        channels: Optional list of channels to search
        (e.g., ["ROC", "DIANA", "3GSM", "2SI", "ROCKFIELD", "AQUANTY"]).
        If not provided, uses channels from agent context (defaults to ["ROC"]).
        top_k: Number of top results to return (1-20). Defaults to 5.

    Returns:
        JSON string with search results including contexts, scores, and metadata.
    """
    try:
        # Get user context for permissions
        context = wrapper.context

        # Parse channels - use explicit channels if provided, otherwise use context
        source_channels = None
        if channels:
            try:
                source_channels = [SourceChannel(ch) for ch in channels]
            except ValueError as e:
                logger.error(f"Invalid channel provided: {e}")
                return json.dumps(
                    {
                        "contexts": [],
                        "error": "Invalid channel. Valid channels: ROC, DIANA, 3GSM, 2SI, "
                        + "Rockfield, Aquanty",
                    }
                )
        else:
            # Use channels from context
            source_channels = context.source_channels

        # User permission comes from context (not as parameter)
        permission = context.user_permission

        # Validate top_k
        if not 1 <= top_k <= 20:
            return json.dumps(
                {
                    "contexts": [],
                    "error": "top_k must be between 1 and 20",
                }
            )

        logger.info(
            f"Searching knowledge base: query='{query[:50]}...', "
            f"channels={channels}, top_k={top_k}"
        )

        # Get RAG service and execute search
        rag_service = get_rag_service()
        rag_result = await rag_service.retrieve_and_rerank(
            query=query,
            source_channels=source_channels,
            user_permission=permission,
            top_k=top_k,
        )

        # Format response using strongly typed models
        def _safe_float(v, default=0.0):
            try:
                return float(v)
            except (TypeError, ValueError):
                return default

        # Create typed result object
        contexts = [
            SearchResultContext(
                text=str(context_dict.get("text", "")),
                score=_safe_float(context_dict.get("score")),
                rerank_score=_safe_float(context_dict.get("rerank_score")),
                rank=i + 1,
                channel=context_dict.get("channel"),
                source=SearchResultSource(
                    title=context_dict.get("Title") or context_dict.get("title"),
                    url=context_dict.get("URL_Link")
                    or context_dict.get("URL")
                    or context_dict.get("URL_Link_With_Page"),
                    file_name=context_dict.get("file_name"),
                    page=context_dict.get("Page_Number"),
                ),
            )
            for i, context_dict in enumerate(rag_result.contexts)
        ]

        metadata = SearchResultMetadata(
            total_retrieved=rag_result.total_retrieved,
            channels_searched=rag_result.channels_searched,
            reranker_used=rag_result.reranker_used,
            results_returned=len(rag_result.contexts),
        )

        result = SearchKnowledgeResult(
            query=rag_result.query, contexts=contexts, metadata=metadata
        )

        logger.info(
            f"Knowledge search completed: {len(rag_result.contexts)} results returned"
        )
        return result.model_dump_json()

    except Exception as e:
        logger.error(f"Error searching knowledge base: {e}")
        return json.dumps(
            {
                "contexts": [],
                "error": str(e),
            }
        )


@function_tool()
async def search_web(
    wrapper: RunContextWrapper[AgentContext],
    query: str,
    max_results: int = 5,
    max_tokens_per_page: int = 4000,
) -> str:
    """
    Search the web using Perplexity API for real-time information.

    This tool searches the web for current information, and updates
    that may not be available in the knowledge base. Ideal for
     up-to-date technical information and/or solutions to geotechnical problems.

    Args:
        query: Search query (be specific for best results).
        max_results: Number of results to return (1-20). Defaults to 5.
        max_tokens_per_page: Content extraction depth (3500-5000).
                            Higher values = more content per page. Defaults to 4000.

    Returns:
        JSON string with search results including titles, URLs, snippets, and dates.
    """
    try:
        # Validate parameters
        if not query or not query.strip():
            return json.dumps(
                {
                    "results": [],
                    "error": "Query cannot be empty",
                }
            )

        if not 1 <= max_results <= 20:
            return json.dumps(
                {
                    "results": [],
                    "error": "max_results must be between 1 and 20",
                }
            )

        if not 3500 <= max_tokens_per_page <= 5000:
            return json.dumps(
                {
                    "results": [],
                    "error": "max_tokens_per_page must be between 3500 and 5000",
                }
            )

        # Check if Perplexity API key is configured
        if not settings.perplexity_api_key:
            logger.error("Perplexity API key not configured")
            return json.dumps(
                {
                    "results": [],
                    "error": "Web search is not available (API key not configured)",
                }
            )

        logger.info(
            f"Searching web: query='{query[:50]}...', "
            f"max_results={max_results}, max_tokens_per_page={max_tokens_per_page}"
        )

        # Create async client and execute search
        async with AsyncPerplexity(api_key=settings.perplexity_api_key) as client:
            search_response = await client.search.create(
                query=query,
                max_results=max_results,
                max_tokens_per_page=max_tokens_per_page,
            )

            # Format results
            results = []
            for result in search_response.results:
                formatted_result = {
                    "title": result.title,
                    "url": result.url,
                    "snippet": result.snippet,
                }

                # Add optional fields if available
                if hasattr(result, "date") and result.date:
                    formatted_result["date"] = result.date
                if hasattr(result, "last_updated") and result.last_updated:
                    formatted_result["last_updated"] = result.last_updated

                results.append(formatted_result)

            response = {
                "query": query,
                "results": results,
                "count": len(results),
            }

            logger.info(f"Web search completed: {len(results)} results returned")
            return json.dumps(response, ensure_ascii=False)

    except Exception as e:
        logger.error(f"Error searching web: {e}")
        return json.dumps(
            {
                "results": [],
                "error": f"Web search failed: {str(e)}",
            }
        )
