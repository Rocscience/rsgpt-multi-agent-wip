"""Tests for app.db_interface.chats module"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from uuid import uuid4, UUID
from datetime import datetime

from app.db_interface.chats import (
    create_chat_session, 
    get_chat_session, 
    delete_chat_session, 
    get_list_of_chat_sessions, 
    get_conversation_history_for_user,
)
from app.db_models.chats import ChatSessionsORM, UserMessagesORM, AIResponsesORM


class TestCreateChatSession:
    """Test cases for create_chat_session function"""
    
    def test_create_chat_session_success(self):
        """Test successful chat session creation"""
        # Arrange
        title = "Test Chat Session"
        user_id = uuid4()
        mock_session = MagicMock()
        mock_chat = ChatSessionsORM(
            id=uuid4(),
            user_id=user_id,
            title=title,
            is_active=True,
            message_count=0,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            deleted_at=None
        )
        
        with patch('app.db_interface.chats.Session') as mock_session_class:
            mock_session_instance = mock_session_class.return_value.__enter__.return_value
            mock_session_instance.add = Mock()
            mock_session_instance.commit = Mock()
            mock_session_instance.refresh = Mock()
            
            # Act
            result = create_chat_session(title, user_id)
            
            # Assert
            mock_session_instance.add.assert_called_once()
            mock_session_instance.commit.assert_called_once()
            mock_session_instance.refresh.assert_called_once()
            
            # Verify the created chat session has correct attributes
            added_chat = mock_session_instance.add.call_args[0][0]
            assert isinstance(added_chat, ChatSessionsORM)
            assert added_chat.user_id == user_id
            assert added_chat.title == title
            assert added_chat.is_active is True
            assert added_chat.message_count == 0

    def test_create_chat_session_with_none_title(self):
        """Test chat session creation with None title"""
        # Arrange
        title = None
        user_id = uuid4()
        
        with patch('app.db_interface.chats.Session') as mock_session_class:
            mock_session_instance = mock_session_class.return_value.__enter__.return_value
            mock_session_instance.add = Mock()
            mock_session_instance.commit = Mock()
            mock_session_instance.refresh = Mock()
            
            # Act
            result = create_chat_session(title, user_id)
            
            # Assert
            added_chat = mock_session_instance.add.call_args[0][0]
            assert added_chat.title is None

    def test_create_chat_session_database_error(self):
        """Test chat session creation with database error"""
        # Arrange
        title = "Test Chat"
        user_id = uuid4()
        
        with patch('app.db_interface.chats.Session') as mock_session_class:
            mock_session_instance = mock_session_class.return_value.__enter__.return_value
            mock_session_instance.add.side_effect = Exception("Database error")
            
            # Act & Assert
            with pytest.raises(Exception) as exc_info:
                create_chat_session(title, user_id)
            
            assert str(exc_info.value) == "Database error"

    @patch('app.db_interface.chats.logger')
    def test_create_chat_session_logs_error(self, mock_logger):
        """Test that errors are properly logged"""
        # Arrange
        title = "Test Chat"
        user_id = uuid4()
        
        with patch('app.db_interface.chats.Session') as mock_session_class:
            mock_session_instance = mock_session_class.return_value.__enter__.return_value
            mock_session_instance.add.side_effect = Exception("Database error")
            
            # Act & Assert
            with pytest.raises(Exception):
                create_chat_session(title, user_id)
            
            mock_logger.error.assert_called_once_with(
                f"Error occured while trying to create the chat session for user: {user_id}"
            )


class TestGetChatSession:
    """Test cases for get_chat_session_meta function"""
    
    def test_get_chat_session_meta_success(self):
        """Test successful retrieval of chat session metadata"""
        # Arrange
        chat_id = uuid4()
        user_id = uuid4()
        mock_chat = ChatSessionsORM(
            id=chat_id,
            user_id=uuid4(),
            title="Test Chat",
            is_active=True,
            message_count=5,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            deleted_at=None
        )
        
        with patch('app.db_interface.chats.Session') as mock_session_class:
            mock_session_instance = mock_session_class.return_value.__enter__.return_value
            mock_query = mock_session_instance.query.return_value
            mock_filter = mock_query.filter.return_value
            mock_filter.first.return_value = mock_chat
            
            # Act
            result = get_chat_session(chat_id, user_id)
            
            # Assert
            assert result == mock_chat
            mock_session_instance.query.assert_called_once_with(ChatSessionsORM)

    def test_get_chat_session_not_found(self):
        """Test retrieval when chat session doesn't exist"""
        # Arrange
        chat_id = uuid4()
        user_id = uuid4()
        
        with patch('app.db_interface.chats.Session') as mock_session_class:
            mock_session_instance = mock_session_class.return_value.__enter__.return_value
            mock_query = mock_session_instance.query.return_value
            mock_filter = mock_query.filter.return_value
            mock_filter.first.return_value = None
            
            # Act
            result = get_chat_session(chat_id, user_id)
            
            # Assert
            assert result is None

    @patch('app.db_interface.chats.logger')
    def test_get_chat_session_logs_not_found(self, mock_logger):
        """Test that missing chat session is properly logged"""
        # Arrange
        chat_id = uuid4()
        user_id = uuid4()
        
        with patch('app.db_interface.chats.Session') as mock_session_class:
            mock_session_instance = mock_session_class.return_value.__enter__.return_value
            mock_query = mock_session_instance.query.return_value
            mock_filter = mock_query.filter.return_value
            mock_filter.first.return_value = None
            
            # Act
            result = get_chat_session(chat_id, user_id)
            
            # Assert
            mock_logger.info.assert_called_once_with(
                f"No chat session found with the matching id: {chat_id}"
            )

    def test_get_chat_session_database_error(self):
        """Test chat session retrieval with database error"""
        # Arrange
        chat_id = uuid4()
        user_id = uuid4()
        
        with patch('app.db_interface.chats.Session') as mock_session_class:
            mock_session_instance = mock_session_class.return_value.__enter__.return_value
            mock_session_instance.query.side_effect = Exception("Database error")
            
            # Act & Assert
            with pytest.raises(Exception) as exc_info:
                get_chat_session(chat_id, user_id)
            
            assert str(exc_info.value) == "Database error"

    @patch('app.db_interface.chats.logger')
    def test_get_chat_session_logs_error(self, mock_logger):
        """Test that errors are properly logged"""
        # Arrange
        chat_id = uuid4()
        user_id = uuid4()
        
        with patch('app.db_interface.chats.Session') as mock_session_class:
            mock_session_instance = mock_session_class.return_value.__enter__.return_value
            mock_session_instance.query.side_effect = Exception("Database error")
            
            # Act & Assert
            with pytest.raises(Exception):
                get_chat_session(chat_id, user_id)
            
            mock_logger.error.assert_called_once_with(
                f"Error occured, trying to obtain chat session with id: {chat_id}"
            )

    def test_get_chat_session_filter_called_correctly(self):
        """Test that the database filter is called with correct parameters"""
        # Arrange
        chat_id = uuid4()
        user_id = uuid4()
        
        with patch('app.db_interface.chats.Session') as mock_session_class:
            mock_session_instance = mock_session_class.return_value.__enter__.return_value
            mock_query = mock_session_instance.query.return_value
            mock_filter = mock_query.filter.return_value
            mock_filter.first.return_value = None
            
            # Act
            get_chat_session(chat_id, user_id)
            
            # Assert
            mock_query.filter.assert_called_once()
            # Verify that the filter was called with the correct conditions
            # Should filter by: id, user_id, and deleted_at is None
            filter_args = mock_query.filter.call_args[0]
            assert len(filter_args) == 3  # Three filter conditions for security
            # The filter condition should compare ChatSessionsORM.id == chat_id


