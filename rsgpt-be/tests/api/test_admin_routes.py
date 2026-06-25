"""Tests for Admin API routes"""

import pytest
from unittest.mock import Mock, patch
from uuid import uuid4
from fastapi.testclient import TestClient

from app.api.main import api_app
from app.dependencies import verify_admin_token


@pytest.fixture
def valid_admin_token():
    """Valid admin token for testing"""
    return "test-admin-token-12345"


@pytest.fixture
def client(valid_admin_token):
    """Create a test client with mocked admin authentication"""
    # Override the verify_admin_token dependency
    api_app.dependency_overrides[verify_admin_token] = lambda: True
    yield TestClient(api_app)
    api_app.dependency_overrides.clear()


@pytest.fixture
def unauthenticated_client():
    """Create a test client without authentication override"""
    api_app.dependency_overrides.clear()
    return TestClient(api_app)


@pytest.fixture
def mock_quota_requests():
    """Mock quota request data"""
    return [
        {
            "id": str(uuid4()),
            "user_id": str(uuid4()),
            "user_name": "John Doe",
            "user_email": "john@example.com",
            "current_quota": 10,
            "current_used": 8,
            "requested_quota": 20,
            "reason": "Need more quota for project work",
            "status": "pending",
            "created_at": "2024-01-15T10:00:00"
        },
        {
            "id": str(uuid4()),
            "user_id": str(uuid4()),
            "user_name": "Jane Smith",
            "user_email": "jane@example.com",
            "current_quota": 10,
            "current_used": 10,
            "requested_quota": 15,
            "reason": "Quota exhausted, need more for analysis",
            "status": "pending",
            "created_at": "2024-01-16T14:30:00"
        }
    ]


class TestListQuotaRequests:
    """Test cases for GET /admin/quota-requests endpoint"""

    def test_list_quota_requests_success(self, client, mock_quota_requests):
        """Test successful retrieval of quota requests"""
        with patch('app.api.routes.admin.get_pending_quota_requests_with_users') as mock_get:
            mock_get.return_value = mock_quota_requests

            response = client.get("/admin/quota-requests")

            assert response.status_code == 200
            data = response.json()
            assert "requests" in data
            assert "total" in data
            assert data["total"] == 2
            assert len(data["requests"]) == 2
            assert data["requests"][0]["user_name"] == "John Doe"
            assert data["requests"][1]["user_email"] == "jane@example.com"

    def test_list_quota_requests_empty(self, client):
        """Test retrieval when no pending requests exist"""
        with patch('app.api.routes.admin.get_pending_quota_requests_with_users') as mock_get:
            mock_get.return_value = []

            response = client.get("/admin/quota-requests")

            assert response.status_code == 200
            data = response.json()
            assert data["requests"] == []
            assert data["total"] == 0

    def test_list_quota_requests_database_error(self, client):
        """Test 500 when database error occurs"""
        with patch('app.api.routes.admin.get_pending_quota_requests_with_users') as mock_get:
            mock_get.side_effect = Exception("Database connection failed")

            response = client.get("/admin/quota-requests")

            assert response.status_code == 500
            data = response.json()
            assert "Failed to list quota requests" in data["detail"]

    def test_list_quota_requests_unauthenticated(self, unauthenticated_client):
        """Test that unauthenticated requests are rejected"""
        response = unauthenticated_client.get("/admin/quota-requests")
        
        # Should return 401 or 422 (missing required header)
        assert response.status_code in [401, 422]


class TestApproveQuotaRequest:
    """Test cases for POST /admin/quota-requests/{id}/approve endpoint"""

    def test_approve_request_success(self, client):
        """Test successful approval of quota request"""
        request_id = uuid4()
        
        with patch('app.api.routes.admin.approve_quota_request') as mock_approve:
            mock_approve.return_value = {
                "id": str(request_id),
                "status": "approved",
                "user_id": str(uuid4()),
                "new_quota": 30
            }

            response = client.post(f"/admin/quota-requests/{request_id}/approve")

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["message"] == "Quota request approved successfully"
            assert data["status"] == "approved"
            assert data["new_quota"] == 30

    def test_approve_request_not_found(self, client):
        """Test 400 when request not found"""
        request_id = uuid4()
        
        with patch('app.api.routes.admin.approve_quota_request') as mock_approve:
            mock_approve.side_effect = ValueError(f"Quota request not found: {request_id}")

            response = client.post(f"/admin/quota-requests/{request_id}/approve")

            assert response.status_code == 400
            data = response.json()
            assert "not found" in data["detail"]

    def test_approve_request_not_pending(self, client):
        """Test 400 when request is not in pending status"""
        request_id = uuid4()
        
        with patch('app.api.routes.admin.approve_quota_request') as mock_approve:
            mock_approve.side_effect = ValueError("Quota request is not pending: approved")

            response = client.post(f"/admin/quota-requests/{request_id}/approve")

            assert response.status_code == 400
            data = response.json()
            assert "not pending" in data["detail"]

    def test_approve_request_database_error(self, client):
        """Test 500 when database error occurs"""
        request_id = uuid4()
        
        with patch('app.api.routes.admin.approve_quota_request') as mock_approve:
            mock_approve.side_effect = Exception("Database error")

            response = client.post(f"/admin/quota-requests/{request_id}/approve")

            assert response.status_code == 500
            data = response.json()
            assert "Failed to approve quota request" in data["detail"]

    def test_approve_request_invalid_uuid(self, client):
        """Test 422 when invalid UUID is provided"""
        response = client.post("/admin/quota-requests/invalid-uuid/approve")
        
        assert response.status_code == 422

    def test_approve_request_unauthenticated(self, unauthenticated_client):
        """Test that unauthenticated requests are rejected"""
        request_id = uuid4()
        response = unauthenticated_client.post(f"/admin/quota-requests/{request_id}/approve")
        
        assert response.status_code in [401, 422]


