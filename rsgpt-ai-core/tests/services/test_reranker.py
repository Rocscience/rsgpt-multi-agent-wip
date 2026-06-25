"""Unit tests for reranker services"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.rerank import RerankResult
from app.services.reranker import CohereReranker, KeepTopKReranker, RerankerService


class TestCohereReranker:
    """Test Cohere reranker implementation"""

    @pytest.mark.asyncio
    @patch("app.services.reranker.cohere_reranker.ClientV2")
    async def test_rerank_correct_ordering(self, mock_client_class):
        """Test that Cohere reranker returns correctly ordered results"""
        # Mock Cohere SDK response
        mock_result_1 = MagicMock()
        mock_result_1.index = 2
        mock_result_1.relevance_score = 0.95

        mock_result_2 = MagicMock()
        mock_result_2.index = 0
        mock_result_2.relevance_score = 0.85

        mock_result_3 = MagicMock()
        mock_result_3.index = 1
        mock_result_3.relevance_score = 0.75

        mock_response = MagicMock()
        mock_response.results = [mock_result_1, mock_result_2, mock_result_3]

        mock_client = MagicMock()
        mock_client.rerank.return_value = mock_response
        mock_client_class.return_value = mock_client

        # Test documents
        documents = ["Doc A", "Doc B", "Doc C"]
        query = "test query"

        reranker = CohereReranker(api_key="test-key")
        results = await reranker.rerank(query, documents, top_k=3)

        # Verify ordering (highest relevance first)
        assert len(results) == 3
        assert results[0].text == "Doc C"
        assert results[0].relevance_score == 0.95
        assert results[1].text == "Doc A"
        assert results[1].relevance_score == 0.85
        assert results[2].text == "Doc B"
        assert results[2].relevance_score == 0.75

    @pytest.mark.asyncio
    async def test_rerank_empty_documents(self):
        """Test that empty documents list is handled gracefully"""
        reranker = CohereReranker(api_key="test-key")
        results = await reranker.rerank("query", [], top_k=5)

        assert results == []

    @pytest.mark.asyncio
    async def test_rerank_no_api_key(self):
        """Test that missing API key raises ValueError"""
        reranker = CohereReranker(api_key="")

        with pytest.raises(ValueError, match="Cohere API key is not configured"):
            await reranker.rerank("query", ["doc1", "doc2"])

    @pytest.mark.asyncio
    @patch("app.services.reranker.cohere_reranker.ClientV2")
    async def test_rerank_api_failure(self, mock_client_class):
        """Test that API failures are properly handled"""
        # Mock API error
        mock_client = MagicMock()
        mock_client.rerank.side_effect = Exception("API Error")
        mock_client_class.return_value = mock_client

        reranker = CohereReranker(api_key="test-key")

        with pytest.raises(Exception):
            await reranker.rerank("query", ["doc1", "doc2"])


class TestKeepTopKReranker:
    """Test KeepTopK backup reranker"""

    @pytest.mark.asyncio
    async def test_rerank_returns_original_order(self):
        """Test that KeepTopK returns documents in original order"""
        documents = ["First", "Second", "Third", "Fourth"]
        reranker = KeepTopKReranker()

        results = await reranker.rerank("query", documents, top_k=3)

        assert len(results) == 3
        assert results[0].text == "First"
        assert results[0].index == 0
        assert results[1].text == "Second"
        assert results[1].index == 1
        assert results[2].text == "Third"
        assert results[2].index == 2

    @pytest.mark.asyncio
    async def test_rerank_all_documents(self):
        """Test that KeepTopK returns all documents when top_k is None"""
        documents = ["Doc1", "Doc2", "Doc3"]
        reranker = KeepTopKReranker()

        results = await reranker.rerank("query", documents, top_k=None)

        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_rerank_empty_documents(self):
        """Test that empty documents list is handled gracefully"""
        reranker = KeepTopKReranker()
        results = await reranker.rerank("query", [])

        assert results == []

    @pytest.mark.asyncio
    async def test_rerank_scores_decrease(self):
        """Test that relevance scores decrease monotonically"""
        documents = ["Doc1", "Doc2", "Doc3", "Doc4"]
        reranker = KeepTopKReranker()

        results = await reranker.rerank("query", documents)

        # Scores should decrease
        for i in range(len(results) - 1):
            assert results[i].relevance_score > results[i + 1].relevance_score


class TestRerankerService:
    """Test unified reranker service with fallback"""

    @pytest.mark.asyncio
    @patch("app.services.reranker.reranker_service.get_cohere_reranker")
    async def test_uses_cohere_when_available(self, mock_get_cohere):
        """Test that service uses Cohere when available"""
        # Mock Cohere reranker
        mock_cohere = AsyncMock()
        mock_cohere.rerank.return_value = [
            RerankResult(text="Doc1", index=0, relevance_score=0.9)
        ]
        mock_get_cohere.return_value = mock_cohere

        service = RerankerService()
        results, reranker_used = await service.rerank("query", ["Doc1", "Doc2"])

        assert reranker_used == "cohere"
        assert len(results) == 1
        mock_cohere.rerank.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.services.reranker.reranker_service.get_cohere_reranker")
    @patch("app.services.reranker.reranker_service.get_keep_topk_reranker")
    async def test_fallback_to_backup_on_error(self, mock_get_backup, mock_get_cohere):
        """Test that service falls back to backup on Cohere failure"""
        # Mock Cohere to fail
        mock_cohere = AsyncMock()
        mock_cohere.rerank.side_effect = Exception("API Error")
        mock_get_cohere.return_value = mock_cohere

        # Mock backup reranker
        mock_backup = AsyncMock()
        mock_backup.rerank.return_value = [
            RerankResult(text="Doc1", index=0, relevance_score=1.0)
        ]
        mock_get_backup.return_value = mock_backup

        service = RerankerService()
        results, reranker_used = await service.rerank("query", ["Doc1", "Doc2"])

        assert reranker_used == "backup"
        assert len(results) == 1
        mock_backup.rerank.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.services.reranker.reranker_service.get_cohere_reranker")
    @patch("app.services.reranker.reranker_service.get_keep_topk_reranker")
    async def test_fallback_on_missing_api_key(self, mock_get_backup, mock_get_cohere):
        """Test that service falls back when Cohere API key is missing"""
        # Mock Cohere to raise ValueError (no API key)
        mock_cohere = AsyncMock()
        mock_cohere.rerank.side_effect = ValueError("API key not configured")
        mock_get_cohere.return_value = mock_cohere

        # Mock backup reranker
        mock_backup = AsyncMock()
        mock_backup.rerank.return_value = [
            RerankResult(text="Doc1", index=0, relevance_score=1.0)
        ]
        mock_get_backup.return_value = mock_backup

        service = RerankerService()
        results, reranker_used = await service.rerank("query", ["Doc1"])

        assert reranker_used == "backup"
        mock_backup.rerank.assert_called_once()

    @pytest.mark.asyncio
    async def test_empty_documents_handled(self):
        """Test that empty documents list is handled gracefully"""
        service = RerankerService()
        results, reranker_used = await service.rerank("query", [])

        assert results == []
        assert reranker_used == "none"