class TestGetListOfChatSessions:
    """Test cases for get_list_of_chat_sessions function"""

    def test_get_list_of_chat_sessions_success_default_params(self):
        """Test successful retrieval with default pagination parameters"""
        # Arrange
        user_id = uuid4()
        mock_chat_1 = ChatSessionsORM(
            id=uuid4(),
            user_id=user_id,
            title="Chat 1",
            is_active=True,
            message_count=3,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            deleted_at=None
        )
        mock_chat_2 = ChatSessionsORM(
            id=uuid4(),
            user_id=user_id,
            title="Chat 2",
            is_active=True,
            message_count=1,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            deleted_at=None
        )
        mock_sessions = [mock_chat_1, mock_chat_2]

        with patch('app.db_interface.chats.Session') as mock_session_class:
            mock_session_instance = mock_session_class.return_value.__enter__.return_value
            mock_query = mock_session_instance.query.return_value
            mock_filter = mock_query.filter.return_value
            mock_filter.count.return_value = 2  # Total count
            mock_order_by = mock_filter.order_by.return_value
            mock_offset = mock_order_by.offset.return_value
            mock_limit = mock_offset.limit.return_value
            mock_limit.all.return_value = mock_sessions

            # Act
            result_sessions, total_count = get_list_of_chat_sessions(user_id)

            # Assert
            assert result_sessions == mock_sessions
            assert total_count == 2
            mock_session_instance.query.assert_called_once_with(ChatSessionsORM)
            mock_filter.count.assert_called_once()
            mock_filter.order_by.assert_called_once()
            mock_order_by.offset.assert_called_once_with(0)  # Default page 1
            mock_offset.limit.assert_called_once_with(20)  # Default page_size

    def test_get_list_of_chat_sessions_with_custom_pagination(self):
        """Test retrieval with custom pagination parameters"""
        # Arrange
        user_id = uuid4()
        page = 3
        page_size = 5
        expected_offset = (page - 1) * page_size  # (3-1) * 5 = 10
        mock_sessions = [ChatSessionsORM(id=uuid4(), user_id=user_id, title=f"Chat {i}") for i in range(5)]

        with patch('app.db_interface.chats.Session') as mock_session_class:
            mock_session_instance = mock_session_class.return_value.__enter__.return_value
            mock_query = mock_session_instance.query.return_value
            mock_filter = mock_query.filter.return_value
            mock_filter.count.return_value = 25  # Total count
            mock_order_by = mock_filter.order_by.return_value
            mock_offset = mock_order_by.offset.return_value
            mock_limit = mock_offset.limit.return_value
            mock_limit.all.return_value = mock_sessions

            # Act
            result_sessions, total_count = get_list_of_chat_sessions(user_id, page, page_size)

            # Assert
            assert result_sessions == mock_sessions
            assert total_count == 25
            mock_order_by.offset.assert_called_once_with(expected_offset)
            mock_offset.limit.assert_called_once_with(page_size)

    def test_get_list_of_chat_sessions_empty_result(self):
        """Test retrieval when no chat sessions exist"""
        # Arrange
        user_id = uuid4()

        with patch('app.db_interface.chats.Session') as mock_session_class:
            mock_session_instance = mock_session_class.return_value.__enter__.return_value
            mock_query = mock_session_instance.query.return_value
            mock_filter = mock_query.filter.return_value
            mock_filter.count.return_value = 0
            mock_order_by = mock_filter.order_by.return_value
            mock_offset = mock_order_by.offset.return_value
            mock_limit = mock_offset.limit.return_value
            mock_limit.all.return_value = []

            # Act
            result_sessions, total_count = get_list_of_chat_sessions(user_id)

            # Assert
            assert result_sessions == []
            assert total_count == 0
            mock_filter.count.assert_called_once()
            mock_limit.all.assert_called_once()

    def test_get_list_of_chat_sessions_correct_filters(self):
        """Test that correct database filters are applied"""
        # Arrange
        user_id = uuid4()

        with patch('app.db_interface.chats.Session') as mock_session_class:
            mock_session_instance = mock_session_class.return_value.__enter__.return_value
            mock_query = mock_session_instance.query.return_value
            mock_filter = mock_query.filter.return_value
            mock_filter.count.return_value = 0
            mock_order_by = mock_filter.order_by.return_value
            mock_offset = mock_order_by.offset.return_value
            mock_limit = mock_offset.limit.return_value
            mock_limit.all.return_value = []

            # Act
            get_list_of_chat_sessions(user_id)

            # Assert
            mock_session_instance.query.assert_called_once_with(ChatSessionsORM)
            mock_query.filter.assert_called_once()
            # Verify filter includes user_id and deleted_at is None
            filter_args = mock_query.filter.call_args[0]
            assert len(filter_args) == 2  # user_id and deleted_at filters

    def test_get_list_of_chat_sessions_correct_ordering(self):
        """Test that results are ordered correctly (most recent first)"""
        # Arrange
        user_id = uuid4()

        with patch('app.db_interface.chats.Session') as mock_session_class:
            mock_session_instance = mock_session_class.return_value.__enter__.return_value
            mock_query = mock_session_instance.query.return_value
            mock_filter = mock_query.filter.return_value
            mock_filter.count.return_value = 0
            mock_order_by = mock_filter.order_by.return_value
            mock_offset = mock_order_by.offset.return_value
            mock_limit = mock_offset.limit.return_value
            mock_limit.all.return_value = []

            # Act
            get_list_of_chat_sessions(user_id)

            # Assert
            mock_filter.order_by.assert_called_once()
            # Would ideally check that it's ordering by created_at desc, but that's hard to verify in mock

    def test_get_list_of_chat_sessions_database_error(self):
        """Test chat sessions retrieval with database error"""
        # Arrange
        user_id = uuid4()

        with patch('app.db_interface.chats.Session') as mock_session_class:
            mock_session_instance = mock_session_class.return_value.__enter__.return_value
            mock_session_instance.query.side_effect = Exception("Database connection failed")

            # Act & Assert
            with pytest.raises(Exception) as exc_info:
                get_list_of_chat_sessions(user_id)

            assert str(exc_info.value) == "Database connection failed"

    @patch('app.db_interface.chats.logger')
    def test_get_list_of_chat_sessions_logs_error(self, mock_logger):
        """Test that errors are properly logged"""
        # Arrange
        user_id = uuid4()

        with patch('app.db_interface.chats.Session') as mock_session_class:
            mock_session_instance = mock_session_class.return_value.__enter__.return_value
            mock_session_instance.query.side_effect = Exception("Database error")

            # Act & Assert
            with pytest.raises(Exception):
                get_list_of_chat_sessions(user_id)

            mock_logger.error.assert_called_once_with(
                f"Error obtaining paginated chat sessions for user: {user_id}"
            )

    def test_get_list_of_chat_sessions_pagination_edge_cases(self):
        """Test pagination with edge case parameters"""
        # Arrange
        user_id = uuid4()
        page = 1
        page_size = 1  # Minimum page size

        with patch('app.db_interface.chats.Session') as mock_session_class:
            mock_session_instance = mock_session_class.return_value.__enter__.return_value
            mock_query = mock_session_instance.query.return_value
            mock_filter = mock_query.filter.return_value
            mock_filter.count.return_value = 100
            mock_order_by = mock_filter.order_by.return_value
            mock_offset = mock_order_by.offset.return_value
            mock_limit = mock_offset.limit.return_value
            mock_limit.all.return_value = [ChatSessionsORM(id=uuid4(), user_id=user_id, title="Single Chat")]

            # Act
            result_sessions, total_count = get_list_of_chat_sessions(user_id, page, page_size)

            # Assert
            assert len(result_sessions) == 1
            assert total_count == 100
            mock_order_by.offset.assert_called_once_with(0)  # First page
            mock_offset.limit.assert_called_once_with(1)  # Single item

    def test_get_list_of_chat_sessions_large_page_number(self):
        """Test retrieval with large page number (beyond available data)"""
        # Arrange
        user_id = uuid4()
        page = 100  # Very large page number
        page_size = 20
        expected_offset = (page - 1) * page_size  # 99 * 20 = 1980

        with patch('app.db_interface.chats.Session') as mock_session_class:
            mock_session_instance = mock_session_class.return_value.__enter__.return_value
            mock_query = mock_session_instance.query.return_value
            mock_filter = mock_query.filter.return_value
            mock_filter.count.return_value = 50  # Total count less than offset
            mock_order_by = mock_filter.order_by.return_value
            mock_offset = mock_order_by.offset.return_value
            mock_limit = mock_offset.limit.return_value
            mock_limit.all.return_value = []  # No results for this page

            # Act
            result_sessions, total_count = get_list_of_chat_sessions(user_id, page, page_size)

            # Assert
            assert result_sessions == []
            assert total_count == 50
            mock_order_by.offset.assert_called_once_with(expected_offset)
            mock_offset.limit.assert_called_once_with(page_size)
 