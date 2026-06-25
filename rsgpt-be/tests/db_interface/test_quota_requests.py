"""Tests for app.db_interface.quota_requests module"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from uuid import uuid4
from datetime import datetime

from app.db_interface.quota_requests import (
    create_quota_request,
    get_quota_requests_by_user_id,
    get_pending_quota_requests,
    get_pending_quota_requests_with_users,
    get_quota_request_by_id,
    approve_quota_request,
    deny_quota_request
)
from app.db_models.quota_requests import QuotaRequestsORM, QuotaRequestStatus
from app.db_models.users import UsersORM


class TestCreateQuotaRequest:
    """Test cases for create_quota_request function"""

    def test_create_quota_request_success(self):
        """Test successful creation of quota request"""
        user_id = uuid4()
        requested_quota = 20
        reason = "Need more quota for project work"
        
        with patch('app.db_interface.quota_requests.Session') as mock_session_class:
            mock_session_instance = mock_session_class.return_value.__enter__.return_value
            mock_session_instance.add = Mock()
            mock_session_instance.commit = Mock()
            mock_session_instance.refresh = Mock()
            mock_session_instance.expunge = Mock()
            
            result = create_quota_request(user_id, requested_quota, reason)
            
            mock_session_instance.add.assert_called_once()
            mock_session_instance.commit.assert_called_once()
            mock_session_instance.refresh.assert_called_once()
            mock_session_instance.expunge.assert_called_once()
            
            # Verify the created request has correct attributes
            added_request = mock_session_instance.add.call_args[0][0]
            assert isinstance(added_request, QuotaRequestsORM)
            assert added_request.user_id == user_id
            assert added_request.requested_quota == requested_quota
            assert added_request.reason == reason
            assert added_request.status == QuotaRequestStatus.PENDING.value

    def test_create_quota_request_database_error(self):
        """Test quota request creation with database error"""
        user_id = uuid4()
        
        with patch('app.db_interface.quota_requests.Session') as mock_session_class:
            mock_session_instance = mock_session_class.return_value.__enter__.return_value
            mock_session_instance.add.side_effect = Exception("Database error")
            
            with pytest.raises(Exception) as exc_info:
                create_quota_request(user_id, 10, "test reason")
            
            assert str(exc_info.value) == "Database error"

    @patch('app.db_interface.quota_requests.logger')
    def test_create_quota_request_logs_info(self, mock_logger):
        """Test that quota request creation logs appropriate messages"""
        user_id = uuid4()
        
        with patch('app.db_interface.quota_requests.Session') as mock_session_class:
            mock_session_instance = mock_session_class.return_value.__enter__.return_value
            mock_session_instance.add = Mock()
            mock_session_instance.commit = Mock()
            mock_session_instance.refresh = Mock()
            mock_session_instance.expunge = Mock()
            
            create_quota_request(user_id, 15, "Test reason")
            
            assert mock_logger.info.call_count >= 1


class TestGetQuotaRequestsByUserId:
    """Test cases for get_quota_requests_by_user_id function"""

    def test_get_quota_requests_success(self):
        """Test successful retrieval of quota requests for a user"""
        user_id = uuid4()
        mock_requests = [
            QuotaRequestsORM(id=uuid4(), user_id=user_id, requested_quota=10, reason="Reason 1", status="pending"),
            QuotaRequestsORM(id=uuid4(), user_id=user_id, requested_quota=20, reason="Reason 2", status="approved"),
        ]
        
        with patch('app.db_interface.quota_requests.Session') as mock_session_class:
            mock_session_instance = mock_session_class.return_value.__enter__.return_value
            mock_query = mock_session_instance.query.return_value
            mock_filter = mock_query.filter.return_value
            mock_order = mock_filter.order_by.return_value
            mock_order.all.return_value = mock_requests
            
            result = get_quota_requests_by_user_id(user_id)
            
            assert result == mock_requests
            assert len(result) == 2

    def test_get_quota_requests_empty(self):
        """Test retrieval when user has no quota requests"""
        user_id = uuid4()
        
        with patch('app.db_interface.quota_requests.Session') as mock_session_class:
            mock_session_instance = mock_session_class.return_value.__enter__.return_value
            mock_query = mock_session_instance.query.return_value
            mock_filter = mock_query.filter.return_value
            mock_order = mock_filter.order_by.return_value
            mock_order.all.return_value = []
            
            result = get_quota_requests_by_user_id(user_id)
            
            assert result == []

    def test_get_quota_requests_database_error(self):
        """Test retrieval with database error"""
        user_id = uuid4()
        
        with patch('app.db_interface.quota_requests.Session') as mock_session_class:
            mock_session_instance = mock_session_class.return_value.__enter__.return_value
            mock_session_instance.query.side_effect = Exception("Database error")
            
            with pytest.raises(Exception) as exc_info:
                get_quota_requests_by_user_id(user_id)
            
            assert str(exc_info.value) == "Database error"


class TestGetPendingQuotaRequests:
    """Test cases for get_pending_quota_requests function"""

    def test_get_pending_requests_success(self):
        """Test successful retrieval of pending quota requests"""
        mock_requests = [
            QuotaRequestsORM(id=uuid4(), user_id=uuid4(), requested_quota=10, reason="Reason 1", status="pending"),
            QuotaRequestsORM(id=uuid4(), user_id=uuid4(), requested_quota=15, reason="Reason 2", status="pending"),
        ]
        
        with patch('app.db_interface.quota_requests.Session') as mock_session_class:
            mock_session_instance = mock_session_class.return_value.__enter__.return_value
            mock_query = mock_session_instance.query.return_value
            mock_filter = mock_query.filter.return_value
            mock_order = mock_filter.order_by.return_value
            mock_order.all.return_value = mock_requests
            
            result = get_pending_quota_requests()
            
            assert result == mock_requests
            assert len(result) == 2

    def test_get_pending_requests_empty(self):
        """Test retrieval when no pending requests exist"""
        with patch('app.db_interface.quota_requests.Session') as mock_session_class:
            mock_session_instance = mock_session_class.return_value.__enter__.return_value
            mock_query = mock_session_instance.query.return_value
            mock_filter = mock_query.filter.return_value
            mock_order = mock_filter.order_by.return_value
            mock_order.all.return_value = []
            
            result = get_pending_quota_requests()
            
            assert result == []


class TestGetPendingQuotaRequestsWithUsers:
    """Test cases for get_pending_quota_requests_with_users function"""

    def test_get_pending_with_users_success(self):
        """Test successful retrieval of pending requests with user info"""
        user_id = uuid4()
        request_id = uuid4()
        
        mock_user = UsersORM(
            id=user_id,
            auth0_sub="auth0|123",
            email="test@example.com",
            name="Test User",
            agent_quota=10,
            agent_quota_used=5
        )
        
        mock_request = MagicMock(spec=QuotaRequestsORM)
        mock_request.id = request_id
        mock_request.user_id = user_id
        mock_request.requested_quota = 20
        mock_request.reason = "Need more quota"
        mock_request.status = "pending"
        mock_request.created_at = datetime(2024, 1, 15, 10, 0, 0)
        mock_request.users_orm = mock_user
        
        with patch('app.db_interface.quota_requests.Session') as mock_session_class:
            mock_session_instance = mock_session_class.return_value.__enter__.return_value
            mock_query = mock_session_instance.query.return_value
            mock_options = mock_query.options.return_value
            mock_filter = mock_options.filter.return_value
            mock_order = mock_filter.order_by.return_value
            mock_order.all.return_value = [mock_request]
            
            result = get_pending_quota_requests_with_users()
            
            assert len(result) == 1
            assert result[0]["id"] == str(request_id)
            assert result[0]["user_id"] == str(user_id)
            assert result[0]["user_name"] == "Test User"
            assert result[0]["user_email"] == "test@example.com"
            assert result[0]["current_quota"] == 10
            assert result[0]["current_used"] == 5
            assert result[0]["requested_quota"] == 20
            assert result[0]["reason"] == "Need more quota"
            assert result[0]["status"] == "pending"

    def test_get_pending_with_users_no_user(self):
        """Test retrieval when request has no associated user"""
        request_id = uuid4()
        user_id = uuid4()
        
        mock_request = MagicMock(spec=QuotaRequestsORM)
        mock_request.id = request_id
        mock_request.user_id = user_id
        mock_request.requested_quota = 15
        mock_request.reason = "Test reason"
        mock_request.status = "pending"
        mock_request.created_at = None
        mock_request.users_orm = None  # No user
        
        with patch('app.db_interface.quota_requests.Session') as mock_session_class:
            mock_session_instance = mock_session_class.return_value.__enter__.return_value
            mock_query = mock_session_instance.query.return_value
            mock_options = mock_query.options.return_value
            mock_filter = mock_options.filter.return_value
            mock_order = mock_filter.order_by.return_value
            mock_order.all.return_value = [mock_request]
            
            result = get_pending_quota_requests_with_users()
            
            assert len(result) == 1
            assert result[0]["user_name"] is None
            assert result[0]["user_email"] is None
            assert result[0]["current_quota"] == 10  # Default
            assert result[0]["current_used"] == 0  # Default

    def test_get_pending_with_users_database_error(self):
        """Test retrieval with database error"""
        with patch('app.db_interface.quota_requests.Session') as mock_session_class:
            mock_session_instance = mock_session_class.return_value.__enter__.return_value
            mock_session_instance.query.side_effect = Exception("Database error")
            
            with pytest.raises(Exception) as exc_info:
                get_pending_quota_requests_with_users()
            
            assert str(exc_info.value) == "Database error"


class TestGetQuotaRequestById:
    """Test cases for get_quota_request_by_id function"""

    def test_get_by_id_success(self):
        """Test successful retrieval of quota request by ID"""
        request_id = uuid4()
        mock_request = QuotaRequestsORM(
            id=request_id,
            user_id=uuid4(),
            requested_quota=20,
            reason="Test reason",
            status="pending"
        )
        
        with patch('app.db_interface.quota_requests.Session') as mock_session_class:
            mock_session_instance = mock_session_class.return_value.__enter__.return_value
            mock_query = mock_session_instance.query.return_value
            mock_filter = mock_query.filter.return_value
            mock_filter.first.return_value = mock_request
            
            result = get_quota_request_by_id(request_id)
            
            assert result == mock_request
            assert result.id == request_id

    def test_get_by_id_not_found(self):
        """Test retrieval when request doesn't exist"""
        request_id = uuid4()
        
        with patch('app.db_interface.quota_requests.Session') as mock_session_class:
            mock_session_instance = mock_session_class.return_value.__enter__.return_value
            mock_query = mock_session_instance.query.return_value
            mock_filter = mock_query.filter.return_value
            mock_filter.first.return_value = None
            
            result = get_quota_request_by_id(request_id)
            
            assert result is None


