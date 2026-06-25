"""Tests for app.db_interface.users module"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from uuid import uuid4
from datetime import datetime

from app.db_interface.users import create_user, get_user_id_by_auth0_sub
from app.db_models.users import UsersORM
from app.models.users import CreateUserRequest


class TestCreateUser:
    """Test cases for create_user function"""
    
    def test_create_user_success_with_all_fields(self):
        """Test successful user creation with all fields provided"""
        # Arrange
        user_request = CreateUserRequest(
            auth0_sub="auth0|123456789",
            email="test@example.com",
            name="John Doe",
            first_name="John",
            last_name="Doe",
            profile_picture_url="https://example.com/profile.jpg",
            last_login="2024-01-01T00:00:00Z",
            is_active=True
        )
        
        with patch('app.db_interface.users.Session') as mock_session_class:
            mock_session_instance = mock_session_class.return_value.__enter__.return_value
            mock_session_instance.add = Mock()
            mock_session_instance.commit = Mock()
            mock_session_instance.refresh = Mock()
            
            # Act
            result = create_user(user_request)
            
            # Assert
            mock_session_instance.add.assert_called_once()
            mock_session_instance.commit.assert_called_once()
            mock_session_instance.refresh.assert_called_once()
            
            # Verify the created user has correct attributes
            added_user = mock_session_instance.add.call_args[0][0]
            assert isinstance(added_user, UsersORM)
            assert added_user.auth0_sub == user_request.auth0_sub
            assert added_user.email == user_request.email
            assert added_user.name == user_request.name
            assert added_user.first_name == user_request.first_name
            assert added_user.last_name == user_request.last_name
            assert added_user.profile_picture_url == user_request.profile_picture_url
            assert added_user.last_login == user_request.last_login
            assert added_user.is_active == user_request.is_active

    def test_create_user_success_with_minimal_fields(self):
        """Test successful user creation with only required fields"""
        # Arrange
        user_request = CreateUserRequest(
            auth0_sub="auth0|987654321",
            email="minimal@example.com"
        )
        
        with patch('app.db_interface.users.Session') as mock_session_class:
            mock_session_instance = mock_session_class.return_value.__enter__.return_value
            mock_session_instance.add = Mock()
            mock_session_instance.commit = Mock()
            mock_session_instance.refresh = Mock()
            
            # Act
            result = create_user(user_request)
            
            # Assert
            added_user = mock_session_instance.add.call_args[0][0]
            assert added_user.auth0_sub == user_request.auth0_sub
            assert added_user.email == user_request.email
            assert added_user.name is None
            assert added_user.first_name is None
            assert added_user.last_name is None
            assert added_user.profile_picture_url is None
            assert added_user.last_login is None
            assert added_user.is_active is True  # Default value

    def test_create_user_database_error(self):
        """Test user creation with database error"""
        # Arrange
        user_request = CreateUserRequest(
            auth0_sub="auth0|123456789",
            email="test@example.com"
        )
        
        with patch('app.db_interface.users.Session') as mock_session_class:
            mock_session_instance = mock_session_class.return_value.__enter__.return_value
            mock_session_instance.add.side_effect = Exception("Database error")
            
            # Act & Assert
            with pytest.raises(Exception) as exc_info:
                create_user(user_request)
            
            assert str(exc_info.value) == "Database error"

    @patch('app.db_interface.users.logger')
    def test_create_user_logs_info_and_error(self, mock_logger):
        """Test that user creation logs appropriate info and error messages"""
        # Arrange
        user_request = CreateUserRequest(
            auth0_sub="auth0|123456789",
            email="test@example.com"
        )
        
        with patch('app.db_interface.users.Session') as mock_session_class:
            mock_session_instance = mock_session_class.return_value.__enter__.return_value
            mock_session_instance.add.side_effect = Exception("Database error")
            
            # Act & Assert
            with pytest.raises(Exception):
                create_user(user_request)
            
            # Verify logging calls
            assert mock_logger.info.call_count == 1
            assert mock_logger.error.call_count == 1
            
            # Check specific log messages
            info_call = mock_logger.info.call_args_list[0][0][0]
            error_call = mock_logger.error.call_args_list[0][0][0]
            
            assert f"Creating user: {user_request}" in info_call
            assert "Error creating user: Database error" in error_call

    @patch('app.db_interface.users.logger')
    def test_create_user_logs_success(self, mock_logger):
        """Test that successful user creation logs appropriate messages"""
        # Arrange
        user_request = CreateUserRequest(
            auth0_sub="auth0|123456789",
            email="test@example.com"
        )
        
        with patch('app.db_interface.users.Session') as mock_session_class:
            mock_session_instance = mock_session_class.return_value.__enter__.return_value
            mock_session_instance.add = Mock()
            mock_session_instance.commit = Mock()
            mock_session_instance.refresh = Mock()
            
            # Act
            result = create_user(user_request)
            
            # Assert
            assert mock_logger.info.call_count == 2
            assert mock_logger.error.call_count == 0
            
            # Check log messages
            creation_log = mock_logger.info.call_args_list[0][0][0]
            success_log = mock_logger.info.call_args_list[1][0][0]
            
            assert f"Creating user: {user_request}" in creation_log
            assert "User created:" in success_log


class TestGetUserIdByAuth0Sub:
    """Test cases for get_user_id_by_auth0_sub function"""
    
    def test_get_user_id_by_auth0_sub_success(self):
        """Test successful retrieval of user ID by auth0_sub"""
        # Arrange
        auth0_sub = "auth0|123456789"
        expected_user_id = uuid4()
        
        with patch('app.db_interface.users.Session') as mock_session_class:
            mock_session_instance = mock_session_class.return_value.__enter__.return_value
            mock_query = mock_session_instance.query.return_value
            mock_filter = mock_query.filter.return_value
            mock_filter.scalar.return_value = expected_user_id
            
            # Act
            result = get_user_id_by_auth0_sub(auth0_sub)
            
            # Assert
            assert result == expected_user_id
            mock_session_instance.query.assert_called_once_with(UsersORM.id)

    def test_get_user_id_by_auth0_sub_not_found(self):
        """Test retrieval when user with auth0_sub doesn't exist"""
        # Arrange
        auth0_sub = "auth0|nonexistent"
        
        with patch('app.db_interface.users.Session') as mock_session_class:
            mock_session_instance = mock_session_class.return_value.__enter__.return_value
            mock_query = mock_session_instance.query.return_value
            mock_filter = mock_query.filter.return_value
            mock_filter.scalar.return_value = None
            
            # Act
            result = get_user_id_by_auth0_sub(auth0_sub)
            
            # Assert
            assert result is None

    def test_get_user_id_by_auth0_sub_database_error(self):
        """Test user ID retrieval with database error"""
        # Arrange
        auth0_sub = "auth0|123456789"
        
        with patch('app.db_interface.users.Session') as mock_session_class:
            mock_session_instance = mock_session_class.return_value.__enter__.return_value
            mock_session_instance.query.side_effect = Exception("Database error")
            
            # Act & Assert
            with pytest.raises(Exception) as exc_info:
                get_user_id_by_auth0_sub(auth0_sub)
            
            assert str(exc_info.value) == "Database error"

    @patch('app.db_interface.users.logger')
    def test_get_user_id_by_auth0_sub_logs_info_and_error(self, mock_logger):
        """Test that user ID retrieval logs appropriate info and error messages"""
        # Arrange
        auth0_sub = "auth0|123456789"
        
        with patch('app.db_interface.users.Session') as mock_session_class:
            mock_session_instance = mock_session_class.return_value.__enter__.return_value
            mock_session_instance.query.side_effect = Exception("Database error")
            
            # Act & Assert
            with pytest.raises(Exception):
                get_user_id_by_auth0_sub(auth0_sub)
            
            # Verify logging calls
            assert mock_logger.info.call_count == 1
            assert mock_logger.error.call_count == 1
            
            # Check specific log messages
            info_call = mock_logger.info.call_args_list[0][0][0]
            error_call = mock_logger.error.call_args_list[0][0][0]
            
            assert f"Getting user by auth0_sub: {auth0_sub}" in info_call
            assert "Error getting user by auth0_sub: Database error" in error_call

    @patch('app.db_interface.users.logger')
    def test_get_user_id_by_auth0_sub_logs_success(self, mock_logger):
        """Test that successful user ID retrieval logs appropriate messages"""
        # Arrange
        auth0_sub = "auth0|123456789"
        expected_user_id = uuid4()
        
        with patch('app.db_interface.users.Session') as mock_session_class:
            mock_session_instance = mock_session_class.return_value.__enter__.return_value
            mock_query = mock_session_instance.query.return_value
            mock_filter = mock_query.filter.return_value
            mock_filter.scalar.return_value = expected_user_id
            
            # Act
            result = get_user_id_by_auth0_sub(auth0_sub)
            
            # Assert
            assert mock_logger.info.call_count == 2
            assert mock_logger.error.call_count == 0
            
            # Check log messages
            getting_log = mock_logger.info.call_args_list[0][0][0]
            found_log = mock_logger.info.call_args_list[1][0][0]
            
            assert f"Getting user by auth0_sub: {auth0_sub}" in getting_log
            assert f"User ID found: {expected_user_id}" in found_log

    def test_get_user_id_by_auth0_sub_filter_called_correctly(self):
        """Test that the database filter is called with correct parameters"""
        # Arrange
        auth0_sub = "auth0|123456789"
        
        with patch('app.db_interface.users.Session') as mock_session_class:
            mock_session_instance = mock_session_class.return_value.__enter__.return_value
            mock_query = mock_session_instance.query.return_value
            mock_filter = mock_query.filter.return_value
            mock_filter.scalar.return_value = None
            
            # Act
            get_user_id_by_auth0_sub(auth0_sub)
            
            # Assert
            mock_query.filter.assert_called_once()
            # Verify that the filter was called with the correct condition 


