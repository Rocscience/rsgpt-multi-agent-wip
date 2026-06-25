"""Tests for app.services.user_service — focusing on RSI-218 changes.

Covers:
  - update_organization_and_quota(): org creation, quota update, access_level
    update, user reassignment when org_id differs, and no-op when already correct.
  - get_quota_and_access_level_from_license_data(): all license permutations.
  - extract_organization_data(): happy path and error branches.
"""

import pytest
from unittest.mock import Mock, patch, call
from uuid import uuid4

from app.services.user_service import UserService
from app.db_models.organizations import OrganizationsORM, UserOrganizationsORM
from app.models.enums import User_Permission_Enum
from app.models.consts import (
    QUESTIONS_PER_FCL_LICENSE,
    QUESTIONS_PER_PCL_LICENSE,
    QUESTIONS_FOR_NO_LICENSE,
)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _make_org(org_id=None, access_level="BASIC", question_quota=20, rocportal_status=False):
    """Return a lightweight OrganizationsORM with the given fields set."""
    org = OrganizationsORM(
        id=org_id or str(uuid4()),
        name="Test Org",
        question_quota=question_quota,
        access_level=access_level,
        rocportal_status=rocportal_status,
    )
    return org


def _rocportal_response(org_id, org_name="Rocscience", licenses=None):
    """Build a minimal rocportal API response dict."""
    return {
        "result": True,
        "data": {
            "current_organization": {
                "id": org_id,
                "name": org_name,
                "licenses": licenses or [],
            }
        },
    }


def _active_fcl(num_seats=1):
    return {"type": "FCL", "status": "Active", "num_seats": num_seats}


def _active_pcl(num_seats=1):
    return {"type": "PCL", "status": "Active", "num_seats": num_seats}


def _lapsed_fcl(num_seats=1):
    return {"type": "FCL", "status": "Lapsed", "num_seats": num_seats}


# ---------------------------------------------------------------------------
# TestGetQuotaAndAccessLevelFromLicenseData
# ---------------------------------------------------------------------------

class TestGetQuotaAndAccessLevelFromLicenseData:
    """Unit tests for the license-parsing helper."""

    def setup_method(self):
        self.service = UserService()

    def test_no_licenses_returns_basic_with_default_quota(self):
        quota, level = self.service.get_quota_and_access_level_from_license_data([])
        assert quota == QUESTIONS_FOR_NO_LICENSE
        assert level == User_Permission_Enum.BASIC

    def test_only_lapsed_licenses_treated_as_no_active(self):
        quota, level = self.service.get_quota_and_access_level_from_license_data(
            [_lapsed_fcl(5)]
        )
        assert quota == QUESTIONS_FOR_NO_LICENSE
        assert level == User_Permission_Enum.BASIC

    def test_single_active_fcl_one_seat(self):
        quota, level = self.service.get_quota_and_access_level_from_license_data(
            [_active_fcl(1)]
        )
        assert quota == QUESTIONS_PER_FCL_LICENSE * 1
        assert level == User_Permission_Enum.FLEXIBLE

    def test_active_fcl_multiple_seats(self):
        seats = 3
        quota, level = self.service.get_quota_and_access_level_from_license_data(
            [_active_fcl(seats)]
        )
        assert quota == QUESTIONS_PER_FCL_LICENSE * seats
        assert level == User_Permission_Enum.FLEXIBLE

    def test_single_active_pcl_one_seat(self):
        quota, level = self.service.get_quota_and_access_level_from_license_data(
            [_active_pcl(1)]
        )
        assert quota == QUESTIONS_PER_PCL_LICENSE * 1
        assert level == User_Permission_Enum.FLEXIBLE

    def test_mixed_fcl_and_pcl_licenses(self):
        licenses = [_active_fcl(2), _active_pcl(3)]
        quota, level = self.service.get_quota_and_access_level_from_license_data(licenses)
        expected = QUESTIONS_PER_FCL_LICENSE * 2 + QUESTIONS_PER_PCL_LICENSE * 3
        assert quota == expected
        assert level == User_Permission_Enum.FLEXIBLE

    def test_active_and_lapsed_mix_only_counts_active(self):
        licenses = [_active_fcl(1), _lapsed_fcl(10)]
        quota, level = self.service.get_quota_and_access_level_from_license_data(licenses)
        assert quota == QUESTIONS_PER_FCL_LICENSE * 1
        assert level == User_Permission_Enum.FLEXIBLE