class TestApproveQuotaRequest:
    """Test cases for approve_quota_request function"""

    def test_approve_success(self):
        """Test successful approval of quota request"""
        request_id = uuid4()
        user_id = uuid4()
        
        mock_request = MagicMock(spec=QuotaRequestsORM)
        mock_request.id = request_id
        mock_request.user_id = user_id
        mock_request.requested_quota = 20
        mock_request.status = QuotaRequestStatus.PENDING.value
        
        mock_user = MagicMock(spec=UsersORM)
        mock_user.id = user_id
        mock_user.agent_quota = 10
        
        with patch('app.db_interface.quota_requests.Session') as mock_session_class:
            mock_session_instance = mock_session_class.return_value.__enter__.return_value
            
            # First query for request
            mock_query1 = MagicMock()
            mock_options = MagicMock()
            mock_filter1 = MagicMock()
            mock_query1.options.return_value = mock_options
            mock_options.filter.return_value = mock_filter1
            mock_filter1.first.return_value = mock_request
            
            # Second query for user
            mock_query2 = MagicMock()
            mock_filter2 = MagicMock()
            mock_query2.filter.return_value = mock_filter2
            mock_filter2.first.return_value = mock_user
            
            mock_session_instance.query.side_effect = [mock_query1, mock_query2]
            mock_session_instance.commit = Mock()
            
            result = approve_quota_request(request_id)
            
            assert result["id"] == str(request_id)
            assert result["status"] == QuotaRequestStatus.APPROVED.value
            assert mock_user.agent_quota == 30  # 10 + 20
            mock_session_instance.commit.assert_called_once()

    def test_approve_request_not_found(self):
        """Test approval when request doesn't exist"""
        request_id = uuid4()
        
        with patch('app.db_interface.quota_requests.Session') as mock_session_class:
            mock_session_instance = mock_session_class.return_value.__enter__.return_value
            mock_query = mock_session_instance.query.return_value
            mock_options = mock_query.options.return_value
            mock_filter = mock_options.filter.return_value
            mock_filter.first.return_value = None
            
            with pytest.raises(ValueError) as exc_info:
                approve_quota_request(request_id)
            
            assert "not found" in str(exc_info.value)

    def test_approve_request_not_pending(self):
        """Test approval when request is not pending"""
        request_id = uuid4()
        
        mock_request = MagicMock(spec=QuotaRequestsORM)
        mock_request.id = request_id
        mock_request.status = QuotaRequestStatus.APPROVED.value  # Already approved
        
        with patch('app.db_interface.quota_requests.Session') as mock_session_class:
            mock_session_instance = mock_session_class.return_value.__enter__.return_value
            mock_query = mock_session_instance.query.return_value
            mock_options = mock_query.options.return_value
            mock_filter = mock_options.filter.return_value
            mock_filter.first.return_value = mock_request
            
            with pytest.raises(ValueError) as exc_info:
                approve_quota_request(request_id)
            
            assert "not pending" in str(exc_info.value)