class TestGetUserById:
    """Test cases for get_user_by_id function"""
    
    def test_get_user_by_id_success(self):
        """Test successful retrieval of user by user_id"""
        from app.db_interface.users import get_user_by_id
        
        # Arrange
        user_id = uuid4()
        mock_user = UsersORM(
            id=user_id,
            auth0_sub="auth0|123456789",
            email="test@example.com",
            agent_quota=10,
            agent_quota_used=5
        )
        
        with patch('app.db_interface.users.Session') as mock_session_class:
            mock_session_instance = mock_session_class.return_value.__enter__.return_value
            mock_query = mock_session_instance.query.return_value
            mock_filter = mock_query.filter.return_value
            mock_filter.first.return_value = mock_user
            
            # Act
            result = get_user_by_id(user_id)
            
            # Assert
            assert result == mock_user
            mock_session_instance.query.assert_called_once_with(UsersORM)

    def test_get_user_by_id_not_found(self):
        """Test retrieval when user doesn't exist"""
        from app.db_interface.users import get_user_by_id
        
        # Arrange
        user_id = uuid4()
        
        with patch('app.db_interface.users.Session') as mock_session_class:
            mock_session_instance = mock_session_class.return_value.__enter__.return_value
            mock_query = mock_session_instance.query.return_value
            mock_filter = mock_query.filter.return_value
            mock_filter.first.return_value = None
            
            # Act
            result = get_user_by_id(user_id)
            
            # Assert
            assert result is None

    def test_get_user_by_id_database_error(self):
        """Test user retrieval with database error"""
        from app.db_interface.users import get_user_by_id
        
        # Arrange
        user_id = uuid4()
        
        with patch('app.db_interface.users.Session') as mock_session_class:
            mock_session_instance = mock_session_class.return_value.__enter__.return_value
            mock_session_instance.query.side_effect = Exception("Database error")
            
            # Act & Assert
            with pytest.raises(Exception) as exc_info:
                get_user_by_id(user_id)
            
            assert str(exc_info.value) == "Database error"


