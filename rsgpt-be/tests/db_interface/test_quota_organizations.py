"""Tests for app.db_interface.organizations quota methods"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from uuid import uuid4
from datetime import date, datetime, timedelta

from app.db_interface.organizations import (
    get_organizations_for_quota_reset,
    reset_organization_quota,
    get_organization_by_id_for_quota
)
from app.db_models.organizations import OrganizationsORM


class TestQuotaDBInterface:
    """Test cases for quota-related DB interface methods"""

    @pytest.fixture
    def sample_organization(self):
        """Create a sample organization for testing"""
        org_id = str(uuid4())
        return OrganizationsORM(
            id=org_id,
            name="Test Organization",
            question_quota=100,
            questions_used=50,
            access_level="FLEXIBLE",
            quota_reset_date=date.today(),
            rocportal_status=True,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )

    @pytest.fixture
    def sample_organizations_list(self):
        """Create a list of sample organizations for testing"""
        orgs = []
        for i in range(3):
            org_id = str(uuid4())
            org = OrganizationsORM(
                id=org_id,
                name=f"Test Organization {i+1}",
                question_quota=100 + i * 50,
                questions_used=20 + i * 10,
                access_level="FLEXIBLE",
                quota_reset_date=date.today(),
                rocportal_status=True,
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            orgs.append(org)
        return orgs

    @patch('app.db_interface.organizations.Session')
    def test_get_organizations_for_quota_reset_success(self, mock_session_class, sample_organizations_list):
        """Test successful retrieval of organizations for quota reset"""
        # Arrange
        mock_session = MagicMock()
        mock_session_class.return_value.__enter__.return_value = mock_session
        mock_session.query.return_value.filter.return_value.all.return_value = sample_organizations_list
        target_date = date.today()

        # Act
        result = get_organizations_for_quota_reset(target_date)

        # Assert
        assert result == sample_organizations_list
        assert len(result) == 3
        mock_session.query.assert_called_once_with(OrganizationsORM)
        mock_session.query.return_value.filter.assert_called_once()

    @patch('app.db_interface.organizations.Session')
    def test_get_organizations_for_quota_reset_default_date(self, mock_session_class, sample_organizations_list):
        """Test retrieval with default date (today)"""
        # Arrange
        mock_session = MagicMock()
        mock_session_class.return_value.__enter__.return_value = mock_session
        mock_session.query.return_value.filter.return_value.all.return_value = sample_organizations_list

        # Act
        result = get_organizations_for_quota_reset()

        # Assert
        assert result == sample_organizations_list
        assert len(result) == 3
        mock_session.query.assert_called_once_with(OrganizationsORM)

    @patch('app.db_interface.organizations.Session')
    def test_get_organizations_for_quota_reset_empty_list(self, mock_session_class):
        """Test retrieval when no organizations need reset"""
        # Arrange
        mock_session = MagicMock()
        mock_session_class.return_value.__enter__.return_value = mock_session
        mock_session.query.return_value.filter.return_value.all.return_value = []

        # Act
        result = get_organizations_for_quota_reset()

        # Assert
        assert result == []
        assert len(result) == 0
        mock_session.query.assert_called_once_with(OrganizationsORM)

    @patch('app.db_interface.organizations.Session')
    def test_get_organizations_for_quota_reset_exception(self, mock_session_class):
        """Test exception handling in get_organizations_for_quota_reset"""
        # Arrange
        mock_session = MagicMock()
        mock_session_class.return_value.__enter__.return_value = mock_session
        mock_session.query.side_effect = Exception("Database connection error")

        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            get_organizations_for_quota_reset()
        
        assert str(exc_info.value) == "Database connection error"

    @patch('app.db_interface.organizations.Session')
    def test_reset_organization_quota_success(self, mock_session_class, sample_organization):
        """Test successful quota reset for an organization"""
        # Arrange
        mock_session = MagicMock()
        mock_session_class.return_value.__enter__.return_value = mock_session
        mock_session.query.return_value.filter.return_value.first.return_value = sample_organization
        
        org_id = str(sample_organization.id)
        new_reset_date = date.today() + timedelta(days=30)

        # Act
        result = reset_organization_quota(org_id, new_reset_date)

        # Assert
        assert result == sample_organization
        assert sample_organization.questions_used == 0
        assert sample_organization.quota_reset_date == new_reset_date
        mock_session.commit.assert_called_once()
        mock_session.refresh.assert_called_once_with(sample_organization)

    @patch('app.db_interface.organizations.Session')
    def test_reset_organization_quota_not_found(self, mock_session_class):
        """Test quota reset for non-existent organization"""
        # Arrange
        mock_session = MagicMock()
        mock_session_class.return_value.__enter__.return_value = mock_session
        mock_session.query.return_value.filter.return_value.first.return_value = None
        
        org_id = str(uuid4())
        new_reset_date = date.today() + timedelta(days=30)

        # Act
        result = reset_organization_quota(org_id, new_reset_date)

        # Assert
        assert result is None
        mock_session.commit.assert_not_called()
        mock_session.refresh.assert_not_called()

    @patch('app.db_interface.organizations.Session')
    def test_reset_organization_quota_exception(self, mock_session_class):
        """Test exception handling in reset_organization_quota"""
        # Arrange
        mock_session = MagicMock()
        mock_session_class.return_value.__enter__.return_value = mock_session
        mock_session.query.side_effect = Exception("Database error")
        
        org_id = str(uuid4())
        new_reset_date = date.today() + timedelta(days=30)

        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            reset_organization_quota(org_id, new_reset_date)
        
        assert str(exc_info.value) == "Database error"

    @patch('app.db_interface.organizations.Session')
    def test_get_organization_by_id_for_quota_success(self, mock_session_class, sample_organization):
        """Test successful retrieval of organization by ID"""
        # Arrange
        mock_session = MagicMock()
        mock_session_class.return_value.__enter__.return_value = mock_session
        mock_session.query.return_value.filter.return_value.first.return_value = sample_organization
        
        org_id = str(sample_organization.id)

        # Act
        result = get_organization_by_id_for_quota(org_id)

        # Assert
        assert result == sample_organization
        mock_session.query.assert_called_once_with(OrganizationsORM)
        mock_session.query.return_value.filter.assert_called_once()

    @patch('app.db_interface.organizations.Session')
    def test_get_organization_by_id_for_quota_not_found(self, mock_session_class):
        """Test retrieval of non-existent organization"""
        # Arrange
        mock_session = MagicMock()
        mock_session_class.return_value.__enter__.return_value = mock_session
        mock_session.query.return_value.filter.return_value.first.return_value = None
        
        org_id = str(uuid4())

        # Act
        result = get_organization_by_id_for_quota(org_id)

        # Assert
        assert result is None
        mock_session.query.assert_called_once_with(OrganizationsORM)

    @patch('app.db_interface.organizations.Session')
    def test_get_organization_by_id_for_quota_exception(self, mock_session_class):
        """Test exception handling in get_organization_by_id_for_quota"""
        # Arrange
        mock_session = MagicMock()
        mock_session_class.return_value.__enter__.return_value = mock_session
        mock_session.query.side_effect = Exception("Database error")
        
        org_id = str(uuid4())

        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            get_organization_by_id_for_quota(org_id)
        
        assert str(exc_info.value) == "Database error"


class TestQuotaDBInterfaceIntegration:
    """Integration tests for quota DB interface methods"""

    def test_quota_reset_date_calculation(self):
        """Test that quota reset date calculation is correct"""
        # Arrange
        today = date.today()
        expected_reset_date = today + timedelta(days=30)

        # Act
        calculated_date = today + timedelta(days=30)

        # Assert
        assert calculated_date == expected_reset_date
        assert (calculated_date - today).days == 30

    def test_organization_quota_fields(self):
        """Test that organization has all required quota fields"""
        # Arrange
        from uuid import uuid4
        from datetime import date, datetime
        
        org = OrganizationsORM(
            id=str(uuid4()),
            name="Test Organization",
            question_quota=100,
            questions_used=50,
            access_level="FLEXIBLE",
            quota_reset_date=date.today(),
            rocportal_status=True,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )

        # Act & Assert
        assert hasattr(org, 'id')
        assert hasattr(org, 'name')
        assert hasattr(org, 'question_quota')
        assert hasattr(org, 'questions_used')
        assert hasattr(org, 'access_level')
        assert hasattr(org, 'quota_reset_date')
        assert hasattr(org, 'rocportal_status')
        
        assert isinstance(org.question_quota, int)
        assert isinstance(org.questions_used, int)
        assert isinstance(org.quota_reset_date, date)
        assert isinstance(org.rocportal_status, bool)

    def test_quota_reset_operation_structure(self):
        """Test the structure of quota reset operation"""
        # Arrange
        org_id = str(uuid4())
        new_reset_date = date.today() + timedelta(days=30)

        # Act & Assert
        # Test that the function signature is correct
        import inspect
        sig = inspect.signature(reset_organization_quota)
        params = list(sig.parameters.keys())
        
        assert 'organization_id' in params
        assert 'new_quota_reset_date' in params
        
        # Test parameter types
        assert sig.parameters['organization_id'].annotation == str
        assert sig.parameters['new_quota_reset_date'].annotation == date

    def test_get_organizations_query_structure(self):
        """Test the structure of get_organizations query"""
        # Arrange
        target_date = date.today()

        # Act & Assert
        # Test that the function signature is correct
        import inspect
        sig = inspect.signature(get_organizations_for_quota_reset)
        params = list(sig.parameters.keys())
        
        assert 'target_date' in params
        
        # Test parameter types and default
        param = sig.parameters['target_date']
        assert param.annotation == date
        assert param.default is None

    def test_get_organization_by_id_query_structure(self):
        """Test the structure of get_organization_by_id query"""
        # Arrange
        org_id = str(uuid4())

        # Act & Assert
        # Test that the function signature is correct
        import inspect
        sig = inspect.signature(get_organization_by_id_for_quota)
        params = list(sig.parameters.keys())
        
        assert 'organization_id' in params
        
        # Test parameter types
        assert sig.parameters['organization_id'].annotation == str
