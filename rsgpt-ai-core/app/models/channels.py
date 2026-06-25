"""Channel definitions and enums for context retrieval"""

from enum import Enum
from typing import Dict


class SourceChannel(str, Enum):
    """Source channels that users can request (high-level interface)"""

    ROC = "ROC"
    DIANA = "DIANA"
    THREE_GSM = "3GSM"
    TWO_SI = "2SI"
    ROCKFIELD = "ROCKFIELD"
    AQUANTY = "AQUANTY"


class Channel(str, Enum):
    """Internal channels for context retrieval (mapped from source channels)"""

    DOCUMENTATION = "documentation"
    TECH_SUPPORT = "tech_support"
    DIANA = "diana"
    THREE_GSM = "three_gsm"
    TWO_SI = "two_si"
    ROCKFIELD = "rockfield"
    AQUANTY = "aquanty"


class UserPermission(str, Enum):
    """User permission levels"""

    BASIC = "basic"
    FLEXIBLE = "flexible"


# Channel to config key mapping
CHANNEL_CONFIG_KEYS: Dict[Channel, str] = {
    Channel.DOCUMENTATION: "documentation",
    Channel.TECH_SUPPORT: "tech_support",
    Channel.DIANA: "diana",
    Channel.THREE_GSM: "three_gsm",
    Channel.TWO_SI: "two_si",
    Channel.ROCKFIELD: "rockfield",
    Channel.AQUANTY: "aquanty",
}


# Two-level mapping: source_channel → permission → internal_channels
SOURCE_CHANNEL_MAPPING: Dict[SourceChannel, Dict[UserPermission, list[Channel]]] = {
    SourceChannel.ROC: {
        UserPermission.BASIC: [Channel.DOCUMENTATION],
        UserPermission.FLEXIBLE: [Channel.DOCUMENTATION, Channel.TECH_SUPPORT],
    },
    SourceChannel.DIANA: {
        UserPermission.BASIC: [Channel.DIANA],
        UserPermission.FLEXIBLE: [Channel.DIANA],
    },
    SourceChannel.THREE_GSM: {
        UserPermission.BASIC: [Channel.THREE_GSM],
        UserPermission.FLEXIBLE: [Channel.THREE_GSM],
    },
    SourceChannel.TWO_SI: {
        UserPermission.BASIC: [Channel.TWO_SI],
        UserPermission.FLEXIBLE: [Channel.TWO_SI],
    },
    SourceChannel.ROCKFIELD: {
        UserPermission.BASIC: [Channel.ROCKFIELD],
        UserPermission.FLEXIBLE: [Channel.ROCKFIELD],
    },
    SourceChannel.AQUANTY: {
        UserPermission.BASIC: [Channel.AQUANTY],
        UserPermission.FLEXIBLE: [Channel.AQUANTY],
    },
}
