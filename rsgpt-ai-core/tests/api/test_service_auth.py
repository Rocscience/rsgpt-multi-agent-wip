"""Tests for service authentication and token scoping"""

import pytest
from fastapi.testclient import TestClient

from app.main import app

# Test tokens (must match values set in conftest.py)
TEST_BE_TOKEN = "test-be-service-token-12345"
# Unified MCP token for all MCP servers (RS2, RSPile, etc.)
TEST_MCP_TOKEN = "test-mcp-service-token-67890"


class TestServiceAuthentication:
    """Test service-to-service authentication with token scoping"""

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
        """Get unified MCP service token for testing (RS2, RSPile, etc.)"""
        return TEST_MCP_TOKEN

    def get_test_payload(self, endpoint: str):
        """Get appropriate test payload for each endpoint"""
        if endpoint == "/chat/stream":
            return {
                "messages": [{"role": "user", "content": "test"}],
                "provider": "openai",
                "model": "gpt-4o-mini",
            }
        elif endpoint == "/agent/stream":
            return {
                "messages": [{"role": "user", "content": "test"}],
                "model": "gpt-4o-mini",
            }
        elif endpoint == "/search/semantic":
            return {
                "query": "How do I use SetMaterialProperty in RS2?",
                "index_name": "rs2-scripting-2025",
                "namespace": "rs2-scripting-functions-wcode",
                "top_k": 5,
            }
        elif endpoint == "/rerank/":
            return {
                "query": "How to set material properties in RS2",
                "documents": [
                    "SetMaterialProperty allows you to modify material properties in RS2 models",
                    "The mesh generation in RS2 uses finite element analysis",
                    "Material properties include strength, stiffness, and other parameters",
                    "RS2 supports various material models for geotechnical analysis",
                ],
                "top_k": 3,
            }
        return {}

    # BE Token Tests - Should access chat and agent only
    def test_be_token_chat_allowed(self, client, be_token):
        """BE token should access /chat/stream"""
        headers = {"X-Service-Token": be_token}
        payload = self.get_test_payload("/chat/stream")
        response = client.post("/api/v1/chat/stream", json=payload, headers=headers)
        assert response.status_code == 200

    @pytest.mark.skip(reason="Integration test requires full agent setup with API keys")
    def test_be_token_agent_allowed(self, client, be_token):
        """BE token should access /agent/stream"""
        headers = {"X-Service-Token": be_token}
        payload = self.get_test_payload("/agent/stream")
        response = client.post("/api/v1/agent/stream", json=payload, headers=headers)
        assert response.status_code == 200

    def test_be_token_search_blocked(self, client, be_token):
        """BE token should NOT access /search/semantic"""
        headers = {"X-Service-Token": be_token}
        payload = self.get_test_payload("/search/semantic")
        response = client.post("/api/v1/search/semantic", json=payload, headers=headers)
        assert response.status_code == 403
        assert "not authorized" in response.json()["detail"].lower()

    def test_be_token_rerank_blocked(self, client, be_token):
        """BE token should NOT access /rerank/"""
        headers = {"X-Service-Token": be_token}
        payload = self.get_test_payload("/rerank/")
        response = client.post("/api/v1/rerank/", json=payload, headers=headers)
        assert response.status_code == 403
        assert "not authorized" in response.json()["detail"].lower()

    # MCP Token Tests - Should access search and rerank only
    def test_mcp_token_search_allowed(self, client, mcp_token):
        """MCP token should access /search/semantic"""
        headers = {"X-Service-Token": mcp_token}
        payload = self.get_test_payload("/search/semantic")
        response = client.post("/api/v1/search/semantic", json=payload, headers=headers)
        # May return 200 (success), 400 (business logic error), or 500 (mock/config error in tests)
        # The key is that auth passed (not 401/403)
        assert response.status_code not in [401, 403]

    def test_mcp_token_rerank_allowed(self, client, mcp_token):
        """MCP token should access /rerank/"""
        headers = {"X-Service-Token": mcp_token}
        payload = self.get_test_payload("/rerank/")
        response = client.post("/api/v1/rerank/", json=payload, headers=headers)
        # May return 200 (success) or 400 (business logic error, but auth passed)
        assert response.status_code in [200, 400]

    def test_mcp_token_chat_blocked(self, client, mcp_token):
        """MCP token should NOT access /chat/stream (verify_be_auth requires BE token)"""
        headers = {"X-Service-Token": mcp_token}
        payload = self.get_test_payload("/chat/stream")
        response = client.post("/api/v1/chat/stream", json=payload, headers=headers)
        # verify_be_auth treats non-BE tokens as unauthorized (401), not forbidden (403)
        assert response.status_code == 401
        assert "invalid" in response.json()["detail"].lower() or "unauthorized" in response.json()["detail"].lower()

    def test_mcp_token_agent_blocked(self, client, mcp_token):
        """MCP token should NOT access /agent/stream (verify_be_auth requires BE token)"""
        headers = {"X-Service-Token": mcp_token}
        payload = self.get_test_payload("/agent/stream")
        response = client.post("/api/v1/agent/stream", json=payload, headers=headers)
        # verify_be_auth treats non-BE tokens as unauthorized (401), not forbidden (403)
        assert response.status_code == 401
        assert "invalid" in response.json()["detail"].lower() or "unauthorized" in response.json()["detail"].lower()

    # Invalid Token Tests
    def test_invalid_token_chat_rejected(self, client):
        """Invalid token should be rejected on /chat/stream"""
        headers = {"X-Service-Token": "invalid-token"}
        payload = self.get_test_payload("/chat/stream")
        response = client.post("/api/v1/chat/stream", json=payload, headers=headers)
        assert response.status_code == 401
        assert "invalid" in response.json()["detail"].lower()

    def test_invalid_token_agent_rejected(self, client):
        """Invalid token should be rejected on /agent/stream"""
        headers = {"X-Service-Token": "invalid-token"}
        payload = self.get_test_payload("/agent/stream")
        response = client.post("/api/v1/agent/stream", json=payload, headers=headers)
        assert response.status_code == 401
        assert "invalid" in response.json()["detail"].lower()

    def test_invalid_token_search_rejected(self, client):
        """Invalid token should be rejected on /search/semantic"""
        headers = {"X-Service-Token": "invalid-token"}
        payload = self.get_test_payload("/search/semantic")
        response = client.post("/api/v1/search/semantic", json=payload, headers=headers)
        assert response.status_code == 401
        assert "invalid" in response.json()["detail"].lower()

    def test_invalid_token_rerank_rejected(self, client):
        """Invalid token should be rejected on /rerank/"""
        headers = {"X-Service-Token": "invalid-token"}
        payload = self.get_test_payload("/rerank/")
        response = client.post("/api/v1/rerank/", json=payload, headers=headers)
        assert response.status_code == 401
        assert "invalid" in response.json()["detail"].lower()

    # No Token Tests
    def test_no_token_chat_rejected(self, client):
        """Missing token should be rejected on /chat/stream"""
        payload = self.get_test_payload("/chat/stream")
        response = client.post("/api/v1/chat/stream", json=payload)
        # verify_be_auth returns 401 for missing token, may return 400 for validation errors
        assert response.status_code in [400, 401]

    def test_no_token_agent_rejected(self, client):
        """Missing token should be rejected on /agent/stream"""
        payload = self.get_test_payload("/agent/stream")
        response = client.post("/api/v1/agent/stream", json=payload)
        # verify_be_auth returns 401 for missing token, may return 400 for validation errors
        assert response.status_code in [400, 401]

    def test_no_token_search_rejected(self, client):
        """Missing token should be rejected on /search/semantic"""
        payload = self.get_test_payload("/search/semantic")
        response = client.post("/api/v1/search/semantic", json=payload)
        assert response.status_code == 401
        assert "missing" in response.json()["detail"].lower()

    def test_no_token_rerank_rejected(self, client):
        """Missing token should be rejected on /rerank/"""
        payload = self.get_test_payload("/rerank/")
        response = client.post("/api/v1/rerank/", json=payload)
        assert response.status_code == 401
        assert "missing" in response.json()["detail"].lower()
