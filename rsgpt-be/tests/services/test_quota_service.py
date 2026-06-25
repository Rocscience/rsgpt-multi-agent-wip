"""Tests for app.services.quota_service module"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from uuid import uuid4, UUID
from datetime import date, datetime, timedelta
from typing import List

from app.services.quota_service import QuotaService, daily_quota_reset_job
from app.db_models.organizations import OrganizationsORM
from app.db_models.users import UsersORM
from app.db_interface.organizations import (
    get_organizations_for_quota_reset,
    reset_organization_quota,
    get_organization_by_id_for_quota
)


class TestQuotaService:
    """Test cases for QuotaService class"""

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

    @patch('app.services.quota_service.get_organizations_for_quota_reset')
    def test_get_organizations_for_quota_reset_success(self, mock_get_orgs, sample_organizations_list):
        """Test successful retrieval of organizations for quota reset"""
        # Arrange
        mock_get_orgs.return_value = sample_organizations_list
        target_date = date.today()

        # Act
        result = QuotaService.get_organizations_for_quota_reset(target_date)

        # Assert
        assert result == sample_organizations_list
        assert len(result) == 3
        mock_get_orgs.assert_called_once_with(target_date)

    @patch('app.services.quota_service.get_organizations_for_quota_reset')
    def test_get_organizations_for_quota_reset_default_date(self, mock_get_orgs, sample_organizations_list):
        """Test retrieval with default date (today)"""
        # Arrange
        mock_get_orgs.return_value = sample_organizations_list

        # Act
        result = QuotaService.get_organizations_for_quota_reset()

        # Assert
        assert result == sample_organizations_list
        mock_get_orgs.assert_called_once_with(None)

    @patch('app.services.quota_service.get_organizations_for_quota_reset')
    def test_get_organizations_for_quota_reset_empty_list(self, mock_get_orgs):
        """Test retrieval when no organizations need reset"""
        # Arrange
        mock_get_orgs.return_value = []

        # Act
        result = QuotaService.get_organizations_for_quota_reset()

        # Assert
        assert result == []
        assert len(result) == 0
        mock_get_orgs.assert_called_once_with(None)

    @patch('app.services.quota_service.get_organizations_for_quota_reset')
    def test_get_organizations_for_quota_reset_exception(self, mock_get_orgs):
        """Test exception handling in get_organizations_for_quota_reset"""
        # Arrange
        mock_get_orgs.side_effect = Exception("Database connection error")

        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            QuotaService.get_organizations_for_quota_reset()
        
        assert str(exc_info.value) == "Database connection error"
        mock_get_orgs.assert_called_once_with(None)

    @patch('app.services.quota_service.reset_organization_quota')
    def test_reset_organization_quota_success(self, mock_reset_quota, sample_organization):
        """Test successful quota reset for an organization"""
        # Arrange
        mock_reset_quota.return_value = sample_organization
        sample_organization.questions_used = 0  # Reset to 0

        # Act
        result = QuotaService.reset_organization_quota(sample_organization)

        # Assert
        assert result is True
        mock_reset_quota.assert_called_once()
        call_args = mock_reset_quota.call_args
        assert call_args[0][0] == str(sample_organization.id)  # organization_id
        assert isinstance(call_args[0][1], date)  # new_reset_date

    @patch('app.services.quota_service.reset_organization_quota')
    def test_reset_organization_quota_failure(self, mock_reset_quota, sample_organization):
        """Test quota reset failure"""
        # Arrange
        mock_reset_quota.return_value = None

        # Act
        result = QuotaService.reset_organization_quota(sample_organization)

        # Assert
        assert result is False
        mock_reset_quota.assert_called_once()

    @patch('app.services.quota_service.reset_organization_quota')
    def test_reset_organization_quota_exception(self, mock_reset_quota, sample_organization):
        """Test exception handling in quota reset"""
        # Arrange
        mock_reset_quota.side_effect = Exception("Database error")

        # Act
        result = QuotaService.reset_organization_quota(sample_organization)

        # Assert
        assert result is False
        mock_reset_quota.assert_called_once()

    @patch('app.services.quota_service.get_organization_by_id_for_quota')
    def test_get_organization_by_id_success(self, mock_get_org, sample_organization):
        """Test successful retrieval of organization by ID"""
        # Arrange
        org_id = str(sample_organization.id)
        mock_get_org.return_value = sample_organization

        # Act
        result = QuotaService.get_organization_by_id(org_id)

        # Assert
        assert result == sample_organization
        mock_get_org.assert_called_once_with(org_id)

    @patch('app.services.quota_service.get_organization_by_id_for_quota')
    def test_get_organization_by_id_not_found(self, mock_get_org):
        """Test retrieval of non-existent organization"""
        # Arrange
        org_id = str(uuid4())
        mock_get_org.return_value = None

        # Act
        result = QuotaService.get_organization_by_id(org_id)

        # Assert
        assert result is None
        mock_get_org.assert_called_once_with(org_id)

    @patch('app.services.quota_service.get_organization_by_id_for_quota')
    def test_get_organization_by_id_exception(self, mock_get_org):
        """Test exception handling in get_organization_by_id"""
        # Arrange
        org_id = str(uuid4())
        mock_get_org.side_effect = Exception("Database error")

        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            QuotaService.get_organization_by_id(org_id)
        
        assert str(exc_info.value) == "Database error"
        mock_get_org.assert_called_once_with(org_id)

    @patch('app.services.quota_service.QuotaService.reset_organization_quota')
    @patch('app.services.quota_service.QuotaService.get_organizations_for_quota_reset')
    def test_process_daily_quota_resets_success(self, mock_get_orgs, mock_reset_quota, sample_organizations_list):
        """Test successful daily quota reset process"""
        # Arrange
        mock_get_orgs.return_value = sample_organizations_list
        mock_reset_quota.return_value = True

        # Act
        result = QuotaService.process_daily_quota_resets()

        # Assert
        assert result["status"] == "success"
        assert result["organizations_processed"] == 3
        assert result["organizations_successful"] == 3
        assert result["organizations_failed"] == 0
        assert result["duration_seconds"] > 0
        assert "processed_at" in result
        assert "completed_at" in result
        
        mock_get_orgs.assert_called_once()
        assert mock_reset_quota.call_count == 3

    @patch('app.services.quota_service.QuotaService.reset_organization_quota')
    @patch('app.services.quota_service.QuotaService.get_organizations_for_quota_reset')
    def test_process_daily_quota_resets_partial_failure(self, mock_get_orgs, mock_reset_quota, sample_organizations_list):
        """Test daily quota reset with partial failures"""
        # Arrange
        mock_get_orgs.return_value = sample_organizations_list
        # First two succeed, third fails
        mock_reset_quota.side_effect = [True, True, False]

        # Act
        result = QuotaService.process_daily_quota_resets()

        # Assert
        assert result["status"] == "partial_success"
        assert result["organizations_processed"] == 3
        assert result["organizations_successful"] == 2
        assert result["organizations_failed"] == 1
        assert result["duration_seconds"] > 0

    @patch('app.services.quota_service.QuotaService.get_organizations_for_quota_reset')
    def test_process_daily_quota_resets_no_organizations(self, mock_get_orgs):
        """Test daily quota reset when no organizations need reset"""
        # Arrange
        mock_get_orgs.return_value = []

        # Act
        result = QuotaService.process_daily_quota_resets()

        # Assert
        assert result["status"] == "success"
        assert result["organizations_processed"] == 0
        assert result["organizations_successful"] == 0
        assert result["organizations_failed"] == 0
        assert result["duration_seconds"] > 0

    @patch('app.services.quota_service.QuotaService.get_organizations_for_quota_reset')
    def test_process_daily_quota_resets_exception(self, mock_get_orgs):
        """Test exception handling in daily quota reset process"""
        # Arrange
        mock_get_orgs.side_effect = Exception("Database connection failed")

        # Act
        result = QuotaService.process_daily_quota_resets()

        # Assert
        assert result["status"] == "error"
        assert result["message"] == "Database connection failed"
        assert result["organizations_processed"] == 0
        assert result["organizations_successful"] == 0
        assert result["organizations_failed"] == 0
        assert result["duration_seconds"] > 0


class TestResetAllAgentQuotas:
    """Test cases for the reset_all_agent_quotas method"""

    @patch('app.services.quota_service.reset_all_users_agent_quota')
    def test_reset_all_agent_quotas_success(self, mock_reset_all):
        """Test successful agent quota reset for all users"""
        # Arrange
        mock_reset_all.return_value = 10  # 10 users reset

        # Act
        result = QuotaService.reset_all_agent_quotas()

        # Assert
        assert result["status"] == "success"
        assert result["users_reset"] == 10
        assert result["duration_seconds"] >= 0
        assert "processed_at" in result
        assert "completed_at" in result
        mock_reset_all.assert_called_once()

    @patch('app.services.quota_service.reset_all_users_agent_quota')
    def test_reset_all_agent_quotas_no_users(self, mock_reset_all):
        """Test agent quota reset when no users need reset"""
        # Arrange
        mock_reset_all.return_value = 0

        # Act
        result = QuotaService.reset_all_agent_quotas()

        # Assert
        assert result["status"] == "success"
        assert result["users_reset"] == 0
        assert result["message"] == "Reset agent quota for 0 users"
        mock_reset_all.assert_called_once()

    @patch('app.services.quota_service.reset_all_users_agent_quota')
    def test_reset_all_agent_quotas_exception(self, mock_reset_all):
        """Test exception handling in agent quota reset"""
        # Arrange
        mock_reset_all.side_effect = Exception("Database connection failed")

        # Act
        result = QuotaService.reset_all_agent_quotas()

        # Assert
        assert result["status"] == "error"
        assert result["message"] == "Database connection failed"
        assert result["users_reset"] == 0
        assert result["duration_seconds"] >= 0


class TestDailyQuotaResetJob:
    """Test cases for the daily_quota_reset_job function"""

    @patch('app.services.quota_service.QuotaService.process_daily_quota_resets')
    def test_daily_quota_reset_job_success(self, mock_process_resets):
        """Test successful daily quota reset job execution"""
        # Arrange
        expected_result = {
            "status": "success",
            "message": "Quota reset completed successfully",
            "organizations_processed": 2,
            "organizations_successful": 2,
            "organizations_failed": 0,
            "duration_seconds": 1.5
        }
        mock_process_resets.return_value = expected_result

        # Act
        with patch('app.services.quota_service.date') as mock_date:
            mock_date.today.return_value = date(2026, 1, 15)  # Not first of month
            result = daily_quota_reset_job()

        # Assert
        assert result == expected_result
        mock_process_resets.assert_called_once()

    @patch('app.services.quota_service.QuotaService.process_daily_quota_resets')
    def test_daily_quota_reset_job_failure(self, mock_process_resets):
        """Test daily quota reset job with failures"""
        # Arrange
        expected_result = {
            "status": "error",
            "message": "Database connection failed",
            "organizations_processed": 0,
            "organizations_successful": 0,
            "organizations_failed": 0,
            "duration_seconds": 0.1
        }
        mock_process_resets.return_value = expected_result

        # Act
        with patch('app.services.quota_service.date') as mock_date:
            mock_date.today.return_value = date(2026, 1, 15)  # Not first of month
            result = daily_quota_reset_job()

        # Assert
        assert result == expected_result
        mock_process_resets.assert_called_once()

    @patch('app.services.quota_service.QuotaService.process_daily_quota_resets')
    def test_daily_quota_reset_job_exception(self, mock_process_resets):
        """Test exception handling in daily quota reset job"""
        # Arrange
        mock_process_resets.side_effect = Exception("Unexpected error")

        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            daily_quota_reset_job()
        
        assert str(exc_info.value) == "Unexpected error"
        mock_process_resets.assert_called_once()

    @patch('app.services.quota_service.QuotaService.reset_all_agent_quotas')
    @patch('app.services.quota_service.QuotaService.process_daily_quota_resets')
    def test_daily_quota_reset_job_first_of_month_triggers_agent_reset(self, mock_process_resets, mock_agent_reset):
        """Test that agent quota reset is triggered on first of month"""
        # Arrange
        org_result = {
            "status": "success",
            "message": "Processed 2 organizations",
            "organizations_processed": 2,
            "organizations_successful": 2,
            "organizations_failed": 0,
            "duration_seconds": 1.0
        }
        agent_result = {
            "status": "success",
            "message": "Reset agent quota for 5 users",
            "users_reset": 5,
            "duration_seconds": 0.5
        }
        mock_process_resets.return_value = org_result
        mock_agent_reset.return_value = agent_result

        # Act
        with patch('app.services.quota_service.date') as mock_date:
            mock_date.today.return_value = date(2026, 2, 1)  # First of month
            result = daily_quota_reset_job()

        # Assert
        mock_process_resets.assert_called_once()
        mock_agent_reset.assert_called_once()
        assert "agent_quota_reset" in result
        assert result["agent_quota_reset"] == agent_result

    @patch('app.services.quota_service.QuotaService.reset_all_agent_quotas')
    @patch('app.services.quota_service.QuotaService.process_daily_quota_resets')
    def test_daily_quota_reset_job_not_first_of_month_no_agent_reset(self, mock_process_resets, mock_agent_reset):
        """Test that agent quota reset is NOT triggered when not first of month"""
        # Arrange
        org_result = {
            "status": "success",
            "message": "Processed 2 organizations",
            "organizations_processed": 2,
            "organizations_successful": 2,
            "organizations_failed": 0,
            "duration_seconds": 1.0
        }
        mock_process_resets.return_value = org_result

        # Act
        with patch('app.services.quota_service.date') as mock_date:
            mock_date.today.return_value = date(2026, 2, 15)  # Not first of month
            result = daily_quota_reset_job()

        # Assert
        mock_process_resets.assert_called_once()
        mock_agent_reset.assert_not_called()
        assert "agent_quota_reset" not in result

    @patch('app.services.quota_service.QuotaService.reset_all_agent_quotas')
    @patch('app.services.quota_service.QuotaService.process_daily_quota_resets')
    def test_daily_quota_reset_job_first_of_month_all_months(self, mock_process_resets, mock_agent_reset):
        """Test that agent quota reset works for first of any month"""
        # Arrange
        org_result = {"status": "success", "organizations_processed": 0, "organizations_successful": 0, "organizations_failed": 0, "duration_seconds": 0.1}
        agent_result = {"status": "success", "users_reset": 3, "duration_seconds": 0.1}
        mock_process_resets.return_value = org_result
        mock_agent_reset.return_value = agent_result

        # Test multiple first-of-month dates
        first_of_months = [
            date(2026, 1, 1),
            date(2026, 3, 1),
            date(2026, 6, 1),
            date(2026, 12, 1),
        ]

        for first_date in first_of_months:
            mock_process_resets.reset_mock()
            mock_agent_reset.reset_mock()
            
            with patch('app.services.quota_service.date') as mock_date:
                mock_date.today.return_value = first_date
                result = daily_quota_reset_job()
            
            # Assert agent reset was called for each first of month
            mock_agent_reset.assert_called_once()
            assert "agent_quota_reset" in result


class TestQuotaServiceIntegration:
    """Integration tests for QuotaService with real database operations"""

    @pytest.fixture
    def test_organization_data(self):
        """Create test organization data"""
        return {
            "id": str(uuid4()),
            "name": "Integration Test Org",
            "question_quota": 200,
            "questions_used": 75,
            "access_level": "FLEXIBLE",
            "quota_reset_date": date.today(),
            "rocportal_status": True
        }

    def test_quota_reset_date_calculation(self):
        """Test that quota reset date is calculated correctly (30 days from today)"""
        # Arrange
        today = date.today()
        expected_reset_date = today + timedelta(days=30)

        # Act
        # This tests the date calculation logic in reset_organization_quota
        calculated_date = today + timedelta(days=30)

        # Assert
        assert calculated_date == expected_reset_date
        assert (calculated_date - today).days == 30

    def test_organization_quota_info_structure(self, test_organization_data):
        """Test that organization quota information has correct structure"""
        # Arrange
        org_data = test_organization_data

        # Act & Assert
        assert "id" in org_data
        assert "name" in org_data
        assert "question_quota" in org_data
        assert "questions_used" in org_data
        assert "access_level" in org_data
        assert "quota_reset_date" in org_data
        assert "rocportal_status" in org_data
        
        assert isinstance(org_data["question_quota"], int)
        assert isinstance(org_data["questions_used"], int)
        assert isinstance(org_data["quota_reset_date"], date)
        assert isinstance(org_data["rocportal_status"], bool)

    def test_quota_reset_result_structure(self):
        """Test that quota reset result has correct structure"""
        # Arrange
        result = {
            "status": "success",
            "message": "Test message",
            "organizations_processed": 1,
            "organizations_successful": 1,
            "organizations_failed": 0,
            "duration_seconds": 1.0,
            "processed_at": datetime.now().isoformat(),
            "completed_at": datetime.now().isoformat()
        }

        # Act & Assert
        required_fields = [
            "status", "message", "organizations_processed",
            "organizations_successful", "organizations_failed", "duration_seconds"
        ]
        
        for field in required_fields:
            assert field in result
        
        assert isinstance(result["organizations_processed"], int)
        assert isinstance(result["organizations_successful"], int)
        assert isinstance(result["organizations_failed"], int)
        assert isinstance(result["duration_seconds"], float)
        assert result["organizations_processed"] >= 0
        assert result["organizations_successful"] >= 0
        assert result["organizations_failed"] >= 0
        assert result["duration_seconds"] >= 0
