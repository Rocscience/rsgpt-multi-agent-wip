"""Tests for SSL connection retry mechanism and database resilience"""

import pytest
import time
from unittest.mock import Mock, patch, MagicMock
from sqlalchemy.exc import OperationalError, DisconnectionError

from app.db_models.connection import with_db_retry, execute_with_retry, check_database_health
from app.db_interface.users import get_user_by_auth0_sub


class TestSSLConnectionRetry:
    """Test the SSL connection retry mechanism"""

    def test_with_db_retry_decorator_success_first_attempt(self):
        """Test that successful operations don't get retried"""
        call_count = 0
        
        @with_db_retry(max_retries=3, retry_delay=0.1)
        def mock_db_operation():
            nonlocal call_count
            call_count += 1
            return "success"
        
        result = mock_db_operation()
        
        assert result == "success"
        assert call_count == 1

    def test_with_db_retry_ssl_connection_error_retry(self):
        """Test that SSL connection errors trigger retries"""
        call_count = 0
        
        @with_db_retry(max_retries=2, retry_delay=0.1)
        def mock_db_operation():
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                # Simulate SSL connection error for first 2 attempts
                raise OperationalError(
                    "SSL connection has been closed unexpectedly", 
                    None, 
                    None
                )
            return "success_after_retry"
        
        with patch('app.db_models.connection.engine') as mock_engine:
            result = mock_db_operation()
            
            assert result == "success_after_retry"
            assert call_count == 3
            # Verify engine.dispose() was called on retry attempts
            assert mock_engine.dispose.call_count == 2

    def test_with_db_retry_non_ssl_error_no_retry(self):
        """Test that non-SSL errors don't trigger retries"""
        call_count = 0
        
        @with_db_retry(max_retries=3, retry_delay=0.1)
        def mock_db_operation():
            nonlocal call_count
            call_count += 1
            raise OperationalError("Database does not exist", None, None)
        
        with pytest.raises(OperationalError, match="Database does not exist"):
            mock_db_operation()
        
        assert call_count == 1

    def test_with_db_retry_exhausted_retries(self):
        """Test behavior when all retries are exhausted"""
        call_count = 0
        
        @with_db_retry(max_retries=2, retry_delay=0.1)
        def mock_db_operation():
            nonlocal call_count
            call_count += 1
            raise OperationalError(
                "SSL connection has been closed unexpectedly", 
                None, 
                None
            )
        
        with patch('app.db_models.connection.engine') as mock_engine:
            with pytest.raises(OperationalError, match="SSL connection has been closed"):
                mock_db_operation()
            
            assert call_count == 3  # Initial attempt + 2 retries
            assert mock_engine.dispose.call_count == 2

    def test_execute_with_retry_function(self):
        """Test the execute_with_retry utility function"""
        def sample_func(x, y, z=None):
            if z == "fail":
                raise OperationalError("SSL connection has been closed", None, None)
            return x + y
        
        with patch('app.db_models.connection.engine'):
            # Test successful execution
            result = execute_with_retry(sample_func, 1, 2, z="success")
            assert result == 3

    @patch('app.db_models.connection.Session')
    @patch('app.db_models.connection.text')
    def test_check_database_health_healthy(self, mock_text, mock_session_class):
        """Test database health check when database is healthy"""
        # Mock session and query result
        mock_session = MagicMock()
        mock_session_class.return_value.__enter__.return_value = mock_session
        mock_session.execute.return_value.scalar.return_value = 1
        mock_text.return_value = "SELECT 1"
        
        # Mock connection pool
        with patch('app.db_models.connection.engine') as mock_engine:
            mock_pool = MagicMock()
            mock_pool.size.return_value = 10
            mock_pool.checkedin.return_value = 8
            mock_pool.checkedout.return_value = 2
            mock_pool.overflow.return_value = 0
            mock_engine.pool = mock_pool
            
            health_status = check_database_health()
            
            assert health_status["database"] == "healthy"
            assert health_status["error"] is None
            assert health_status["connection_pool"]["size"] == 10
            assert health_status["connection_pool"]["checked_in"] == 8
            assert health_status["connection_pool"]["checked_out"] == 2
            assert health_status["connection_pool"]["overflow"] == 0

    @patch('app.db_models.connection.Session')
    @patch('app.db_models.connection.text')
    def test_check_database_health_unhealthy(self, mock_text, mock_session_class):
        """Test database health check when database is unhealthy"""
        # Mock session to raise an error
        mock_session_class.return_value.__enter__.side_effect = OperationalError(
            "SSL connection has been closed", None, None
        )
        mock_text.return_value = "SELECT 1"
        
        health_status = check_database_health()
        
        assert health_status["database"] == "unhealthy"
        assert "SSL connection has been closed" in health_status["error"]


class TestUserFunctionsWithRetry:
    """Test that user database functions properly use retry mechanism"""

    @patch('app.db_interface.users.Session')
    def test_get_user_by_auth0_sub_with_retry(self, mock_session_class):
        """Test that get_user_by_auth0_sub uses retry mechanism"""
        mock_session = MagicMock()
        mock_session_class.return_value.__enter__.return_value = mock_session
        
        # Mock user object
        mock_user = MagicMock()
        mock_user.auth0_sub = "test-auth0-sub"
        mock_session.query.return_value.filter.return_value.first.return_value = mock_user
        
        with patch('app.db_models.connection.engine'):
            result = get_user_by_auth0_sub("test-auth0-sub")
            
            assert result == mock_user
            mock_session.query.assert_called_once()

    @patch('app.db_interface.users.Session')
    def test_get_user_by_auth0_sub_retry_on_ssl_error(self, mock_session_class):
        """Test that get_user_by_auth0_sub retries on SSL connection errors"""
        call_count = 0
        
        def mock_session_context():
            nonlocal call_count
            call_count += 1
            mock_session = MagicMock()
            
            if call_count <= 2:
                # First two attempts fail with SSL error
                mock_session.query.return_value.filter.return_value.first.side_effect = \
                    OperationalError("SSL connection has been closed unexpectedly", None, None)
            else:
                # Third attempt succeeds
                mock_user = MagicMock()
                mock_user.auth0_sub = "test-auth0-sub"
                mock_session.query.return_value.filter.return_value.first.return_value = mock_user
            
            return mock_session
        
        mock_session_class.return_value.__enter__.side_effect = mock_session_context
        
        with patch('app.db_models.connection.engine') as mock_engine:
            result = get_user_by_auth0_sub("test-auth0-sub")
            
            assert result.auth0_sub == "test-auth0-sub"
            assert call_count == 3
            # Verify engine was disposed on retry attempts
            assert mock_engine.dispose.call_count == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