# ---------------------------------------------------------------------------
# TestExtractOrganizationData
# ---------------------------------------------------------------------------

class TestExtractOrganizationData:
    """Tests for extract_organization_data() error handling."""

    def setup_method(self):
        self.service = UserService()
        self.user_id = uuid4()

    def test_raises_if_org_id_missing(self):
        bad_response = {"result": True, "data": {"current_organization": {"name": "Acme", "licenses": []}}}
        with pytest.raises(ValueError, match="Organization ID not found"):
            self.service.extract_organization_data(self.user_id, bad_response)

    def test_raises_if_org_name_missing(self):
        bad_response = {"result": True, "data": {"current_organization": {"id": str(uuid4()), "licenses": []}}}
        with pytest.raises(ValueError, match="Organization name not found"):
            self.service.extract_organization_data(self.user_id, bad_response)

    def test_raises_if_data_key_missing(self):
        with pytest.raises(ValueError):
            self.service.extract_organization_data(self.user_id, {"result": True})

    def test_happy_path_returns_correct_dataclass(self):
        org_id = str(uuid4())
        response = _rocportal_response(org_id, licenses=[_active_fcl(2)])
        result = self.service.extract_organization_data(self.user_id, response)

        assert result.organization_id == org_id
        assert result.organization_name == "Rocscience"
        assert result.question_quota == QUESTIONS_PER_FCL_LICENSE * 2
        assert result.access_level == User_Permission_Enum.FLEXIBLE
        assert result.rocportal_status is True

    def test_rocportal_status_false_when_result_false(self):
        org_id = str(uuid4())
        response = _rocportal_response(org_id)
        response["result"] = False
        result = self.service.extract_organization_data(self.user_id, response)
        assert result.rocportal_status is False


# ---------------------------------------------------------------------------
# TestUpdateOrganizationAndQuota — RSI-218 core logic
# ---------------------------------------------------------------------------

