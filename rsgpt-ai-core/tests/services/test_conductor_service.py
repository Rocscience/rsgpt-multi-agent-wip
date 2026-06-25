"""Unit tests for conductor service"""

from unittest.mock import patch

import pytest

from app.models.channels import Channel, SourceChannel, UserPermission
from app.services.config import ConductorService, get_conductor_service


class TestConductorService:
    """Test conductor service functionality"""

    @pytest.fixture
    def conductor_service(self):
        """Create a conductor service instance"""
        return ConductorService()

    def test_initialization(self, conductor_service):
        """Test conductor service initializes with channel mapping"""
        assert conductor_service.channel_mapping is not None
        assert len(conductor_service.channel_mapping) > 0

    def test_conduct_roc_basic(self, conductor_service):
        """Test conducting ROC with BASIC permission"""
        result = conductor_service.conduct(UserPermission.BASIC, [SourceChannel.ROC])
        assert result == [Channel.DOCUMENTATION]

    def test_conduct_roc_flexible(self, conductor_service):
        """Test conducting ROC with FLEXIBLE permission"""
        result = conductor_service.conduct(UserPermission.FLEXIBLE, [SourceChannel.ROC])
        assert result == [Channel.DOCUMENTATION, Channel.TECH_SUPPORT]

    def test_conduct_diana_basic(self, conductor_service):
        """Test conducting DIANA with BASIC permission"""
        result = conductor_service.conduct(UserPermission.BASIC, [SourceChannel.DIANA])
        assert result == [Channel.DIANA]

    def test_conduct_diana_flexible(self, conductor_service):
        """Test conducting DIANA with FLEXIBLE permission"""
        result = conductor_service.conduct(
            UserPermission.FLEXIBLE, [SourceChannel.DIANA]
        )
        assert result == [Channel.DIANA]

    def test_conduct_three_gsm_basic(self, conductor_service):
        """Test conducting 3GSM with BASIC permission"""
        result = conductor_service.conduct(
            UserPermission.BASIC, [SourceChannel.THREE_GSM]
        )
        assert result == [Channel.THREE_GSM]

    def test_conduct_three_gsm_flexible(self, conductor_service):
        """Test conducting 3GSM with FLEXIBLE permission"""
        result = conductor_service.conduct(
            UserPermission.FLEXIBLE, [SourceChannel.THREE_GSM]
        )
        assert result == [Channel.THREE_GSM]

    def test_conduct_two_si_basic(self, conductor_service):
        """Test conducting 2SI with BASIC permission"""
        result = conductor_service.conduct(UserPermission.BASIC, [SourceChannel.TWO_SI])
        assert result == [Channel.TWO_SI]

    def test_conduct_two_si_flexible(self, conductor_service):
        """Test conducting 2SI with FLEXIBLE permission"""
        result = conductor_service.conduct(
            UserPermission.FLEXIBLE, [SourceChannel.TWO_SI]
        )
        assert result == [Channel.TWO_SI]

    def test_conduct_multiple_source_channels(self, conductor_service):
        """Test conducting with multiple source channels"""
        result = conductor_service.conduct(
            UserPermission.BASIC, [SourceChannel.DIANA, SourceChannel.THREE_GSM]
        )
        assert Channel.DIANA in result
        assert Channel.THREE_GSM in result
        assert len(result) == 2

    def test_conduct_multiple_with_flexible(self, conductor_service):
        """Test conducting multiple channels with FLEXIBLE permission"""
        result = conductor_service.conduct(
            UserPermission.FLEXIBLE, [SourceChannel.ROC, SourceChannel.DIANA]
        )
        assert Channel.DOCUMENTATION in result
        assert Channel.TECH_SUPPORT in result
        assert Channel.DIANA in result
        assert len(result) == 3

    def test_conduct_removes_duplicates(self, conductor_service):
        """Test that duplicate source channels are removed"""
        result = conductor_service.conduct(
            UserPermission.BASIC,
            [SourceChannel.DIANA, SourceChannel.DIANA, SourceChannel.DIANA],
        )
        assert result == [Channel.DIANA]

    def test_conduct_removes_duplicate_internal_channels(self, conductor_service):
        """Test that duplicate internal channels are removed from result"""
        # If we had a case where multiple source channels map to same internal channel
        # For now, test with current mappings
        result = conductor_service.conduct(
            UserPermission.BASIC, [SourceChannel.DIANA, SourceChannel.THREE_GSM]
        )
        # Check no duplicates
        assert len(result) == len(set(result))

    def test_conduct_preserves_order(self, conductor_service):
        """Test that channel order is preserved"""
        result = conductor_service.conduct(
            UserPermission.BASIC,
            [SourceChannel.THREE_GSM, SourceChannel.DIANA, SourceChannel.TWO_SI],
        )
        assert result[0] == Channel.THREE_GSM
        assert result[1] == Channel.DIANA
        assert result[2] == Channel.TWO_SI

    def test_conduct_empty_source_channels_raises_error(self, conductor_service):
        """Test that empty source channels raises ValueError"""
        with pytest.raises(ValueError, match="Source channels cannot be empty"):
            conductor_service.conduct(UserPermission.BASIC, [])

    @patch("app.services.config.conductor_service.logger")
    def test_conduct_invalid_source_channel_logs_warning(
        self, mock_logger, conductor_service
    ):
        """Test that invalid source channel logs warning"""
        # Save reference to original mapping
        from app.models.channels import SOURCE_CHANNEL_MAPPING

        original_diana_mapping = SOURCE_CHANNEL_MAPPING[SourceChannel.DIANA]

        try:
            # Remove a channel from mapping to simulate missing
            del SOURCE_CHANNEL_MAPPING[SourceChannel.DIANA]

            result = conductor_service.conduct(
                UserPermission.BASIC, [SourceChannel.DIANA, SourceChannel.ROC]
            )

            # Should still get ROC channel
            assert result == [Channel.DOCUMENTATION]
            # Should log warning
            mock_logger.warning.assert_called()
        finally:
            # Restore the original mapping
            SOURCE_CHANNEL_MAPPING[SourceChannel.DIANA] = original_diana_mapping

    @patch("app.services.config.conductor_service.logger")
    def test_conduct_invalid_permission_logs_warning(
        self, mock_logger, conductor_service
    ):
        """Test that invalid permission logs warning"""
        # Save original mapping
        from app.models.channels import SOURCE_CHANNEL_MAPPING

        original_basic = SOURCE_CHANNEL_MAPPING[SourceChannel.DIANA][
            UserPermission.BASIC
        ]

        try:
            # Temporarily remove BASIC permission
            del SOURCE_CHANNEL_MAPPING[SourceChannel.DIANA][UserPermission.BASIC]

            result = conductor_service.conduct(
                UserPermission.BASIC, [SourceChannel.DIANA]
            )

            # Should return empty list
            assert result == []
            # Should log warning
            mock_logger.warning.assert_called()
        finally:
            # Restore original mapping
            SOURCE_CHANNEL_MAPPING[SourceChannel.DIANA][
                UserPermission.BASIC
            ] = original_basic

    @patch("app.services.config.conductor_service.logger")
    def test_conduct_logs_debug_message(self, mock_logger, conductor_service):
        """Test that conduct logs debug message"""
        conductor_service.conduct(UserPermission.BASIC, [SourceChannel.DIANA])
        mock_logger.debug.assert_called_once()


class TestGetConductorService:
    """Test conductor service singleton getter"""

    def test_get_conductor_service_returns_instance(self):
        """Test that get_conductor_service returns a ConductorService instance"""
        service = get_conductor_service()
        assert isinstance(service, ConductorService)

    def test_get_conductor_service_returns_same_instance(self):
        """Test that get_conductor_service returns the same instance"""
        service1 = get_conductor_service()
        service2 = get_conductor_service()
        assert service1 is service2

    @patch("app.services.config.conductor_service._conductor_service", None)
    def test_get_conductor_service_creates_instance_if_none(self):
        """Test that get_conductor_service creates instance if none exists"""
        service = get_conductor_service()
        assert service is not None
        assert isinstance(service, ConductorService)