class TestIncrementUserAgentQuotaUsed:
    """Test cases for increment_user_agent_quota_used function"""
    
    def test_increment_agent_quota_used_success_default_amount(self):
        """Test successful increment of agent quota used with default amount (1)"""
        from app.db_interface.users import increment_user_agent_quota_used
        
        # Arrange
        user_id = uuid4()
        initial_quota_used = 3
        mock_user = UsersORM(
            id=user_id,
            auth0_sub="auth0|123456789",
            email="test@example.com",
            agent_quota=10,
            agent_quota_used=initial_quota_used
        )
        
        with patch('app.db_interface.users.Session') as mock_session_class:
            mock_session_instance = mock_session_class.return_value.__enter__.return_value
            mock_query = mock_session_instance.query.return_value
            mock_filter = mock_query.filter.return_value
            mock_filter.first.return_value = mock_user
            mock_session_instance.commit = Mock()
            mock_session_instance.refresh = Mock()
            
            # Act
            result = increment_user_agent_quota_used(user_id)
            
            # Assert
            assert mock_user.agent_quota_used == initial_quota_used + 1
            assert result == mock_user
            mock_session_instance.commit.assert_called_once()
            mock_session_instance.refresh.assert_called_once_with(mock_user)

    def test_increment_agent_quota_used_success_custom_amount(self):
        """Test successful increment of agent quota used with custom amount"""
        from app.db_interface.users import increment_user_agent_quota_used
        
        # Arrange
        user_id = uuid4()
        initial_quota_used = 2
        increment_amount = 3
        mock_user = UsersORM(
            id=user_id,
            auth0_sub="auth0|123456789",
            email="test@example.com",
            agent_quota=10,
            agent_quota_used=initial_quota_used
        )
        
        with patch('app.db_interface.users.Session') as mock_session_class:
            mock_session_instance = mock_session_class.return_value.__enter__.return_value
            mock_query = mock_session_instance.query.return_value
            mock_filter = mock_query.filter.return_value
            mock_filter.first.return_value = mock_user
            mock_session_instance.commit = Mock()
            mock_session_instance.refresh = Mock()
            
            # Act
            result = increment_user_agent_quota_used(user_id, increment_amount)
            
            # Assert
            assert mock_user.agent_quota_used == initial_quota_used + increment_amount
            assert result == mock_user
            mock_session_instance.commit.assert_called_once()

    def test_increment_agent_quota_used_user_not_found(self):
        """Test increment when user doesn't exist"""
        from app.db_interface.users import increment_user_agent_quota_used
        
        # Arrange
        user_id = uuid4()
        
        with patch('app.db_interface.users.Session') as mock_session_class:
            mock_session_instance = mock_session_class.return_value.__enter__.return_value
            mock_query = mock_session_instance.query.return_value
            mock_filter = mock_query.filter.return_value
            mock_filter.first.return_value = None
            
            # Act
            result = increment_user_agent_quota_used(user_id)
            
            # Assert
            assert result is None

    def test_increment_agent_quota_used_database_error(self):
        """Test increment agent quota with database error"""
        from app.db_interface.users import increment_user_agent_quota_used
        
        # Arrange
        user_id = uuid4()
        
        with patch('app.db_interface.users.Session') as mock_session_class:
            mock_session_instance = mock_session_class.return_value.__enter__.return_value
            mock_session_instance.query.side_effect = Exception("Database error")
            
            # Act & Assert
            with pytest.raises(Exception) as exc_info:
                increment_user_agent_quota_used(user_id)
            
            assert str(exc_info.value) == "Database error"


