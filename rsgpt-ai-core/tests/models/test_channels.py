"""Unit tests for channel models and mappings"""

import pytest

from app.models.channels import (
    CHANNEL_CONFIG_KEYS,
    SOURCE_CHANNEL_MAPPING,
    Channel,
    SourceChannel,
    UserPermission,
)


class TestChannelEnums:
    """Test channel enum definitions"""

    def test_source_channel_values(self):
        """Test all source channel enum values"""
        assert SourceChannel.ROC.value == "ROC"
        assert SourceChannel.DIANA.value == "DIANA"
        assert SourceChannel.THREE_GSM.value == "3GSM"
        assert SourceChannel.TWO_SI.value == "2SI"
        assert SourceChannel.ROCKFIELD.value == "ROCKFIELD"
        assert SourceChannel.AQUANTY.value == "AQUANTY"

    def test_channel_values(self):
        """Test all internal channel enum values"""
        assert Channel.DOCUMENTATION.value == "documentation"
        assert Channel.TECH_SUPPORT.value == "tech_support"
        assert Channel.DIANA.value == "diana"
        assert Channel.THREE_GSM.value == "three_gsm"
        assert Channel.TWO_SI.value == "two_si"
        assert Channel.ROCKFIELD.value == "rockfield"
        assert Channel.AQUANTY.value == "aquanty"

    def test_user_permission_values(self):
        """Test all user permission enum values"""
        assert UserPermission.BASIC.value == "basic"
        assert UserPermission.FLEXIBLE.value == "flexible"

    def test_source_channel_enum_membership(self):
        """Test source channel enum membership"""
        assert SourceChannel.ROC in SourceChannel
        assert SourceChannel.DIANA in SourceChannel
        assert SourceChannel.THREE_GSM in SourceChannel
        assert SourceChannel.TWO_SI in SourceChannel
        assert SourceChannel.ROCKFIELD in SourceChannel
        assert SourceChannel.AQUANTY in SourceChannel

    def test_channel_enum_membership(self):
        """Test internal channel enum membership"""
        assert Channel.DOCUMENTATION in Channel
        assert Channel.TECH_SUPPORT in Channel
        assert Channel.DIANA in Channel
        assert Channel.THREE_GSM in Channel
        assert Channel.TWO_SI in Channel
        assert Channel.ROCKFIELD in Channel
        assert Channel.AQUANTY in Channel


class TestChannelConfigKeys:
    """Test channel config key mappings"""

    def test_all_channels_have_config_keys(self):
        """Test that all internal channels have config key mappings"""
        for channel in Channel:
            assert channel in CHANNEL_CONFIG_KEYS

    def test_config_key_values(self):
        """Test specific config key mappings"""
        assert CHANNEL_CONFIG_KEYS[Channel.DOCUMENTATION] == "documentation"
        assert CHANNEL_CONFIG_KEYS[Channel.TECH_SUPPORT] == "tech_support"
        assert CHANNEL_CONFIG_KEYS[Channel.DIANA] == "diana"
        assert CHANNEL_CONFIG_KEYS[Channel.THREE_GSM] == "three_gsm"
        assert CHANNEL_CONFIG_KEYS[Channel.TWO_SI] == "two_si"
        assert CHANNEL_CONFIG_KEYS[Channel.ROCKFIELD] == "rockfield"
        assert CHANNEL_CONFIG_KEYS[Channel.AQUANTY] == "aquanty"

    def test_config_keys_match_channel_values(self):
        """Test that config keys match channel enum values"""
        for channel, config_key in CHANNEL_CONFIG_KEYS.items():
            assert channel.value == config_key


