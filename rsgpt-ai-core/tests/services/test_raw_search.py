"""Unit tests for raw semantic search functionality"""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.models.context import (
    RawSearchResultItem,
    RawSemanticSearchRequest,
    RawSemanticSearchResponse,
)
from app.services.search import ContextService


class TestPineconeServiceRawSearch:
    """Test PineconeService raw search functionality"""

    @pytest.fixture
    def mock_pinecone_service(self):
        """Create a mock pinecone service"""
        with patch(
            "app.services.search.pinecone_service.Pinecone"
        ) as mock_pinecone, patch(
            "app.services.search.pinecone_service.settings"
        ) as mock_settings:
            from app.services.search import PineconeService

            # Mock settings
            mock_settings.pinecone_api_key = "test-api-key"
            mock_settings.pinecone_default_top_k = 10
            mock_settings.pinecone_index_name = "test-index"

            # Mock the index
            mock_index = Mock()
            mock_pinecone.return_value.Index.return_value = mock_index
            mock_pinecone.return_value.list_indexes.return_value.indexes = [
                {"name": "test-index"}
            ]

            service = PineconeService()
            service._indexes = {"test-index": mock_index}

            yield service, mock_index

    @pytest.mark.asyncio
    async def test_raw_search_success(self, mock_pinecone_service):
        """Test successful raw search"""
        service, mock_index = mock_pinecone_service

        # Mock Pinecone response with arbitrary metadata
        mock_index.query.return_value = Mock(
            matches=[
                {
                    "id": "doc1",
                    "score": 0.95,
                    "metadata": {
                        "custom_field": "value1",
                        "content": "Some content",
                        "arbitrary_data": {"nested": "data"},
                    },
                },
                {
                    "id": "doc2",
                    "score": 0.87,
                    "metadata": {
                        "custom_field": "value2",
                        "content": "Other content",
                    },
                },
            ]
        )

        query_vector = [0.1] * 1536
        results = await service.raw_search(
            query_vector=query_vector,
            index_name="test-index",
            namespace="test-namespace",
            top_k=10,
        )

        # Verify results
        assert len(results) == 2
        assert isinstance(results[0], RawSearchResultItem)
        assert results[0].id == "doc1"
        assert results[0].score == 0.95
        assert results[0].metadata["custom_field"] == "value1"
        assert results[0].metadata["arbitrary_data"]["nested"] == "data"

        # Verify Pinecone was called correctly
        mock_index.query.assert_called_once_with(
            vector=query_vector,
            top_k=10,
            include_metadata=True,
            namespace="test-namespace",
        )

    @pytest.mark.asyncio
    async def test_raw_search_empty_results(self, mock_pinecone_service):
        """Test raw search with no results"""
        service, mock_index = mock_pinecone_service

        mock_index.query.return_value = Mock(matches=[])

        query_vector = [0.1] * 1536
        results = await service.raw_search(
            query_vector=query_vector,
            index_name="test-index",
            namespace="test-namespace",
            top_k=5,
        )

        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_raw_search_with_empty_metadata(self, mock_pinecone_service):
        """Test raw search handles empty metadata gracefully"""
        service, mock_index = mock_pinecone_service

        mock_index.query.return_value = Mock(
            matches=[
                {"id": "doc1", "score": 0.95, "metadata": {}},
                {"id": "doc2", "score": 0.87},  # Missing metadata
            ]
        )

        query_vector = [0.1] * 1536
        results = await service.raw_search(
            query_vector=query_vector,
            index_name="test-index",
            namespace="test-namespace",
            top_k=10,
        )

        assert len(results) == 2
        assert results[0].metadata == {}
        assert results[1].metadata == {}

    @pytest.mark.asyncio
    async def test_raw_search_invalid_index(self, mock_pinecone_service):
        """Test raw search with invalid index name"""
        service, _ = mock_pinecone_service

        # Mock the list_indexes to not include the requested index
        with patch.object(service.client, "list_indexes") as mock_list:
            mock_list.return_value = Mock(indexes=[{"name": "other-index"}])

            with pytest.raises(ValueError, match="does not exist"):
                await service.raw_search(
                    query_vector=[0.1] * 1536,
                    index_name="nonexistent-index",
                    namespace="test-namespace",
                    top_k=10,
                )

    @pytest.mark.asyncio
    async def test_raw_search_pinecone_error(self, mock_pinecone_service):
        """Test raw search handles Pinecone errors"""
        service, mock_index = mock_pinecone_service

        mock_index.query.side_effect = Exception("Pinecone API error")

        with pytest.raises(Exception, match="Pinecone API error"):
            await service.raw_search(
                query_vector=[0.1] * 1536,
                index_name="test-index",
                namespace="test-namespace",
                top_k=10,
            )