class TestResetUserAgentQuota:
    """Test cases for reset_user_agent_quota function"""
    
    def test_reset_agent_quota_success(self):
        """Test successful reset of agent quota for a user"""
        from app.db_interface.users import reset_user_agent_quota
        
        # Arrange
        user_id = uuid4()
        mock_user = UsersORM(
            id=user_id,
            auth0_sub="auth0|123456789",
            email="test@example.com",
            agent_quota=5,  # Was reduced somehow
            agent_quota_used=8
        )
        
        with patch('app.db_interface.users.Session') as mock_session_class:
            mock_session_instance = mock_session_class.return_value.__enter__.return_value
            mock_query = mock_session_instance.query.return_value
            mock_filter = mock_query.filter.return_value
            mock_filter.first.return_value = mock_user
            mock_session_instance.commit = Mock()
            mock_session_instance.refresh = Mock()
            
            # Act
            result = reset_user_agent_quota(user_id)
            
            # Assert
            assert mock_user.agent_quota == 25
            assert mock_user.agent_quota_used == 0
            assert result == mock_user
            mock_session_instance.commit.assert_called_once()
            mock_session_instance.refresh.assert_called_once_with(mock_user)

    def test_reset_agent_quota_user_not_found(self):
        """Test reset when user doesn't exist"""
        from app.db_interface.users import reset_user_agent_quota
        
        # Arrange
        user_id = uuid4()
        
        with patch('app.db_interface.users.Session') as mock_session_class:
            mock_session_instance = mock_session_class.return_value.__enter__.return_value
            mock_query = mock_session_instance.query.return_value
            mock_filter = mock_query.filter.return_value
            mock_filter.first.return_value = None
            
            # Act
            result = reset_user_agent_quota(user_id)
            
            # Assert
            assert result is None

    def test_reset_agent_quota_database_error(self):
        """Test reset agent quota with database error"""
        from app.db_interface.users import reset_user_agent_quota
        
        # Arrange
        user_id = uuid4()
        
        with patch('app.db_interface.users.Session') as mock_session_class:
            mock_session_instance = mock_session_class.return_value.__enter__.return_value
            mock_session_instance.query.side_effect = Exception("Database error")
            
            # Act & Assert
            with pytest.raises(Exception) as exc_info:
                reset_user_agent_quota(user_id)
            
            assert str(exc_info.value) == "Database error"