class TestDenyQuotaRequest:
    """Test cases for deny_quota_request function"""

    def test_deny_success(self):
        """Test successful denial of quota request"""
        request_id = uuid4()
        user_id = uuid4()
        
        mock_request = MagicMock(spec=QuotaRequestsORM)
        mock_request.id = request_id
        mock_request.user_id = user_id
        mock_request.status = QuotaRequestStatus.PENDING.value
        
        with patch('app.db_interface.quota_requests.Session') as mock_session_class:
            mock_session_instance = mock_session_class.return_value.__enter__.return_value
            mock_query = mock_session_instance.query.return_value
            mock_filter = mock_query.filter.return_value
            mock_filter.first.return_value = mock_request
            mock_session_instance.commit = Mock()
            
            result = deny_quota_request(request_id)
            
            assert result["id"] == str(request_id)
            assert result["status"] == QuotaRequestStatus.DENIED.value
            assert result["user_id"] == str(user_id)
            mock_session_instance.commit.assert_called_once()

    def test_deny_request_not_found(self):
        """Test denial when request doesn't exist"""
        request_id = uuid4()
        
        with patch('app.db_interface.quota_requests.Session') as mock_session_class:
            mock_session_instance = mock_session_class.return_value.__enter__.return_value
            mock_query = mock_session_instance.query.return_value
            mock_filter = mock_query.filter.return_value
            mock_filter.first.return_value = None
            
            with pytest.raises(ValueError) as exc_info:
                deny_quota_request(request_id)
            
            assert "not found" in str(exc_info.value)

    def test_deny_request_not_pending(self):
        """Test denial when request is not pending"""
        request_id = uuid4()
        
        mock_request = MagicMock(spec=QuotaRequestsORM)
        mock_request.id = request_id
        mock_request.status = QuotaRequestStatus.DENIED.value  # Already denied
        
        with patch('app.db_interface.quota_requests.Session') as mock_session_class:
            mock_session_instance = mock_session_class.return_value.__enter__.return_value
            mock_query = mock_session_instance.query.return_value
            mock_filter = mock_query.filter.return_value
            mock_filter.first.return_value = mock_request
            
            with pytest.raises(ValueError) as exc_info:
                deny_quota_request(request_id)
            
            assert "not pending" in str(exc_info.value)

    def test_deny_database_error(self):
        """Test denial with database error"""
        request_id = uuid4()
        
        with patch('app.db_interface.quota_requests.Session') as mock_session_class:
            mock_session_instance = mock_session_class.return_value.__enter__.return_value
            mock_session_instance.query.side_effect = Exception("Database error")
            
            with pytest.raises(Exception) as exc_info:
                deny_quota_request(request_id)
            
            assert str(exc_info.value) == "Database error"
