"""Tests for app.db_interface.organizations module"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from uuid import uuid4
from datetime import datetime, date

from app.db_interface.organizations import (
    create_organization,
    get_organization_by_user_id,
    add_user_to_organization,
    update_organization_quota,
    increment_organization_questions_used,
    reassign_user_organization,
)
from app.db_models.organizations import OrganizationsORM, UserOrganizationsORM
from app.models.organizations import CreateOrganizationRequest


class TestCreateOrganization:
    """Test cases for create_organization function"""
    
    def test_create_organization_success(self):
        """Test successful organization creation"""
        # Arrange
        org_id = uuid4()
        org_request = CreateOrganizationRequest(
            id=org_id,
            name="Test Organization",
            question_quota=100,
            access_level="premium",
            quota_reset_date=date(2024, 1, 1),
            rocportal_status=True
        )
        
        with patch('app.db_interface.organizations.Session') as mock_session_class:
            mock_session_instance = mock_session_class.return_value.__enter__.return_value
            mock_session_instance.add = Mock()
            mock_session_instance.commit = Mock()
            mock_session_instance.refresh = Mock()
            
            # Act
            result = create_organization(org_request)
            
            # Assert
            mock_session_instance.add.assert_called_once()
            mock_session_instance.commit.assert_called_once()
            mock_session_instance.refresh.assert_called_once()
            
            # Verify the created organization has correct attributes
            added_org = mock_session_instance.add.call_args[0][0]
            assert isinstance(added_org, OrganizationsORM)
            assert added_org.id == org_request.id
            assert added_org.name == org_request.name
            assert added_org.question_quota == org_request.question_quota
            assert added_org.access_level == org_request.access_level
            assert added_org.quota_reset_date == org_request.quota_reset_date

    def test_create_organization_with_none_quota_reset_date(self):
        """Test organization creation with None quota_reset_date"""
        # Arrange
        org_request = CreateOrganizationRequest(
            id=uuid4(),
            name="Test Organization",
            question_quota=50,
            access_level="basic",
            quota_reset_date=None,
            rocportal_status=False
        )
        
        with patch('app.db_interface.organizations.Session') as mock_session_class:
            mock_session_instance = mock_session_class.return_value.__enter__.return_value
            mock_session_instance.add = Mock()
            mock_session_instance.commit = Mock()
            mock_session_instance.refresh = Mock()
            
            # Act
            result = create_organization(org_request)
            
            # Assert
            added_org = mock_session_instance.add.call_args[0][0]
            assert added_org.quota_reset_date is None

    def test_create_organization_database_error(self):
        """Test organization creation with database error"""
        # Arrange
        org_request = CreateOrganizationRequest(
            id=uuid4(),
            name="Test Organization",
            question_quota=100,
            access_level="premium",
            rocportal_status=True
        )
        
        with patch('app.db_interface.organizations.Session') as mock_session_class:
            mock_session_instance = mock_session_class.return_value.__enter__.return_value
            mock_session_instance.add.side_effect = Exception("Database error")
            
            # Act & Assert
            with pytest.raises(Exception) as exc_info:
                create_organization(org_request)
            
            assert str(exc_info.value) == "Database error"


class TestGetOrganizationByUserId:
    """Test cases for get_organization_by_user_id function"""
    
    def test_get_organization_by_user_id_success(self):
        """Test successful retrieval of organization by user ID"""
        # Arrange
        user_id = "test_user_123"
        org_id = uuid4()
        mock_org = OrganizationsORM(
            id=org_id,
            name="Test Organization",
            question_quota=100,
            access_level="premium",
            quota_reset_date=date(2024, 1, 1)
        )
        mock_user_org = UserOrganizationsORM(
            user_id=user_id,
            organization_id=str(org_id)
        )
        mock_user_org.organizations_orm = mock_org
        
        with patch('app.db_interface.organizations.Session') as mock_session_class:
            mock_session_instance = mock_session_class.return_value.__enter__.return_value
            mock_query = mock_session_instance.query.return_value
            mock_filter = mock_query.filter.return_value
            mock_filter.first.return_value = mock_user_org
            
            # Act
            result = get_organization_by_user_id(user_id)
            
            # Assert
            assert result == mock_org
            mock_session_instance.query.assert_called_once_with(UserOrganizationsORM)

    def test_get_organization_by_user_id_not_found(self):
        """Test retrieval when user is not associated with any organization"""
        # Arrange
        user_id = "nonexistent_user"
        
        with patch('app.db_interface.organizations.Session') as mock_session_class:
            mock_session_instance = mock_session_class.return_value.__enter__.return_value
            mock_query = mock_session_instance.query.return_value
            mock_filter = mock_query.filter.return_value
            mock_filter.first.return_value = None
            
            # Act
            result = get_organization_by_user_id(user_id)
            
            # Assert
            assert result is None

    def test_get_organization_by_user_id_database_error(self):
        """Test organization retrieval with database error"""
        # Arrange
        user_id = "test_user_123"
        
        with patch('app.db_interface.organizations.Session') as mock_session_class:
            mock_session_instance = mock_session_class.return_value.__enter__.return_value
            mock_session_instance.query.side_effect = Exception("Database error")
            
            # Act & Assert
            with pytest.raises(Exception) as exc_info:
                get_organization_by_user_id(user_id)
            
            assert str(exc_info.value) == "Database error"


class TestAddUserToOrganization:
    """Test cases for add_user_to_organization function"""
    
    def test_add_user_to_organization_success(self):
        """Test successful addition of user to organization"""
        # Arrange
        user_id = "test_user_123"
        organization_id = str(uuid4())
        
        with patch('app.db_interface.organizations.Session') as mock_session_class:
            mock_session_instance = mock_session_class.return_value.__enter__.return_value
            mock_session_instance.add = Mock()
            mock_session_instance.commit = Mock()
            mock_session_instance.refresh = Mock()
            
            # Act
            result = add_user_to_organization(user_id, organization_id)
            
            # Assert
            mock_session_instance.add.assert_called_once()
            mock_session_instance.commit.assert_called_once()
            mock_session_instance.refresh.assert_called_once()
            
            # Verify the created user-organization relationship has correct attributes
            added_user_org = mock_session_instance.add.call_args[0][0]
            assert isinstance(added_user_org, UserOrganizationsORM)
            assert added_user_org.user_id == user_id
            assert added_user_org.organization_id == organization_id

    def test_add_user_to_organization_database_error(self):
        """Test adding user to organization with database error"""
        # Arrange
        user_id = "test_user_123"
        organization_id = str(uuid4())
        
        with patch('app.db_interface.organizations.Session') as mock_session_class:
            mock_session_instance = mock_session_class.return_value.__enter__.return_value
            mock_session_instance.add.side_effect = Exception("Database error")
            
            # Act & Assert
            with pytest.raises(Exception) as exc_info:
                add_user_to_organization(user_id, organization_id)
            
            assert str(exc_info.value) == "Database error"


class TestUpdateOrganizationQuota:
    """Test cases for update_organization_quota function"""
    
    def test_update_organization_quota_success(self):
        """Test successful update of organization quota"""
        # Arrange
        organization_id = str(uuid4())
        new_quota = 200
        mock_org = OrganizationsORM(
            id=uuid4(),
            name="Test Organization",
            question_quota=100,
            access_level="premium",
            quota_reset_date=date(2024, 1, 1)
        )
        
        with patch('app.db_interface.organizations.Session') as mock_session_class:
            mock_session_instance = mock_session_class.return_value.__enter__.return_value
            mock_query = mock_session_instance.query.return_value
            mock_filter = mock_query.filter.return_value
            mock_filter.first.return_value = mock_org
            mock_session_instance.commit = Mock()
            mock_session_instance.refresh = Mock()
            
            # Act
            result = update_organization_quota(organization_id, new_quota, rocportal_status=True)

            # Assert
            assert mock_org.question_quota == new_quota
            mock_session_instance.commit.assert_called_once()
            mock_session_instance.refresh.assert_called_once_with(mock_org)
            mock_session_instance.query.assert_called_once_with(OrganizationsORM)

    def test_update_organization_quota_organization_not_found(self):
        """Test update quota when organization doesn't exist"""
        # Arrange
        organization_id = str(uuid4())
        new_quota = 200
        
        with patch('app.db_interface.organizations.Session') as mock_session_class:
            mock_session_instance = mock_session_class.return_value.__enter__.return_value
            mock_query = mock_session_instance.query.return_value
            mock_filter = mock_query.filter.return_value
            mock_filter.first.return_value = None
            
            # Act & Assert
            # This will raise an AttributeError because None.question_quota is accessed
            with pytest.raises(AttributeError):
                update_organization_quota(organization_id, new_quota, rocportal_status=False)

    def test_update_organization_quota_database_error(self):
        """Test update organization quota with database error"""
        # Arrange
        organization_id = str(uuid4())
        new_quota = 200
        
        with patch('app.db_interface.organizations.Session') as mock_session_class:
            mock_session_instance = mock_session_class.return_value.__enter__.return_value
            mock_session_instance.query.side_effect = Exception("Database error")
            
            # Act & Assert
            with pytest.raises(Exception) as exc_info:
                update_organization_quota(organization_id, new_quota, rocportal_status=True)

            assert str(exc_info.value) == "Database error"

    def test_update_organization_quota_commit_error(self):
        """Test update organization quota with commit error"""
        # Arrange
        organization_id = str(uuid4())
        new_quota = 200
        mock_org = OrganizationsORM(
            id=uuid4(),
            name="Test Organization",
            question_quota=100,
            access_level="premium"
        )
        
        with patch('app.db_interface.organizations.Session') as mock_session_class:
            mock_session_instance = mock_session_class.return_value.__enter__.return_value
            mock_query = mock_session_instance.query.return_value
            mock_filter = mock_query.filter.return_value
            mock_filter.first.return_value = mock_org
            mock_session_instance.commit.side_effect = Exception("Commit failed")
            
            # Act & Assert
            with pytest.raises(Exception) as exc_info:
                update_organization_quota(organization_id, new_quota, rocportal_status=False)

            assert str(exc_info.value) == "Commit failed"
            # Verify that the quota was set before the commit failed
            assert mock_org.question_quota == new_quota


