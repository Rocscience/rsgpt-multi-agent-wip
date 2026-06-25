"""Tests for RAG service"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.channels import Channel, SourceChannel, UserPermission
from app.models.context import ContextItem, ContextResponse
from app.models.rerank import RerankResult
from app.services.search.rag_service import RAGResult, RAGService, get_rag_service


@pytest.fixture
def mock_context_service():
    """Mock context service"""
    service = MagicMock()
    service.retrieve_context = AsyncMock()
    return service


@pytest.fixture
def mock_reranker_service():
    """Mock reranker service"""
    service = MagicMock()
    service.rerank = AsyncMock()
    return service


@pytest.fixture
def rag_service(mock_context_service, mock_reranker_service):
    """Create RAG service with mocked dependencies"""
    with patch(
        "app.services.search.rag_service.get_context_service",
        return_value=mock_context_service,
    ):
        with patch(
            "app.services.search.rag_service.get_reranker_service",
            return_value=mock_reranker_service,
        ):
            return RAGService()


class TestRAGResult:
    """Tests for RAGResult class"""

    def test_rag_result_creation(self):
        """Test RAGResult can be created with all fields"""
        result = RAGResult(
            query="test query",
            contexts=[
                {"text": "context 1", "score": 0.9, "rerank_score": 0.95},
                {"text": "context 2", "score": 0.8, "rerank_score": 0.85},
            ],
            reranker_used="cohere",
            total_retrieved=10,
            channels_searched=["documentation", "tech_support"],
        )

        assert result.query == "test query"
        assert len(result.contexts) == 2
        assert result.reranker_used == "cohere"
        assert result.total_retrieved == 10
        assert len(result.channels_searched) == 2

    def test_rag_result_format_context_with_results(self):
        """Test formatting contexts into a prompt-ready string"""
        result = RAGResult(
            query="test query",
            contexts=[
                {
                    "text": "First context",
                    "score": 0.90,
                    "rerank_score": 0.95,
                    "Title": "First Title",
                    "URL_Link": "http://example.com/1",
                    "file_name": None,
                    "software": None,
                    "Page_Number": None,
                    "URL_Link_With_Page": None,
                    "source": "test_source",
                },
                {
                    "text": "Second context",
                    "score": 0.80,
                    "rerank_score": 0.87,
                    "Title": None,
                    "URL_Link": None,
                    "file_name": "test.pdf",
                    "software": None,
                    "Page_Number": None,
                    "URL_Link_With_Page": None,
                    "source": None,
                },
            ],
            reranker_used="cohere",
            total_retrieved=5,
            channels_searched=["documentation"],
        )

        formatted = result.format_context()

        assert "Entry 1:" in formatted
        assert "Entry 2:" in formatted
        assert "First context" in formatted
        assert "Second context" in formatted
        assert "Score: 0.9" in formatted
        assert "Score: 0.8" in formatted
        assert "Rerank Score: 0.95" in formatted
        assert "Rerank Score: 0.87" in formatted
        assert "Title: First Title" in formatted
        assert "URL Link: http://example.com/1" in formatted
        assert "File Name: test.pdf" in formatted
        assert "Source: test_source" in formatted

    def test_rag_result_format_context_empty(self):
        """Test formatting with no contexts returns empty string"""
        result = RAGResult(
            query="test query",
            contexts=[],
            reranker_used="none",
            total_retrieved=0,
            channels_searched=[],
        )

        formatted = result.format_context()
        assert formatted == ""


class TestRAGService:
    """Tests for RAGService class"""

    @pytest.mark.asyncio
    async def test_retrieve_and_rerank_success(
        self, rag_service, mock_context_service, mock_reranker_service
    ):
        """Test successful RAG pipeline execution"""
        # Mock context retrieval
        mock_context_response = ContextResponse(
            query="test query",
            results=[
                ContextItem(id="1", text="context 1", score=0.9),
                ContextItem(id="2", text="context 2", score=0.8),
                ContextItem(id="3", text="context 3", score=0.7),
            ],
            channels_searched=[Channel.DOCUMENTATION],
            total_results=3,
        )
        mock_context_service.retrieve_context.return_value = mock_context_response

        # Mock reranking
        mock_reranker_service.rerank.return_value = (
            [
                RerankResult(text="context 1", relevance_score=0.95, index=0),
                RerankResult(text="context 3", relevance_score=0.85, index=2),
            ],
            "cohere",
        )

        # Execute RAG pipeline
        result = await rag_service.retrieve_and_rerank(
            query="test query",
            source_channels=[SourceChannel.ROC],
            user_permission=UserPermission.BASIC,
            top_k=2,
        )

        # Verify context service was called correctly
        mock_context_service.retrieve_context.assert_called_once()
        call_args = mock_context_service.retrieve_context.call_args[0][0]
        assert call_args.query == "test query"
        assert call_args.source_channels == [SourceChannel.ROC]
        assert call_args.user_permission == UserPermission.BASIC
        assert call_args.top_k == 6  # 2 * 3

        # Verify reranker was called correctly
        mock_reranker_service.rerank.assert_called_once()
        rerank_args = mock_reranker_service.rerank.call_args
        assert rerank_args[1]["query"] == "test query"
        assert rerank_args[1]["documents"] == ["context 1", "context 2", "context 3"]
        assert rerank_args[1]["top_k"] == 2

        # Verify result
        assert result.query == "test query"
        assert len(result.contexts) == 2
        assert result.contexts[0]["text"] == "context 1"
        assert result.contexts[1]["text"] == "context 3"
        assert result.contexts[0]["score"] == 0.9
        assert result.contexts[1]["score"] == 0.7
        assert result.contexts[0]["rerank_score"] == 0.95
        assert result.contexts[1]["rerank_score"] == 0.85
        assert result.reranker_used == "cohere"
        assert result.total_retrieved == 3
        assert result.channels_searched == ["documentation"]

    @pytest.mark.asyncio
    async def test_retrieve_and_rerank_no_results(
        self, rag_service, mock_context_service, mock_reranker_service
    ):
        """Test RAG pipeline with no results from context retrieval"""
        # Mock empty context retrieval
        mock_context_response = ContextResponse(
            query="test query",
            results=[],
            channels_searched=[],
            total_results=0,
        )
        mock_context_service.retrieve_context.return_value = mock_context_response

        # Execute RAG pipeline
        result = await rag_service.retrieve_and_rerank(query="test query", top_k=5)

        # Verify context service was called
        mock_context_service.retrieve_context.assert_called_once()

        # Verify reranker was NOT called
        mock_reranker_service.rerank.assert_not_called()

        # Verify result
        assert result.query == "test query"
        assert len(result.contexts) == 0
        assert result.reranker_used == "none"
        assert result.total_retrieved == 0

    @pytest.mark.asyncio
    async def test_retrieve_and_rerank_default_channels(
        self, rag_service, mock_context_service, mock_reranker_service
    ):
        """Test RAG pipeline uses default channels when none provided"""
        # Mock context retrieval
        mock_context_response = ContextResponse(
            query="test query",
            results=[ContextItem(id="1", text="context 1", score=0.9)],
            channels_searched=[Channel.DOCUMENTATION],
            total_results=1,
        )
        mock_context_service.retrieve_context.return_value = mock_context_response

        # Mock reranking
        mock_reranker_service.rerank.return_value = (
            [RerankResult(text="context 1", relevance_score=0.95, index=0)],
            "cohere",
        )

        # Execute RAG pipeline without specifying channels
        result = await rag_service.retrieve_and_rerank(query="test query", top_k=1)

        # Verify default channel was used
        call_args = mock_context_service.retrieve_context.call_args[0][0]
        assert call_args.source_channels == [SourceChannel.ROC]

        # Verify result
        assert len(result.contexts) == 1

    @pytest.mark.asyncio
    async def test_retrieve_and_rerank_custom_initial_k(
        self, rag_service, mock_context_service, mock_reranker_service
    ):
        """Test RAG pipeline with custom initial retrieval count"""
        # Mock context retrieval
        mock_context_response = ContextResponse(
            query="test query",
            results=[ContextItem(id="1", text="context 1", score=0.9)],
            channels_searched=[Channel.DOCUMENTATION],
            total_results=1,
        )
        mock_context_service.retrieve_context.return_value = mock_context_response

        # Mock reranking
        mock_reranker_service.rerank.return_value = (
            [RerankResult(text="context 1", relevance_score=0.95, index=0)],
            "cohere",
        )

        # Execute RAG pipeline with custom initial_retrieval_k
        await rag_service.retrieve_and_rerank(
            query="test query", top_k=5, initial_retrieval_k=20
        )

        # Verify initial_retrieval_k was used
        call_args = mock_context_service.retrieve_context.call_args[0][0]
        assert call_args.top_k == 20

    @pytest.mark.asyncio
    async def test_retrieve_and_rerank_with_error(
        self, rag_service, mock_context_service
    ):
        """Test RAG pipeline handles errors properly"""
        # Mock context service to raise an error
        mock_context_service.retrieve_context.side_effect = Exception("Test error")

        # Execute RAG pipeline and expect exception
        with pytest.raises(Exception) as exc_info:
            await rag_service.retrieve_and_rerank(query="test query", top_k=5)

        assert "Test error" in str(exc_info.value)


class TestGetRAGService:
    """Tests for get_rag_service singleton"""

    def test_get_rag_service_returns_singleton(self):
        """Test that get_rag_service returns the same instance"""
        # Reset the global instance
        import app.services.search.rag_service as rag_module

        rag_module._rag_service = None

        # Get service twice
        service1 = get_rag_service()
        service2 = get_rag_service()

        # Verify they're the same instance
        assert service1 is service2