class TestDenyQuotaRequest:
    """Test cases for POST /admin/quota-requests/{id}/deny endpoint"""

    def test_deny_request_success(self, client):
        """Test successful denial of quota request"""
        request_id = uuid4()
        user_id = uuid4()
        
        with patch('app.api.routes.admin.deny_quota_request') as mock_deny:
            mock_deny.return_value = {
                "id": str(request_id),
                "status": "denied",
                "user_id": str(user_id)
            }

            response = client.post(f"/admin/quota-requests/{request_id}/deny")

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["message"] == "Quota request denied"
            assert data["status"] == "denied"

    def test_deny_request_not_found(self, client):
        """Test 400 when request not found"""
        request_id = uuid4()
        
        with patch('app.api.routes.admin.deny_quota_request') as mock_deny:
            mock_deny.side_effect = ValueError(f"Quota request not found: {request_id}")

            response = client.post(f"/admin/quota-requests/{request_id}/deny")

            assert response.status_code == 400
            data = response.json()
            assert "not found" in data["detail"]

    def test_deny_request_not_pending(self, client):
        """Test 400 when request is not in pending status"""
        request_id = uuid4()
        
        with patch('app.api.routes.admin.deny_quota_request') as mock_deny:
            mock_deny.side_effect = ValueError("Quota request is not pending: denied")

            response = client.post(f"/admin/quota-requests/{request_id}/deny")

            assert response.status_code == 400
            data = response.json()
            assert "not pending" in data["detail"]

    def test_deny_request_database_error(self, client):
        """Test 500 when database error occurs"""
        request_id = uuid4()
        
        with patch('app.api.routes.admin.deny_quota_request') as mock_deny:
            mock_deny.side_effect = Exception("Database error")

            response = client.post(f"/admin/quota-requests/{request_id}/deny")

            assert response.status_code == 500
            data = response.json()
            assert "Failed to deny quota request" in data["detail"]

    def test_deny_request_invalid_uuid(self, client):
        """Test 422 when invalid UUID is provided"""
        response = client.post("/admin/quota-requests/invalid-uuid/deny")
        
        assert response.status_code == 422

    def test_deny_request_unauthenticated(self, unauthenticated_client):
        """Test that unauthenticated requests are rejected"""
        request_id = uuid4()
        response = unauthenticated_client.post(f"/admin/quota-requests/{request_id}/deny")
        
        assert response.status_code in [401, 422]


class TestAdminTokenVerification:
    """Test cases for admin token verification"""

    def test_valid_admin_token(self):
        """Test that valid admin token is accepted"""
        with patch('app.config.settings') as mock_settings:
            mock_settings.admin_api_token = "valid-token-12345"
            
            # Create client with real verify_admin_token
            api_app.dependency_overrides.clear()
            client = TestClient(api_app)
            
            with patch('app.api.routes.admin.get_pending_quota_requests_with_users') as mock_get:
                mock_get.return_value = []
                
                response = client.get(
                    "/admin/quota-requests",
                    headers={"X-Admin-Token": "valid-token-12345"}
                )
                
                # Should succeed with valid token
                assert response.status_code == 200

    def test_invalid_admin_token(self):
        """Test that invalid admin token is rejected"""
        with patch('app.config.settings') as mock_settings:
            mock_settings.admin_api_token = "valid-token-12345"
            
            api_app.dependency_overrides.clear()
            client = TestClient(api_app)
            
            response = client.get(
                "/admin/quota-requests",
                headers={"X-Admin-Token": "wrong-token"}
            )
            
            assert response.status_code == 401

    def test_missing_admin_token_config(self):
        """Test 500 when admin token is not configured"""
        with patch('app.config.settings') as mock_settings:
            mock_settings.admin_api_token = ""
            
            api_app.dependency_overrides.clear()
            client = TestClient(api_app)
            
            response = client.get(
                "/admin/quota-requests",
                headers={"X-Admin-Token": "any-token"}
            )
            
            assert response.status_code == 500
