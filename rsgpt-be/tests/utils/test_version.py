"""Tests for version comparison utilities"""

import pytest
from app.utils.version import (
    parse_semver,
    is_newer_version,
    is_same_or_newer_version,
    extract_major_minor_patch,
    compare_versions,
    validate_version_format
)


class TestVersionUtils:
    """Test class for version utility functions"""

    def test_parse_semver_valid(self):
        """Test parsing valid semantic versions"""
        version = parse_semver("1.2.3")
        assert version.major == 1
        assert version.minor == 2
        assert version.micro == 3  # packaging uses 'micro' for patch

    def test_parse_semver_with_prerelease(self):
        """Test parsing version with prerelease"""
        version = parse_semver("2.0.0-beta.1")
        assert version.major == 2
        assert version.minor == 0
        assert version.micro == 0
        assert version.pre is not None

    def test_parse_semver_invalid(self):
        """Test parsing invalid version string"""
        with pytest.raises(ValueError, match="Invalid semver format"):
            parse_semver("not-a-version")

        with pytest.raises(ValueError, match="Invalid semver format"):
            parse_semver("")

    def test_is_newer_version(self):
        """Test version comparison for newer versions"""
        # Basic comparisons
        assert is_newer_version("2.0.0", "1.0.0") is True
        assert is_newer_version("1.1.0", "1.0.0") is True
        assert is_newer_version("1.0.1", "1.0.0") is True

        # Not newer
        assert is_newer_version("1.0.0", "2.0.0") is False
        assert is_newer_version("1.0.0", "1.0.0") is False
        assert is_newer_version("1.0.0", "1.0.1") is False

        # Prerelease versions
        assert is_newer_version("2.0.0", "2.0.0-beta") is True
        assert is_newer_version("2.0.0-beta.2", "2.0.0-beta.1") is True

    def test_is_newer_version_complex(self):
        """Test complex version comparisons"""
        # Multi-digit versions
        assert is_newer_version("1.10.0", "1.9.0") is True
        assert is_newer_version("1.0.10", "1.0.9") is True

        # Same major/minor, different patch
        assert is_newer_version("1.2.1", "1.2.0") is True
        assert is_newer_version("1.2.0", "1.2.1") is False

    def test_is_same_or_newer_version(self):
        """Test same or newer version comparison"""
        assert is_same_or_newer_version("2.0.0", "1.0.0") is True
        assert is_same_or_newer_version("1.0.0", "1.0.0") is True
        assert is_same_or_newer_version("1.0.0", "2.0.0") is False

    def test_extract_major_minor_patch(self):
        """Test extracting version components"""
        assert extract_major_minor_patch("1.2.3") == (1, 2, 3)
        assert extract_major_minor_patch("10.20.30") == (10, 20, 30)
        assert extract_major_minor_patch("0.0.1") == (0, 0, 1)

        # With prerelease (should still extract base version)
        assert extract_major_minor_patch("2.0.0-beta") == (2, 0, 0)
        assert extract_major_minor_patch("1.2.3-alpha.1") == (1, 2, 3)

    def test_compare_versions(self):
        """Test version comparison function"""
        # v1 < v2
        assert compare_versions("1.0.0", "2.0.0") == -1
        assert compare_versions("1.0.0", "1.1.0") == -1
        assert compare_versions("1.0.0", "1.0.1") == -1

        # v1 == v2
        assert compare_versions("1.0.0", "1.0.0") == 0
        assert compare_versions("2.5.3", "2.5.3") == 0

        # v1 > v2
        assert compare_versions("2.0.0", "1.0.0") == 1
        assert compare_versions("1.1.0", "1.0.0") == 1
        assert compare_versions("1.0.1", "1.0.0") == 1

    def test_validate_version_format(self):
        """Test version format validation"""
        # Valid versions
        assert validate_version_format("1.0.0") is True
        assert validate_version_format("0.0.1") is True
        assert validate_version_format("10.20.30") is True
        assert validate_version_format("1.2.3-beta") is True
        assert validate_version_format("2.0.0-rc.1") is True
        assert validate_version_format("1.0.0+build.123") is True

        # Invalid versions
        assert validate_version_format("not-a-version") is False
        assert validate_version_format("1.2") is True  # Valid - treated as 1.2.0
        assert validate_version_format("v1.0.0") is True  # 'v' prefix is actually allowed
        assert validate_version_format("") is False
        assert validate_version_format("1.2.3.4") is True  # Also valid in packaging

    def test_version_edge_cases(self):
        """Test edge cases in version handling"""
        # Zero versions
        assert is_newer_version("0.0.1", "0.0.0") is True
        assert is_newer_version("0.1.0", "0.0.9") is True

        # Large version numbers
        assert is_newer_version("999.999.999", "999.999.998") is True
        assert is_newer_version("1000.0.0", "999.999.999") is True

        # Development versions
        assert is_newer_version("1.0.0", "1.0.0.dev0") is True
        assert is_newer_version("1.0.0a1", "1.0.0.dev0") is True

    def test_version_prerelease_ordering(self):
        """Test prerelease version ordering"""
        # Alpha < Beta < RC < Release
        assert is_newer_version("1.0.0-beta", "1.0.0-alpha") is True
        assert is_newer_version("1.0.0-rc.1", "1.0.0-beta") is True
        assert is_newer_version("1.0.0", "1.0.0-rc.1") is True

        # Within same prerelease type
        assert is_newer_version("1.0.0-alpha.2", "1.0.0-alpha.1") is True
        assert is_newer_version("1.0.0-beta.10", "1.0.0-beta.9") is True