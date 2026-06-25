"""Conductor service for mapping source channels to internal channels based on permissions"""

import logging
from typing import List

from app.models.channels import (
    SOURCE_CHANNEL_MAPPING,
    Channel,
    SourceChannel,
    UserPermission,
)

logger = logging.getLogger(__name__)


class ConductorService:
    """
    Service responsible for determining the internal channels to use based on
    source channels and user permission level.

    This matches the SimpleConductor logic from RSGPT-App.
    """

    def __init__(self):
        """Initialize conductor service with channel mapping"""
        self.channel_mapping = SOURCE_CHANNEL_MAPPING

    def conduct(
        self, user_permission: UserPermission, source_channels: List[SourceChannel]
    ) -> List[Channel]:
        """
        Map source channels to internal channels based on user permission.

        Args:
            user_permission: User's permission level (BASIC or FLEXIBLE)
            source_channels: List of source channels requested by the user

        Returns:
            List of internal channels to search

        Raises:
            ValueError: If source_channels is empty

        Example:
            >>> conductor.conduct(UserPermission.BASIC, [SourceChannel.ROC])
            [Channel.DOCUMENTATION]

            >>> conductor.conduct(UserPermission.FLEXIBLE, [SourceChannel.ROC])
            [Channel.DOCUMENTATION, Channel.TECH_SUPPORT]
        """
        if not source_channels:
            raise ValueError("Source channels cannot be empty")

        # Remove duplicates while preserving order
        source_channels = list(dict.fromkeys(source_channels))

        result_channels = []

        for source_channel in source_channels:
            if source_channel not in self.channel_mapping:
                logger.warning(
                    f"Source channel {source_channel} not found in channel mapping"
                )
                continue

            permission_mapping = self.channel_mapping[source_channel]

            if user_permission not in permission_mapping:
                logger.warning(
                    f"User permission {user_permission} not found in channel mapping "
                    f"for source channel {source_channel}"
                )
                continue

            # Get the internal channels for this source channel and permission
            internal_channels = permission_mapping[user_permission]
            result_channels.extend(internal_channels)

        # Remove duplicates while preserving order
        result_channels = list(dict.fromkeys(result_channels))

        logger.debug(
            f"Conductor mapped source_channels={source_channels} with "
            f"permission={user_permission} to internal_channels={result_channels}"
        )

        return result_channels


# Global instance for dependency injection
_conductor_service = None


def get_conductor_service() -> ConductorService:
    """Get the global conductor service instance"""
    global _conductor_service
    if _conductor_service is None:
        _conductor_service = ConductorService()
    return _conductor_service