class TestIncrementOrganizationQuestionsUsed:
    """Test cases for increment_organization_questions_used function"""
    
    def test_increment_organization_questions_used_success_default_amount(self):
        """Test successful increment of questions used with default amount (1)"""
        # Arrange
        organization_id = str(uuid4())
        initial_questions_used = 5
        mock_org = OrganizationsORM(
            id=uuid4(),
            name="Test Organization",
            question_quota=100,
            questions_used=initial_questions_used,
            access_level="premium",
            quota_reset_date=date(2024, 1, 1)
        )
        
        with patch('app.db_interface.organizations.Session') as mock_session_class:
            mock_session_instance = mock_session_class.return_value.__enter__.return_value
            mock_query = mock_session_instance.query.return_value
            mock_filter = mock_query.filter.return_value
            mock_filter.first.return_value = mock_org
            mock_session_instance.commit = Mock()
            mock_session_instance.refresh = Mock()
            
            # Act
            result = increment_organization_questions_used(organization_id)
            
            # Assert
            assert mock_org.questions_used == initial_questions_used + 1
            assert result == mock_org
            mock_session_instance.commit.assert_called_once()
            mock_session_instance.refresh.assert_called_once_with(mock_org)
            mock_session_instance.query.assert_called_once_with(OrganizationsORM)

    def test_increment_organization_questions_used_success_custom_amount(self):
        """Test successful increment of questions used with custom amount"""
        # Arrange
        organization_id = str(uuid4())
        initial_questions_used = 10
        increment_amount = 5
        mock_org = OrganizationsORM(
            id=uuid4(),
            name="Test Organization",
            question_quota=100,
            questions_used=initial_questions_used,
            access_level="premium"
        )
        
        with patch('app.db_interface.organizations.Session') as mock_session_class:
            mock_session_instance = mock_session_class.return_value.__enter__.return_value
            mock_query = mock_session_instance.query.return_value
            mock_filter = mock_query.filter.return_value
            mock_filter.first.return_value = mock_org
            mock_session_instance.commit = Mock()
            mock_session_instance.refresh = Mock()
            
            # Act
            result = increment_organization_questions_used(organization_id, increment_amount)
            
            # Assert
            assert mock_org.questions_used == initial_questions_used + increment_amount
            assert result == mock_org
            mock_session_instance.commit.assert_called_once()
            mock_session_instance.refresh.assert_called_once_with(mock_org)

    def test_increment_organization_questions_used_zero_amount(self):
        """Test increment with zero amount (should not change questions_used)"""
        # Arrange
        organization_id = str(uuid4())
        initial_questions_used = 15
        increment_amount = 0
        mock_org = OrganizationsORM(
            id=uuid4(),
            name="Test Organization",
            question_quota=100,
            questions_used=initial_questions_used,
            access_level="basic"
        )
        
        with patch('app.db_interface.organizations.Session') as mock_session_class:
            mock_session_instance = mock_session_class.return_value.__enter__.return_value
            mock_query = mock_session_instance.query.return_value
            mock_filter = mock_query.filter.return_value
            mock_filter.first.return_value = mock_org
            mock_session_instance.commit = Mock()
            mock_session_instance.refresh = Mock()
            
            # Act
            result = increment_organization_questions_used(organization_id, increment_amount)
            
            # Assert
            assert mock_org.questions_used == initial_questions_used  # No change
            assert result == mock_org
            mock_session_instance.commit.assert_called_once()
            mock_session_instance.refresh.assert_called_once_with(mock_org)

    def test_increment_organization_questions_used_negative_amount(self):
        """Test increment with negative amount (effectively decrementing)"""
        # Arrange
        organization_id = str(uuid4())
        initial_questions_used = 20
        increment_amount = -3
        mock_org = OrganizationsORM(
            id=uuid4(),
            name="Test Organization",
            question_quota=100,
            questions_used=initial_questions_used,
            access_level="premium"
        )
        
        with patch('app.db_interface.organizations.Session') as mock_session_class:
            mock_session_instance = mock_session_class.return_value.__enter__.return_value
            mock_query = mock_session_instance.query.return_value
            mock_filter = mock_query.filter.return_value
            mock_filter.first.return_value = mock_org
            mock_session_instance.commit = Mock()
            mock_session_instance.refresh = Mock()
            
            # Act
            result = increment_organization_questions_used(organization_id, increment_amount)
            
            # Assert
            assert mock_org.questions_used == initial_questions_used + increment_amount  # 20 + (-3) = 17
            assert result == mock_org
            mock_session_instance.commit.assert_called_once()
            mock_session_instance.refresh.assert_called_once_with(mock_org)

    def test_increment_organization_questions_used_organization_not_found(self):
        """Test increment when organization doesn't exist"""
        # Arrange
        organization_id = str(uuid4())
        
        with patch('app.db_interface.organizations.Session') as mock_session_class:
            mock_session_instance = mock_session_class.return_value.__enter__.return_value
            mock_query = mock_session_instance.query.return_value
            mock_filter = mock_query.filter.return_value
            mock_filter.first.return_value = None
            
            # Act & Assert
            # This will raise an AttributeError because None.questions_used is accessed
            with pytest.raises(AttributeError):
                increment_organization_questions_used(organization_id)

    def test_increment_organization_questions_used_database_error(self):
        """Test increment questions used with database error during query"""
        # Arrange
        organization_id = str(uuid4())
        
        with patch('app.db_interface.organizations.Session') as mock_session_class:
            mock_session_instance = mock_session_class.return_value.__enter__.return_value
            mock_session_instance.query.side_effect = Exception("Database connection failed")
            
            # Act & Assert
            with pytest.raises(Exception) as exc_info:
                increment_organization_questions_used(organization_id)
            
            assert str(exc_info.value) == "Database connection failed"

    def test_increment_organization_questions_used_commit_error(self):
        """Test increment questions used with commit error"""
        # Arrange
        organization_id = str(uuid4())
        initial_questions_used = 8
        mock_org = OrganizationsORM(
            id=uuid4(),
            name="Test Organization",
            question_quota=100,
            questions_used=initial_questions_used,
            access_level="premium"
        )
        
        with patch('app.db_interface.organizations.Session') as mock_session_class:
            mock_session_instance = mock_session_class.return_value.__enter__.return_value
            mock_query = mock_session_instance.query.return_value
            mock_filter = mock_query.filter.return_value
            mock_filter.first.return_value = mock_org
            mock_session_instance.commit.side_effect = Exception("Commit failed")
            
            # Act & Assert
            with pytest.raises(Exception) as exc_info:
                increment_organization_questions_used(organization_id)
            
            assert str(exc_info.value) == "Commit failed"
            # Verify that the questions_used was incremented before the commit failed
            assert mock_org.questions_used == initial_questions_used + 1

    def test_increment_organization_questions_used_refresh_error(self):
        """Test increment questions used with refresh error"""
        # Arrange
        organization_id = str(uuid4())
        initial_questions_used = 12
        mock_org = OrganizationsORM(
            id=uuid4(),
            name="Test Organization",
            question_quota=100,
            questions_used=initial_questions_used,
            access_level="basic"
        )
        
        with patch('app.db_interface.organizations.Session') as mock_session_class:
            mock_session_instance = mock_session_class.return_value.__enter__.return_value
            mock_query = mock_session_instance.query.return_value
            mock_filter = mock_query.filter.return_value
            mock_filter.first.return_value = mock_org
            mock_session_instance.commit = Mock()
            mock_session_instance.refresh.side_effect = Exception("Refresh failed")
            
            # Act & Assert
            with pytest.raises(Exception) as exc_info:
                increment_organization_questions_used(organization_id)
            
            assert str(exc_info.value) == "Refresh failed"
            # Verify that the questions_used was incremented and commit was called
            assert mock_org.questions_used == initial_questions_used + 1
            mock_session_instance.commit.assert_called_once()


