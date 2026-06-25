"""Version comparison utilities for MCP Registry"""

from packaging import version
from typing import Tuple
import logging

logger = logging.getLogger(__name__)


def parse_semver(version_str: str) -> version.Version:
    """
    Parse and validate a semantic version string.

    Args:
        version_str: Version string (e.g., "1.2.0", "2.0.0-beta")

    Returns:
        Parsed Version object

    Raises:
        ValueError: If version string is invalid
    """
    try:
        v = version.parse(version_str)
        # Ensure it's a proper version, not LegacyVersion
        if not isinstance(v, version.Version):
            raise ValueError(f"Invalid version format: {version_str}")
        return v
    except Exception as e:
        logger.error(f"Failed to parse version '{version_str}': {e}")
        raise ValueError(f"Invalid semver format: {version_str}")


def is_newer_version(new_version: str, current_version: str) -> bool:
    """
    Check if new_version is strictly newer than current_version.

    Args:
        new_version: The new version to check
        current_version: The current/existing version

    Returns:
        True if new_version > current_version, False otherwise

    Examples:
        >>> is_newer_version("1.2.0", "1.1.0")
        True
        >>> is_newer_version("1.0.0", "1.1.0")
        False
        >>> is_newer_version("2.0.0-beta", "1.9.9")
        True
    """
    try:
        new_v = parse_semver(new_version)
        current_v = parse_semver(current_version)
        return new_v > current_v
    except ValueError:
        logger.error(f"Version comparison failed: {new_version} vs {current_version}")
        raise


def is_same_or_newer_version(new_version: str, current_version: str) -> bool:
    """
    Check if new_version is same or newer than current_version.

    Args:
        new_version: The new version to check
        current_version: The current/existing version

    Returns:
        True if new_version >= current_version, False otherwise
    """
    try:
        new_v = parse_semver(new_version)
        current_v = parse_semver(current_version)
        return new_v >= current_v
    except ValueError:
        logger.error(f"Version comparison failed: {new_version} vs {current_version}")
        raise


def extract_major_minor_patch(version_str: str) -> Tuple[int, int, int]:
    """
    Extract major, minor, and patch numbers from a version string.

    Args:
        version_str: Version string (e.g., "1.2.3")

    Returns:
        Tuple of (major, minor, patch) integers

    Examples:
        >>> extract_major_minor_patch("1.2.3")
        (1, 2, 3)
        >>> extract_major_minor_patch("2.0.0-beta")
        (2, 0, 0)
    """
    v = parse_semver(version_str)
    # packaging uses 'micro' for patch version
    return v.major, v.minor, v.micro


def compare_versions(version1: str, version2: str) -> int:
    """
    Compare two versions and return comparison result.

    Args:
        version1: First version string
        version2: Second version string

    Returns:
        -1 if version1 < version2
         0 if version1 == version2
         1 if version1 > version2

    Examples:
        >>> compare_versions("1.0.0", "1.1.0")
        -1
        >>> compare_versions("2.0.0", "1.9.9")
        1
        >>> compare_versions("1.2.3", "1.2.3")
        0
    """
    v1 = parse_semver(version1)
    v2 = parse_semver(version2)

    if v1 < v2:
        return -1
    elif v1 > v2:
        return 1
    else:
        return 0


def validate_version_format(version_str: str) -> bool:
    """
    Validate if a string is a valid semantic version.

    Args:
        version_str: Version string to validate

    Returns:
        True if valid, False otherwise
    """
    try:
        parse_semver(version_str)
        return True
    except ValueError:
        return False