class TestContextServiceRawSemanticSearch:
    """Test ContextService raw semantic search functionality"""

    @pytest.fixture
    def mock_context_service(self):
        """Create a mock context service with dependencies"""
        with patch(
            "app.services.search.context_service.get_embedding_service"
        ) as mock_embedding, patch(
            "app.services.search.context_service.get_pinecone_service"
        ) as mock_pinecone, patch(
            "app.services.search.context_service.get_conductor_service"
        ):
            mock_embedding_service = Mock()
            mock_pinecone_service = Mock()

            mock_embedding.return_value = mock_embedding_service
            mock_pinecone.return_value = mock_pinecone_service

            service = ContextService()

            yield service, mock_embedding_service, mock_pinecone_service

    @pytest.mark.asyncio
    async def test_raw_semantic_search_success(self, mock_context_service):
        """Test successful raw semantic search"""
        service, mock_embedding_service, mock_pinecone_service = mock_context_service

        # Mock embedding generation
        mock_embedding_service.embed_text = AsyncMock(return_value=[0.1] * 1536)

        # Mock Pinecone raw search
        mock_results = [
            RawSearchResultItem(
                id="result1",
                score=0.95,
                metadata={"field1": "value1", "field2": "value2"},
            ),
            RawSearchResultItem(
                id="result2",
                score=0.87,
                metadata={"field1": "value3", "field2": "value4"},
            ),
        ]
        mock_pinecone_service.raw_search = AsyncMock(return_value=mock_results)

        # Create request
        request = RawSemanticSearchRequest(
            query="test query",
            namespace="custom-namespace",
            index_name="custom-index",
            top_k=10,
        )

        # Execute
        response = await service.raw_semantic_search(request)

        # Verify response
        assert isinstance(response, RawSemanticSearchResponse)
        assert response.query == "test query"
        assert response.namespace == "custom-namespace"
        assert response.index_name == "custom-index"
        assert response.total_results == 2
        assert len(response.results) == 2
        assert response.results[0].id == "result1"
        assert response.results[0].score == 0.95

        # Verify dependencies were called correctly
        mock_embedding_service.embed_text.assert_called_once_with("test query")
        mock_pinecone_service.raw_search.assert_called_once_with(
            query_vector=[0.1] * 1536,
            index_name="custom-index",
            namespace="custom-namespace",
            top_k=10,
        )

    @pytest.mark.asyncio
    async def test_raw_semantic_search_empty_results(self, mock_context_service):
        """Test raw semantic search with no results"""
        service, mock_embedding_service, mock_pinecone_service = mock_context_service

        mock_embedding_service.embed_text = AsyncMock(return_value=[0.1] * 1536)
        mock_pinecone_service.raw_search = AsyncMock(return_value=[])

        request = RawSemanticSearchRequest(
            query="no results query",
            namespace="empty-namespace",
            index_name="test-index",
            top_k=5,
        )

        response = await service.raw_semantic_search(request)

        assert response.total_results == 0
        assert len(response.results) == 0

    @pytest.mark.asyncio
    async def test_raw_semantic_search_embedding_failure(self, mock_context_service):
        """Test raw semantic search handles embedding generation failure"""
        service, mock_embedding_service, _ = mock_context_service

        mock_embedding_service.embed_text = AsyncMock(
            side_effect=Exception("Embedding service error")
        )

        request = RawSemanticSearchRequest(
            query="test query",
            namespace="test-namespace",
            index_name="test-index",
            top_k=10,
        )

        with pytest.raises(Exception, match="Embedding service error"):
            await service.raw_semantic_search(request)

    @pytest.mark.asyncio
    async def test_raw_semantic_search_pinecone_failure(self, mock_context_service):
        """Test raw semantic search handles Pinecone search failure"""
        service, mock_embedding_service, mock_pinecone_service = mock_context_service

        mock_embedding_service.embed_text = AsyncMock(return_value=[0.1] * 1536)
        mock_pinecone_service.raw_search = AsyncMock(
            side_effect=Exception("Pinecone search error")
        )

        request = RawSemanticSearchRequest(
            query="test query",
            namespace="test-namespace",
            index_name="test-index",
            top_k=10,
        )

        with pytest.raises(Exception, match="Pinecone search error"):
            await service.raw_semantic_search(request)

    @pytest.mark.asyncio
    async def test_raw_semantic_search_with_special_characters(
        self, mock_context_service
    ):
        """Test raw semantic search handles queries with special characters"""
        service, mock_embedding_service, mock_pinecone_service = mock_context_service

        mock_embedding_service.embed_text = AsyncMock(return_value=[0.1] * 1536)
        mock_pinecone_service.raw_search = AsyncMock(return_value=[])

        request = RawSemanticSearchRequest(
            query="special!@#$%^&*()characters",
            namespace="test-namespace",
            index_name="test-index",
            top_k=10,
        )

        response = await service.raw_semantic_search(request)

        assert response.query == "special!@#$%^&*()characters"
        mock_embedding_service.embed_text.assert_called_once_with(
            "special!@#$%^&*()characters"
        )


class TestRawSearchIntegration:
    """Integration tests for raw search functionality"""

    @pytest.mark.asyncio
    async def test_process_raw_search_results(self):
        """Test processing of raw Pinecone results"""
        from app.services.search import PineconeService

        with patch("app.services.search.pinecone_service.Pinecone"), patch(
            "app.services.search.pinecone_service.settings"
        ) as mock_settings:
            mock_settings.pinecone_api_key = "test-api-key"
            mock_settings.pinecone_default_top_k = 10

            service = PineconeService()

            # Test with various metadata structures
            matches = [
                {
                    "id": "id1",
                    "score": 0.95,
                    "metadata": {
                        "text": "content",
                        "extra_field": "value",
                        "nested": {"key": "value"},
                    },
                },
                {
                    "id": "id2",
                    "score": 0.87,
                    "metadata": {"completely": "different", "structure": [1, 2, 3]},
                },
                {"id": "id3", "score": 0.75, "metadata": {}},
            ]

            results = service._process_raw_search_results(matches)

            assert len(results) == 3
            assert results[0].id == "id1"
            assert results[0].score == 0.95
            assert "text" in results[0].metadata
            assert "nested" in results[0].metadata

            assert results[1].metadata["structure"] == [1, 2, 3]
            assert results[2].metadata == {}