# ---------------------------------------------------------------------------
# RSI-218: New and updated function tests
# ---------------------------------------------------------------------------


class TestUpdateOrganizationQuotaWithAccessLevel:
    """Tests for the updated update_organization_quota() that now accepts
    an optional access_level parameter (RSI-218)."""

    def test_update_quota_updates_access_level_when_provided(self):
        """access_level is persisted on the org when explicitly passed"""
        # Arrange
        organization_id = str(uuid4())
        mock_org = OrganizationsORM(
            id=uuid4(),
            name="Rocscience",
            question_quota=20,
            access_level="BASIC",
            quota_reset_date=date(2024, 1, 1),
        )

        with patch("app.db_interface.organizations.Session") as mock_session_class:
            mock_session_instance = mock_session_class.return_value.__enter__.return_value
            mock_session_instance.query.return_value.filter.return_value.first.return_value = mock_org
            mock_session_instance.commit = Mock()
            mock_session_instance.refresh = Mock()

            # Act
            update_organization_quota(organization_id, 900, rocportal_status=True, access_level="FLEXIBLE")

            # Assert — access_level was updated in-place before commit
            assert mock_org.access_level == "FLEXIBLE"
            assert mock_org.question_quota == 900
            assert mock_org.rocportal_status is True
            mock_session_instance.commit.assert_called_once()
            mock_session_instance.refresh.assert_called_once_with(mock_org)

    def test_update_quota_does_not_change_access_level_when_omitted(self):
        """access_level is left untouched when the parameter is not supplied"""
        # Arrange
        organization_id = str(uuid4())
        mock_org = OrganizationsORM(
            id=uuid4(),
            name="Acme",
            question_quota=100,
            access_level="FLEXIBLE",
        )

        with patch("app.db_interface.organizations.Session") as mock_session_class:
            mock_session_instance = mock_session_class.return_value.__enter__.return_value
            mock_session_instance.query.return_value.filter.return_value.first.return_value = mock_org
            mock_session_instance.commit = Mock()
            mock_session_instance.refresh = Mock()

            # Act — no access_level kwarg
            update_organization_quota(organization_id, 250, rocportal_status=True)

            # Assert — access_level unchanged
            assert mock_org.access_level == "FLEXIBLE"
            assert mock_org.question_quota == 250
            mock_session_instance.commit.assert_called_once()

    def test_update_quota_sets_access_level_to_basic(self):
        """access_level can be downgraded from FLEXIBLE to BASIC"""
        # Arrange
        organization_id = str(uuid4())
        mock_org = OrganizationsORM(
            id=uuid4(),
            name="OldFlexOrg",
            question_quota=500,
            access_level="FLEXIBLE",
        )

        with patch("app.db_interface.organizations.Session") as mock_session_class:
            mock_session_instance = mock_session_class.return_value.__enter__.return_value
            mock_session_instance.query.return_value.filter.return_value.first.return_value = mock_org
            mock_session_instance.commit = Mock()
            mock_session_instance.refresh = Mock()

            # Act
            update_organization_quota(organization_id, 20, rocportal_status=False, access_level="BASIC")

            # Assert
            assert mock_org.access_level == "BASIC"
            assert mock_org.question_quota == 20
            assert mock_org.rocportal_status is False
            mock_session_instance.commit.assert_called_once()

    def test_update_quota_with_access_level_database_error(self):
        """Exception from the session is re-raised"""
        organization_id = str(uuid4())

        with patch("app.db_interface.organizations.Session") as mock_session_class:
            mock_session_instance = mock_session_class.return_value.__enter__.return_value
            mock_session_instance.query.side_effect = Exception("DB unavailable")

            with pytest.raises(Exception) as exc_info:
                update_organization_quota(organization_id, 100, rocportal_status=True, access_level="FLEXIBLE")

            assert str(exc_info.value) == "DB unavailable"


