"""Tests for agent quota validation in app.services.chat_service module"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from uuid import uuid4
from datetime import datetime

from fastapi import status
from fastapi.responses import StreamingResponse

from app.services.chat_service import ChatService
from app.db_models.users import UsersORM
from app.db_models.organizations import OrganizationsORM


class TestValidateAgentQuota:
    """Test cases for _validate_agent_quota method"""

    @pytest.fixture
    def chat_service(self):
        """Create a ChatService instance for testing"""
        return ChatService()

    @pytest.fixture
    def sample_user(self):
        """Create a sample user with available agent quota"""
        return UsersORM(
            id=uuid4(),
            auth0_sub="auth0|123456789",
            email="test@example.com",
            agent_quota=10,
            agent_quota_used=5,
            is_active=True
        )

    @pytest.fixture
    def sample_user_quota_exhausted(self):
        """Create a sample user with exhausted agent quota"""
        return UsersORM(
            id=uuid4(),
            auth0_sub="auth0|123456789",
            email="test@example.com",
            agent_quota=10,
            agent_quota_used=10,  # Equal to quota
            is_active=True
        )

    @pytest.fixture
    def sample_user_quota_exceeded(self):
        """Create a sample user with exceeded agent quota"""
        return UsersORM(
            id=uuid4(),
            auth0_sub="auth0|123456789",
            email="test@example.com",
            agent_quota=10,
            agent_quota_used=15,  # Greater than quota
            is_active=True
        )

    @pytest.mark.asyncio
    @patch('app.services.chat_service.get_user_by_id')
    async def test_validate_agent_quota_success(self, mock_get_user, chat_service, sample_user):
        """Test successful agent quota validation when user has available quota"""
        # Arrange
        mock_get_user.return_value = sample_user
        user_id = sample_user.id
        user_sub = "auth0|123456789"

        # Act
        result = await chat_service._validate_agent_quota(user_id, user_sub)

        # Assert
        assert result is None  # No error response means validation passed
        mock_get_user.assert_called_once_with(user_id=user_id)

    @pytest.mark.asyncio
    @patch('app.services.chat_service.get_user_by_id')
    async def test_validate_agent_quota_exhausted(self, mock_get_user, chat_service, sample_user_quota_exhausted):
        """Test agent quota validation when quota is exhausted (equal)"""
        # Arrange
        mock_get_user.return_value = sample_user_quota_exhausted
        user_id = sample_user_quota_exhausted.id
        user_sub = "auth0|123456789"

        # Act
        result = await chat_service._validate_agent_quota(user_id, user_sub)

        # Assert
        assert result is not None
        assert isinstance(result, StreamingResponse)
        assert result.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.asyncio
    @patch('app.services.chat_service.get_user_by_id')
    async def test_validate_agent_quota_exceeded(self, mock_get_user, chat_service, sample_user_quota_exceeded):
        """Test agent quota validation when quota is exceeded (greater than)"""
        # Arrange
        mock_get_user.return_value = sample_user_quota_exceeded
        user_id = sample_user_quota_exceeded.id
        user_sub = "auth0|123456789"

        # Act
        result = await chat_service._validate_agent_quota(user_id, user_sub)

        # Assert
        assert result is not None
        assert isinstance(result, StreamingResponse)
        assert result.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.asyncio
    @patch('app.services.chat_service.get_user_by_id')
    async def test_validate_agent_quota_user_not_found(self, mock_get_user, chat_service):
        """Test agent quota validation when user is not found"""
        # Arrange
        mock_get_user.return_value = None
        user_id = uuid4()
        user_sub = "auth0|nonexistent"

        # Act
        result = await chat_service._validate_agent_quota(user_id, user_sub)

        # Assert
        assert result is not None
        assert isinstance(result, StreamingResponse)
        assert result.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    @pytest.mark.asyncio
    @patch('app.services.chat_service.get_user_by_id')
    async def test_validate_agent_quota_database_error(self, mock_get_user, chat_service):
        """Test agent quota validation with database error"""
        # Arrange
        mock_get_user.side_effect = Exception("Database connection failed")
        user_id = uuid4()
        user_sub = "auth0|123456789"

        # Act
        result = await chat_service._validate_agent_quota(user_id, user_sub)

        # Assert
        assert result is not None
        assert isinstance(result, StreamingResponse)
        assert result.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    @pytest.mark.asyncio
    @patch('app.services.chat_service.get_user_by_id')
    async def test_validate_agent_quota_edge_case_one_remaining(self, mock_get_user, chat_service):
        """Test agent quota validation when user has exactly 1 request remaining"""
        # Arrange
        user = UsersORM(
            id=uuid4(),
            auth0_sub="auth0|123456789",
            email="test@example.com",
            agent_quota=10,
            agent_quota_used=9,  # One remaining
            is_active=True
        )
        mock_get_user.return_value = user

        # Act
        result = await chat_service._validate_agent_quota(user.id, "auth0|123456789")

        # Assert
        assert result is None  # Should pass - still has 1 remaining

    @pytest.mark.asyncio
    @patch('app.services.chat_service.get_user_by_id')
    async def test_validate_agent_quota_fresh_user(self, mock_get_user, chat_service):
        """Test agent quota validation for a fresh user with no usage"""
        # Arrange
        user = UsersORM(
            id=uuid4(),
            auth0_sub="auth0|newuser",
            email="newuser@example.com",
            agent_quota=10,
            agent_quota_used=0,  # No usage yet
            is_active=True
        )
        mock_get_user.return_value = user

        # Act
        result = await chat_service._validate_agent_quota(user.id, "auth0|newuser")

        # Assert
        assert result is None  # Should pass - full quota available


class TestAgentQuotaIncrement:
    """Test cases for agent quota increment in streaming completion"""

    @pytest.fixture
    def chat_service(self):
        """Create a ChatService instance for testing"""
        return ChatService()

    @patch('app.db_interface.users.Session')
    def test_increment_agent_quota_called(self, mock_session_class):
        """Test that increment_user_agent_quota_used is called correctly"""
        from app.db_interface.users import increment_user_agent_quota_used
        
        # Arrange
        user_id = uuid4()
        mock_user = UsersORM(
            id=user_id,
            auth0_sub="auth0|123",
            email="test@example.com",
            agent_quota=10,
            agent_quota_used=5
        )
        
        mock_session_instance = mock_session_class.return_value.__enter__.return_value
        mock_query = mock_session_instance.query.return_value
        mock_filter = mock_query.filter.return_value
        mock_filter.first.return_value = mock_user
        mock_session_instance.commit = Mock()
        mock_session_instance.refresh = Mock()

        # Act
        result = increment_user_agent_quota_used(user_id)

        # Assert
        assert mock_user.agent_quota_used == 6  # Incremented by 1
        assert result == mock_user
        mock_session_instance.commit.assert_called_once()


class TestAgentQuotaValidationIntegration:
    """Integration-style tests for agent quota in chat service"""

    def test_quota_comparison_logic(self):
        """Test the quota comparison logic directly"""
        # Test cases for quota validation
        test_cases = [
            # (agent_quota, agent_quota_used, should_pass)
            (10, 0, True),   # Fresh user
            (10, 5, True),   # Half used
            (10, 9, True),   # One remaining
            (10, 10, False), # Exactly exhausted
            (10, 11, False), # Exceeded
            (10, 15, False), # Far exceeded
            (5, 4, True),    # Different quota
            (5, 5, False),   # Different quota exhausted
            (100, 99, True), # Large quota
            (100, 100, False), # Large quota exhausted
        ]

        for agent_quota, agent_quota_used, should_pass in test_cases:
            is_valid = agent_quota_used < agent_quota
            assert is_valid == should_pass, f"Failed for quota={agent_quota}, used={agent_quota_used}"

    def test_error_message_content(self):
        """Test that error messages are appropriate"""
        chat_service = ChatService()

        # Test error stream creation
        error_msg = "You have used all your agent mode requests."
        error_event = chat_service.create_stream_error_event(error_msg)

        assert "stream.error" in error_event
        assert error_msg in error_event


class TestValidateOrganizationQuotaCheckQuotaFlag:
    """Tests for the check_quota flag on _validate_organization_quota.

    Verifies that ask mode (check_quota=True) gates on org-level quota and
    agent mode (check_quota=False) bypasses the org-level gate. The org row
    must still be returned in both cases because downstream code needs
    user_org.access_level for RAG channel selection and user_org.id for
    tracing.
    """

    @pytest.fixture
    def chat_service(self):
        return ChatService()

    @pytest.fixture
    def org_quota_exhausted(self):
        return OrganizationsORM(
            id=uuid4(),
            name="Test Org",
            access_level="BASIC",
            question_quota=20,
            questions_used=20,
            rocportal_status=True,
        )

    @pytest.mark.asyncio
    @patch('app.services.chat_service.get_organization_by_user_id')
    async def test_ask_mode_blocked_when_org_quota_exhausted(
        self, mock_get_org, chat_service, org_quota_exhausted,
    ):
        """Ask mode (check_quota=True) must reject when org quota is exhausted."""
        mock_get_org.return_value = org_quota_exhausted

        error, org = await chat_service._validate_organization_quota(
            user_id=uuid4(), user_sub="auth0|123", check_quota=True,
        )

        assert error is not None
        assert isinstance(error, StreamingResponse)
        assert error.status_code == status.HTTP_400_BAD_REQUEST
        assert org is None

    @pytest.mark.asyncio
    @patch('app.services.chat_service.get_organization_by_user_id')
    async def test_agent_mode_bypasses_org_quota_when_exhausted(
        self, mock_get_org, chat_service, org_quota_exhausted,
    ):
        """Agent mode (check_quota=False) must NOT reject when org quota is
        exhausted — agent mode is gated solely by per-user agent_quota in
        _validate_agent_quota. The org row must still be returned for
        downstream use."""
        mock_get_org.return_value = org_quota_exhausted

        error, org = await chat_service._validate_organization_quota(
            user_id=uuid4(), user_sub="auth0|123", check_quota=False,
        )

        assert error is None
        assert org is org_quota_exhausted

    @pytest.mark.asyncio
    @patch('app.services.chat_service.get_organization_by_user_id')
    async def test_default_check_quota_is_true(
        self, mock_get_org, chat_service, org_quota_exhausted,
    ):
        """Default behavior (no check_quota arg) must remain quota-checking,
        so existing callers stay safe."""
        mock_get_org.return_value = org_quota_exhausted

        error, org = await chat_service._validate_organization_quota(
            user_id=uuid4(), user_sub="auth0|123",
        )

        assert error is not None
        assert org is None