class TestGetAllUsersForAgentQuotaReset:
    """Test cases for get_all_users_for_agent_quota_reset function"""
    
    def test_get_all_users_for_reset_success(self):
        """Test successful retrieval of users for agent quota reset"""
        from app.db_interface.users import get_all_users_for_agent_quota_reset
        
        # Arrange
        mock_users = [
            UsersORM(id=uuid4(), auth0_sub="auth0|1", email="user1@test.com", is_active=True, agent_quota_used=5),
            UsersORM(id=uuid4(), auth0_sub="auth0|2", email="user2@test.com", is_active=True, agent_quota_used=3),
        ]
        
        with patch('app.db_interface.users.Session') as mock_session_class:
            mock_session_instance = mock_session_class.return_value.__enter__.return_value
            mock_query = mock_session_instance.query.return_value
            mock_filter = mock_query.filter.return_value
            mock_filter.all.return_value = mock_users
            
            # Act
            result = get_all_users_for_agent_quota_reset()
            
            # Assert
            assert result == mock_users
            assert len(result) == 2

    def test_get_all_users_for_reset_empty(self):
        """Test retrieval when no users need reset"""
        from app.db_interface.users import get_all_users_for_agent_quota_reset
        
        with patch('app.db_interface.users.Session') as mock_session_class:
            mock_session_instance = mock_session_class.return_value.__enter__.return_value
            mock_query = mock_session_instance.query.return_value
            mock_filter = mock_query.filter.return_value
            mock_filter.all.return_value = []
            
            # Act
            result = get_all_users_for_agent_quota_reset()
            
            # Assert
            assert result == []
            assert len(result) == 0

    def test_get_all_users_for_reset_database_error(self):
        """Test retrieval with database error"""
        from app.db_interface.users import get_all_users_for_agent_quota_reset
        
        with patch('app.db_interface.users.Session') as mock_session_class:
            mock_session_instance = mock_session_class.return_value.__enter__.return_value
            mock_session_instance.query.side_effect = Exception("Database error")
            
            # Act & Assert
            with pytest.raises(Exception) as exc_info:
                get_all_users_for_agent_quota_reset()
            
            assert str(exc_info.value) == "Database error"


class TestResetAllUsersAgentQuota:
    """Test cases for reset_all_users_agent_quota function"""
    
    def test_reset_all_users_success(self):
        """Test successful bulk reset of agent quota for all users"""
        from app.db_interface.users import reset_all_users_agent_quota
        
        with patch('app.db_interface.users.Session') as mock_session_class:
            mock_session_instance = mock_session_class.return_value.__enter__.return_value
            mock_query = mock_session_instance.query.return_value
            mock_filter = mock_query.filter.return_value
            mock_filter.update.return_value = 5  # 5 users updated
            mock_session_instance.commit = Mock()
            
            # Act
            result = reset_all_users_agent_quota()
            
            # Assert
            assert result == 5
            mock_session_instance.commit.assert_called_once()

    def test_reset_all_users_no_users_to_reset(self):
        """Test bulk reset when no users need reset"""
        from app.db_interface.users import reset_all_users_agent_quota
        
        with patch('app.db_interface.users.Session') as mock_session_class:
            mock_session_instance = mock_session_class.return_value.__enter__.return_value
            mock_query = mock_session_instance.query.return_value
            mock_filter = mock_query.filter.return_value
            mock_filter.update.return_value = 0  # No users updated
            mock_session_instance.commit = Mock()
            
            # Act
            result = reset_all_users_agent_quota()
            
            # Assert
            assert result == 0
            mock_session_instance.commit.assert_called_once()

    def test_reset_all_users_database_error(self):
        """Test bulk reset with database error"""
        from app.db_interface.users import reset_all_users_agent_quota
        
        with patch('app.db_interface.users.Session') as mock_session_class:
            mock_session_instance = mock_session_class.return_value.__enter__.return_value
            mock_session_instance.query.side_effect = Exception("Database error")
            
            # Act & Assert
            with pytest.raises(Exception) as exc_info:
                reset_all_users_agent_quota()
            
            assert str(exc_info.value) == "Database error"

    def test_reset_all_users_commit_error(self):
        """Test bulk reset with commit error"""
        from app.db_interface.users import reset_all_users_agent_quota
        
        with patch('app.db_interface.users.Session') as mock_session_class:
            mock_session_instance = mock_session_class.return_value.__enter__.return_value
            mock_query = mock_session_instance.query.return_value
            mock_filter = mock_query.filter.return_value
            mock_filter.update.return_value = 3
            mock_session_instance.commit.side_effect = Exception("Commit failed")
            
            # Act & Assert
            with pytest.raises(Exception) as exc_info:
                reset_all_users_agent_quota()
            
            assert str(exc_info.value) == "Commit failed"