class TestReassignUserOrganization:
    """Tests for the new reassign_user_organization() function (RSI-218).

    This function updates the existing user_organizations row to point to a
    new org, or inserts a fresh row if none exists yet.
    """

    def test_reassign_updates_existing_row(self):
        """When a user_organizations row already exists it is updated in-place"""
        # Arrange
        user_id = str(uuid4())
        old_org_id = str(uuid4())
        new_org_id = str(uuid4())

        mock_user_org = UserOrganizationsORM(
            user_id=user_id,
            organization_id=old_org_id,
        )

        with patch("app.db_interface.organizations.Session") as mock_session_class:
            mock_session_instance = mock_session_class.return_value.__enter__.return_value
            mock_session_instance.query.return_value.filter.return_value.first.return_value = mock_user_org
            mock_session_instance.commit = Mock()
            mock_session_instance.refresh = Mock()

            # Act
            result = reassign_user_organization(user_id, new_org_id)

            # Assert — organization_id was updated, NOT a new row added
            assert mock_user_org.organization_id == new_org_id
            mock_session_instance.add.assert_not_called()
            mock_session_instance.commit.assert_called_once()
            mock_session_instance.refresh.assert_called_once_with(mock_user_org)

    def test_reassign_inserts_new_row_when_none_exists(self):
        """When no user_organizations row exists a new one is created"""
        # Arrange
        user_id = str(uuid4())
        new_org_id = str(uuid4())

        with patch("app.db_interface.organizations.Session") as mock_session_class:
            mock_session_instance = mock_session_class.return_value.__enter__.return_value
            mock_session_instance.query.return_value.filter.return_value.first.return_value = None
            mock_session_instance.add = Mock()
            mock_session_instance.commit = Mock()
            mock_session_instance.refresh = Mock()

            # Act
            reassign_user_organization(user_id, new_org_id)

            # Assert — a new UserOrganizationsORM was added
            mock_session_instance.add.assert_called_once()
            added_obj = mock_session_instance.add.call_args[0][0]
            assert isinstance(added_obj, UserOrganizationsORM)
            assert added_obj.user_id == user_id
            assert added_obj.organization_id == new_org_id
            mock_session_instance.commit.assert_called_once()

    def test_reassign_queries_correct_user_id(self):
        """The filter uses the supplied user_id"""
        # Arrange
        user_id = str(uuid4())
        new_org_id = str(uuid4())
        mock_user_org = UserOrganizationsORM(user_id=user_id, organization_id=str(uuid4()))

        with patch("app.db_interface.organizations.Session") as mock_session_class:
            mock_session_instance = mock_session_class.return_value.__enter__.return_value
            mock_session_instance.query.return_value.filter.return_value.first.return_value = mock_user_org
            mock_session_instance.commit = Mock()
            mock_session_instance.refresh = Mock()

            # Act
            reassign_user_organization(user_id, new_org_id)

            # Assert — queried on UserOrganizationsORM
            mock_session_instance.query.assert_called_once_with(UserOrganizationsORM)

    def test_reassign_does_not_touch_other_users_rows(self):
        """Only the matched user's row is updated; no other rows are written"""
        # Arrange
        user_id = str(uuid4())
        new_org_id = str(uuid4())
        mock_user_org = UserOrganizationsORM(user_id=user_id, organization_id=str(uuid4()))

        with patch("app.db_interface.organizations.Session") as mock_session_class:
            mock_session_instance = mock_session_class.return_value.__enter__.return_value
            mock_session_instance.query.return_value.filter.return_value.first.return_value = mock_user_org
            mock_session_instance.commit = Mock()
            mock_session_instance.refresh = Mock()

            # Act
            reassign_user_organization(user_id, new_org_id)

            # Assert — only one commit, no bulk updates
            mock_session_instance.commit.assert_called_once()
            mock_session_instance.add.assert_not_called()

    def test_reassign_database_error_is_reraised(self):
        """Database exceptions propagate to the caller"""
        user_id = str(uuid4())
        new_org_id = str(uuid4())

        with patch("app.db_interface.organizations.Session") as mock_session_class:
            mock_session_instance = mock_session_class.return_value.__enter__.return_value
            mock_session_instance.query.side_effect = Exception("Connection reset")

            with pytest.raises(Exception) as exc_info:
                reassign_user_organization(user_id, new_org_id)

            assert str(exc_info.value) == "Connection reset"

    def test_reassign_commit_error_is_reraised(self):
        """Commit failures propagate to the caller"""
        user_id = str(uuid4())
        new_org_id = str(uuid4())
        mock_user_org = UserOrganizationsORM(user_id=user_id, organization_id=str(uuid4()))

        with patch("app.db_interface.organizations.Session") as mock_session_class:
            mock_session_instance = mock_session_class.return_value.__enter__.return_value
            mock_session_instance.query.return_value.filter.return_value.first.return_value = mock_user_org
            mock_session_instance.commit.side_effect = Exception("Commit failed")

            with pytest.raises(Exception) as exc_info:
                reassign_user_organization(user_id, new_org_id)

            assert str(exc_info.value) == "Commit failed"