class TestUpdateOrganizationAndQuota:
    """Tests for update_organization_and_quota() covering all branches
    introduced / changed in RSI-218."""

    SERVICE_PATH = "app.services.user_service"

    def setup_method(self):
        self.service = UserService()
        self.user_id = uuid4()

    # ------------------------------------------------------------------
    # Branch 1: org does not exist in DB yet → CREATE
    # ------------------------------------------------------------------

    def test_creates_org_when_not_in_db(self):
        """When rocportal returns an org we have never seen, it is created."""
        org_id = str(uuid4())
        response = _rocportal_response(org_id, licenses=[_active_fcl(1)])

        new_org = _make_org(org_id=org_id, access_level="FLEXIBLE", question_quota=250)

        with patch(f"{self.SERVICE_PATH}.get_organization_by_id", return_value=None) as mock_get_by_id, \
             patch(f"{self.SERVICE_PATH}.create_organization", return_value=new_org) as mock_create, \
             patch(f"{self.SERVICE_PATH}.get_organization_by_user_id", return_value=None), \
             patch(f"{self.SERVICE_PATH}.add_user_to_organization") as mock_add, \
             patch(f"{self.SERVICE_PATH}.update_organization_quota") as mock_update, \
             patch(f"{self.SERVICE_PATH}.reassign_user_organization") as mock_reassign:

            result = self.service.update_organization_and_quota(self.user_id, response)

        mock_get_by_id.assert_called_once_with(org_id)
        mock_create.assert_called_once()
        mock_update.assert_not_called()
        mock_add.assert_called_once_with(self.user_id, new_org.id)
        mock_reassign.assert_not_called()
        assert result == new_org

    def test_create_passes_correct_quota_and_access_level(self):
        """Created org receives quota and access_level derived from license data."""
        org_id = str(uuid4())
        # 2 FCL seats + 3 PCL seats
        response = _rocportal_response(org_id, licenses=[_active_fcl(2), _active_pcl(3)])
        expected_quota = QUESTIONS_PER_FCL_LICENSE * 2 + QUESTIONS_PER_PCL_LICENSE * 3

        new_org = _make_org(org_id=org_id, access_level="FLEXIBLE", question_quota=expected_quota)

        with patch(f"{self.SERVICE_PATH}.get_organization_by_id", return_value=None), \
             patch(f"{self.SERVICE_PATH}.create_organization", return_value=new_org) as mock_create, \
             patch(f"{self.SERVICE_PATH}.get_organization_by_user_id", return_value=None), \
             patch(f"{self.SERVICE_PATH}.add_user_to_organization"), \
             patch(f"{self.SERVICE_PATH}.reassign_user_organization"):

            self.service.update_organization_and_quota(self.user_id, response)

        create_request = mock_create.call_args[0][0]
        assert create_request.question_quota == expected_quota
        assert create_request.access_level == User_Permission_Enum.FLEXIBLE

    # ------------------------------------------------------------------
    # Branch 2: org exists → UPDATE quota + access_level + rocportal_status
    # ------------------------------------------------------------------

    def test_updates_existing_org_quota_and_access_level(self):
        """When org already exists it is updated with latest quota and access_level."""
        org_id = str(uuid4())
        response = _rocportal_response(org_id, licenses=[_active_fcl(3)])
        expected_quota = QUESTIONS_PER_FCL_LICENSE * 3

        existing_org = _make_org(org_id=org_id, access_level="BASIC", question_quota=20)
        updated_org = _make_org(org_id=org_id, access_level="FLEXIBLE", question_quota=expected_quota)

        with patch(f"{self.SERVICE_PATH}.get_organization_by_id", return_value=existing_org), \
             patch(f"{self.SERVICE_PATH}.update_organization_quota", return_value=updated_org) as mock_update, \
             patch(f"{self.SERVICE_PATH}.get_organization_by_user_id", return_value=updated_org), \
             patch(f"{self.SERVICE_PATH}.create_organization") as mock_create, \
             patch(f"{self.SERVICE_PATH}.add_user_to_organization") as mock_add, \
             patch(f"{self.SERVICE_PATH}.reassign_user_organization") as mock_reassign:

            result = self.service.update_organization_and_quota(self.user_id, response)

        mock_create.assert_not_called()
        mock_update.assert_called_once_with(
            existing_org.id,
            expected_quota,
            True,                           # rocportal_status from response["result"]
            access_level=User_Permission_Enum.FLEXIBLE,
        )
        # User already in correct org → no add or reassign
        mock_add.assert_not_called()
        mock_reassign.assert_not_called()
        assert result == updated_org

    def test_update_passes_rocportal_status_from_response(self):
        """rocportal_status boolean comes from response['result'], not hardcoded."""
        org_id = str(uuid4())
        response = _rocportal_response(org_id, licenses=[_active_fcl(1)])
        response["result"] = False  # simulate a False status

        existing_org = _make_org(org_id=org_id)
        updated_org = _make_org(org_id=org_id, rocportal_status=False)

        with patch(f"{self.SERVICE_PATH}.get_organization_by_id", return_value=existing_org), \
             patch(f"{self.SERVICE_PATH}.update_organization_quota", return_value=updated_org) as mock_update, \
             patch(f"{self.SERVICE_PATH}.get_organization_by_user_id", return_value=updated_org), \
             patch(f"{self.SERVICE_PATH}.create_organization"), \
             patch(f"{self.SERVICE_PATH}.add_user_to_organization"), \
             patch(f"{self.SERVICE_PATH}.reassign_user_organization"):

            self.service.update_organization_and_quota(self.user_id, response)

        _, _, rocportal_status_arg = mock_update.call_args[0]
        assert rocportal_status_arg is False

    # ------------------------------------------------------------------
    # Branch 3: user has NO org → add them (unchanged existing behaviour)
    # ------------------------------------------------------------------

    def test_adds_user_when_no_existing_org_assignment(self):
        """User with no org row gets assigned to the rocportal org."""
        org_id = str(uuid4())
        response = _rocportal_response(org_id, licenses=[_active_fcl(1)])
        existing_org = _make_org(org_id=org_id, access_level="FLEXIBLE", question_quota=250)

        with patch(f"{self.SERVICE_PATH}.get_organization_by_id", return_value=existing_org), \
             patch(f"{self.SERVICE_PATH}.update_organization_quota", return_value=existing_org), \
             patch(f"{self.SERVICE_PATH}.get_organization_by_user_id", return_value=None), \
             patch(f"{self.SERVICE_PATH}.add_user_to_organization") as mock_add, \
             patch(f"{self.SERVICE_PATH}.reassign_user_organization") as mock_reassign, \
             patch(f"{self.SERVICE_PATH}.create_organization"):

            self.service.update_organization_and_quota(self.user_id, response)

        mock_add.assert_called_once_with(self.user_id, existing_org.id)
        mock_reassign.assert_not_called()

    # ------------------------------------------------------------------
    # Branch 4 (RSI-218 NEW): user is in WRONG org → reassign
    # ------------------------------------------------------------------

    def test_reassigns_user_when_current_org_differs_from_rocportal_org(self):
        """Core RSI-218 fix: if user's org_id != rocportal org_id, reassign."""
        rocportal_org_id = str(uuid4())
        self_created_org_id = str(uuid4())

        response = _rocportal_response(rocportal_org_id, licenses=[_active_fcl(1)])

        rocportal_org = _make_org(org_id=rocportal_org_id, access_level="FLEXIBLE", question_quota=250)
        self_created_org = _make_org(org_id=self_created_org_id, access_level="BASIC", question_quota=20)

        with patch(f"{self.SERVICE_PATH}.get_organization_by_id", return_value=rocportal_org), \
             patch(f"{self.SERVICE_PATH}.update_organization_quota", return_value=rocportal_org), \
             patch(f"{self.SERVICE_PATH}.get_organization_by_user_id", return_value=self_created_org), \
             patch(f"{self.SERVICE_PATH}.add_user_to_organization") as mock_add, \
             patch(f"{self.SERVICE_PATH}.reassign_user_organization") as mock_reassign, \
             patch(f"{self.SERVICE_PATH}.create_organization"):

            result = self.service.update_organization_and_quota(self.user_id, response)

        # Must reassign, must NOT just add
        mock_reassign.assert_called_once_with(self.user_id, rocportal_org.id)
        mock_add.assert_not_called()
        assert result == rocportal_org

    def test_reassigns_basic_self_org_to_flex_company_org(self):
        """Reproduces the Avi Tharmalingam scenario end-to-end through the service."""
        company_org_id = str(uuid4())
        personal_org_id = str(uuid4())

        response = _rocportal_response(company_org_id, org_name="Rocscience Inc", licenses=[_active_fcl(1)])

        company_org = _make_org(org_id=company_org_id, access_level="FLEXIBLE", question_quota=250)
        personal_org = _make_org(org_id=personal_org_id, access_level="BASIC", question_quota=20)

        with patch(f"{self.SERVICE_PATH}.get_organization_by_id", return_value=company_org), \
             patch(f"{self.SERVICE_PATH}.update_organization_quota", return_value=company_org), \
             patch(f"{self.SERVICE_PATH}.get_organization_by_user_id", return_value=personal_org), \
             patch(f"{self.SERVICE_PATH}.add_user_to_organization") as mock_add, \
             patch(f"{self.SERVICE_PATH}.reassign_user_organization") as mock_reassign, \
             patch(f"{self.SERVICE_PATH}.create_organization"):

            result = self.service.update_organization_and_quota(self.user_id, response)

        mock_reassign.assert_called_once_with(self.user_id, company_org.id)
        mock_add.assert_not_called()
        assert result.id == company_org_id

    # ------------------------------------------------------------------
    # Branch 5 (RSI-218 NEW): user is already in CORRECT org → no-op
    # ------------------------------------------------------------------

    def test_no_reassign_when_user_already_in_correct_org(self):
        """If user's org_id already matches rocportal org_id, no write is performed."""
        org_id = str(uuid4())
        response = _rocportal_response(org_id, licenses=[_active_fcl(1)])

        correct_org = _make_org(org_id=org_id, access_level="FLEXIBLE", question_quota=250)

        with patch(f"{self.SERVICE_PATH}.get_organization_by_id", return_value=correct_org), \
             patch(f"{self.SERVICE_PATH}.update_organization_quota", return_value=correct_org), \
             patch(f"{self.SERVICE_PATH}.get_organization_by_user_id", return_value=correct_org), \
             patch(f"{self.SERVICE_PATH}.add_user_to_organization") as mock_add, \
             patch(f"{self.SERVICE_PATH}.reassign_user_organization") as mock_reassign, \
             patch(f"{self.SERVICE_PATH}.create_organization"):

            self.service.update_organization_and_quota(self.user_id, response)

        mock_add.assert_not_called()
        mock_reassign.assert_not_called()

    # ------------------------------------------------------------------
    # Edge cases
    # ------------------------------------------------------------------

    def test_no_active_licenses_results_in_basic_org(self):
        """No active licenses → org created/updated as BASIC with default quota."""
        org_id = str(uuid4())
        # Only lapsed licenses
        response = _rocportal_response(org_id, licenses=[_lapsed_fcl(5)])

        new_org = _make_org(org_id=org_id, access_level="BASIC", question_quota=QUESTIONS_FOR_NO_LICENSE)

        with patch(f"{self.SERVICE_PATH}.get_organization_by_id", return_value=None), \
             patch(f"{self.SERVICE_PATH}.create_organization", return_value=new_org) as mock_create, \
             patch(f"{self.SERVICE_PATH}.get_organization_by_user_id", return_value=None), \
             patch(f"{self.SERVICE_PATH}.add_user_to_organization"), \
             patch(f"{self.SERVICE_PATH}.reassign_user_organization"):

            self.service.update_organization_and_quota(self.user_id, response)

        create_request = mock_create.call_args[0][0]
        assert create_request.question_quota == QUESTIONS_FOR_NO_LICENSE
        assert create_request.access_level == User_Permission_Enum.BASIC

    def test_raises_if_org_id_missing_from_response(self):
        """ValueError propagates up if rocportal response is malformed."""
        bad_response = {
            "result": True,
            "data": {"current_organization": {"name": "Acme", "licenses": []}},
        }
        with pytest.raises(ValueError, match="Organization ID not found"):
            self.service.update_organization_and_quota(self.user_id, bad_response)

    def test_logs_reassignment(self):
        """A log message is emitted when a user is reassigned (aids debugging)."""
        rocportal_org_id = str(uuid4())
        self_created_org_id = str(uuid4())

        response = _rocportal_response(rocportal_org_id, licenses=[_active_fcl(1)])
        rocportal_org = _make_org(org_id=rocportal_org_id, access_level="FLEXIBLE")
        self_created_org = _make_org(org_id=self_created_org_id, access_level="BASIC")

        with patch(f"{self.SERVICE_PATH}.get_organization_by_id", return_value=rocportal_org), \
             patch(f"{self.SERVICE_PATH}.update_organization_quota", return_value=rocportal_org), \
             patch(f"{self.SERVICE_PATH}.get_organization_by_user_id", return_value=self_created_org), \
             patch(f"{self.SERVICE_PATH}.add_user_to_organization"), \
             patch(f"{self.SERVICE_PATH}.reassign_user_organization"), \
             patch(f"{self.SERVICE_PATH}.logger") as mock_logger:

            self.service.update_organization_and_quota(self.user_id, response)

        # At least one info log should mention the reassignment
        log_messages = [str(c) for c in mock_logger.info.call_args_list]
        assert any("Reassigning" in msg or "reassign" in msg.lower() for msg in log_messages)

    def test_logs_new_org_creation(self):
        """A log message is emitted when a brand-new org is created."""
        org_id = str(uuid4())
        response = _rocportal_response(org_id, licenses=[_active_fcl(1)])
        new_org = _make_org(org_id=org_id, access_level="FLEXIBLE")

        with patch(f"{self.SERVICE_PATH}.get_organization_by_id", return_value=None), \
             patch(f"{self.SERVICE_PATH}.create_organization", return_value=new_org), \
             patch(f"{self.SERVICE_PATH}.get_organization_by_user_id", return_value=None), \
             patch(f"{self.SERVICE_PATH}.add_user_to_organization"), \
             patch(f"{self.SERVICE_PATH}.reassign_user_organization"), \
             patch(f"{self.SERVICE_PATH}.logger") as mock_logger:

            self.service.update_organization_and_quota(self.user_id, response)

        log_messages = [str(c) for c in mock_logger.info.call_args_list]
        assert any("Created" in msg or "created" in msg.lower() for msg in log_messages)
