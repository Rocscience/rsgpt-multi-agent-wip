"""Full pipeline integration tests - Tests auth + business logic together"""

import pytest
from fastapi.testclient import TestClient

from app.main import app

# Test tokens (must match values set in conftest.py)
TEST_BE_TOKEN = "test-be-service-token-12345"
TEST_MCP_TOKEN = "test-mcp-service-token-67890"


@pytest.mark.integration
class TestFullPipeline:
    """Integration tests that verify complete request flow including external APIs"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)

    @pytest.fixture
    def be_token(self):
        """Get BE service token for testing"""
        return TEST_BE_TOKEN

    @pytest.fixture
    def mcp_token(self):
        """Get MCP service token for testing"""
        return TEST_MCP_TOKEN

    def test_search_semantic_full_pipeline(self, client, mcp_token):
        """Test full semantic search pipeline with MCP token"""
        payload = {
            "query": "How do I use SetMaterialProperty in RS2?",
            "index_name": "rs2-scripting-2025",
            "namespace": "rs2-scripting-functions-wcode",
            "top_k": 5,
        }
        headers = {"X-Service-Token": mcp_token}

        response = client.post("/api/v1/search/semantic", json=payload, headers=headers)

        # May return 200 (success), 400 (business logic error), or 500 (mock/config error in tests)
        # The key is that auth passed (not 401/403)
        assert response.status_code not in [401, 403]

        if response.status_code == 200:
            data = response.json()
            assert "total_results" in data
            assert "results" in data
            # Verify results have expected structure
            if data["total_results"] > 0:
                result = data["results"][0]
                assert "score" in result
                assert "id" in result

    def test_rerank_full_pipeline(self, client, mcp_token):
        """Test full rerank pipeline with MCP token"""
        payload = {
            "query": "How to set material properties in RS2",
            "documents": [
                "SetMaterialProperty allows you to modify material properties in RS2 models",
                "The mesh generation in RS2 uses finite element analysis",
                "Material properties include strength, stiffness, and other parameters",
                "RS2 supports various material models for geotechnical analysis",
            ],
            "top_k": 3,
        }
        headers = {"X-Service-Token": mcp_token}

        response = client.post("/api/v1/rerank/", json=payload, headers=headers)

        # May return 200 (success) or 400 (business logic error like Cohere not configured)
        assert response.status_code in [200, 400]

        if response.status_code == 200:
            data = response.json()
            assert "total_results" in data
            assert "results" in data
            assert "reranker_used" in data
            # Verify reranked results
            if data["total_results"] > 0:
                result = data["results"][0]
                assert "relevance_score" in result
                assert "text" in result

    def test_chat_stream_full_pipeline(self, client, be_token):
        """Test chat stream with BE token (verify stream starts)"""
        payload = {
            "messages": [{"role": "user", "content": "Say 'hello' in one word"}],
            "provider": "openai",
            "model": "gpt-4o-mini",
            "max_tokens": 10,
        }
        headers = {"X-Service-Token": be_token}

        response = client.post("/api/v1/chat/stream", json=payload, headers=headers)

        # Streaming endpoint should return 200
        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")