class TestSourceChannelMapping:
    """Test source channel to internal channel mappings"""

    def test_all_source_channels_mapped(self):
        """Test that all source channels have mappings"""
        for source_channel in SourceChannel:
            assert source_channel in SOURCE_CHANNEL_MAPPING

    def test_all_source_channels_have_both_permissions(self):
        """Test that all source channels have BASIC and FLEXIBLE permissions"""
        for source_channel in SourceChannel:
            assert UserPermission.BASIC in SOURCE_CHANNEL_MAPPING[source_channel]
            assert UserPermission.FLEXIBLE in SOURCE_CHANNEL_MAPPING[source_channel]

    def test_roc_basic_mapping(self):
        """Test ROC basic permission mapping"""
        channels = SOURCE_CHANNEL_MAPPING[SourceChannel.ROC][UserPermission.BASIC]
        assert channels == [Channel.DOCUMENTATION]

    def test_roc_flexible_mapping(self):
        """Test ROC flexible permission mapping"""
        channels = SOURCE_CHANNEL_MAPPING[SourceChannel.ROC][UserPermission.FLEXIBLE]
        assert channels == [Channel.DOCUMENTATION, Channel.TECH_SUPPORT]

    def test_diana_basic_mapping(self):
        """Test DIANA basic permission mapping"""
        channels = SOURCE_CHANNEL_MAPPING[SourceChannel.DIANA][UserPermission.BASIC]
        assert channels == [Channel.DIANA]

    def test_diana_flexible_mapping(self):
        """Test DIANA flexible permission mapping"""
        channels = SOURCE_CHANNEL_MAPPING[SourceChannel.DIANA][UserPermission.FLEXIBLE]
        assert channels == [Channel.DIANA]

    def test_three_gsm_basic_mapping(self):
        """Test 3GSM basic permission mapping"""
        channels = SOURCE_CHANNEL_MAPPING[SourceChannel.THREE_GSM][UserPermission.BASIC]
        assert channels == [Channel.THREE_GSM]

    def test_three_gsm_flexible_mapping(self):
        """Test 3GSM flexible permission mapping"""
        channels = SOURCE_CHANNEL_MAPPING[SourceChannel.THREE_GSM][
            UserPermission.FLEXIBLE
        ]
        assert channels == [Channel.THREE_GSM]

    def test_two_si_basic_mapping(self):
        """Test 2SI basic permission mapping"""
        channels = SOURCE_CHANNEL_MAPPING[SourceChannel.TWO_SI][UserPermission.BASIC]
        assert channels == [Channel.TWO_SI]

    def test_two_si_flexible_mapping(self):
        """Test 2SI flexible permission mapping"""
        channels = SOURCE_CHANNEL_MAPPING[SourceChannel.TWO_SI][UserPermission.FLEXIBLE]
        assert channels == [Channel.TWO_SI]

    def test_rockfield_basic_mapping(self):
        """Test Rockfield basic permission mapping"""
        channels = SOURCE_CHANNEL_MAPPING[SourceChannel.ROCKFIELD][UserPermission.BASIC]
        assert channels == [Channel.ROCKFIELD]

    def test_rockfield_flexible_mapping(self):
        """Test Rockfield flexible permission mapping"""
        channels = SOURCE_CHANNEL_MAPPING[SourceChannel.ROCKFIELD][
            UserPermission.FLEXIBLE
        ]
        assert channels == [Channel.ROCKFIELD]

    def test_aquanty_basic_mapping(self):
        """Test Aquanty basic permission mapping"""
        channels = SOURCE_CHANNEL_MAPPING[SourceChannel.AQUANTY][UserPermission.BASIC]
        assert channels == [Channel.AQUANTY]

    def test_aquanty_flexible_mapping(self):
        """Test Aquanty flexible permission mapping"""
        channels = SOURCE_CHANNEL_MAPPING[SourceChannel.AQUANTY][
            UserPermission.FLEXIBLE
        ]
        assert channels == [Channel.AQUANTY]

    def test_mapping_returns_list_of_channels(self):
        """Test that all mappings return lists of Channel enums"""
        for source_channel, permission_map in SOURCE_CHANNEL_MAPPING.items():
            for permission, channels in permission_map.items():
                assert isinstance(channels, list)
                assert all(isinstance(ch, Channel) for ch in channels)

    def test_mapping_no_empty_lists(self):
        """Test that no mapping returns an empty list"""
        for source_channel, permission_map in SOURCE_CHANNEL_MAPPING.items():
            for permission, channels in permission_map.items():
                assert len(channels) > 0
