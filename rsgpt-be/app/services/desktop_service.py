"""Service layer for Desktop application releases"""

import logging
from typing import Optional

import boto3
from botocore.exceptions import ClientError

from app.config import settings
from app.models.mcp_registry import S3DownloadResponse
from app.services.s3_service import get_s3_service

logger = logging.getLogger(__name__)

# S3 key prefix for the latest desktop release
DESKTOP_LATEST_PREFIX = "rsinsight-desktop/latest/"

# Presigned URL expiration time in seconds
# 15 minutes is industry standard - long enough for slow connections,
# short enough to limit URL sharing. Downloads continue even if URL
# expires mid-download.
PRESIGNED_URL_EXPIRATION_SECONDS = 900


class DesktopReleaseNotFoundError(Exception):
    """Raised when no desktop release is found in S3."""
    pass


class DesktopInstallerNotFoundError(Exception):
    """Raised when no .exe installer file is found in the release folder."""
    pass


class DesktopService:
    """Service class for Desktop application release operations"""

    def __init__(self):
        self.s3_client = boto3.client('s3', region_name=settings.aws_region)
        self.bucket = settings.desktop_releases_s3_bucket

    def get_latest_release_presigned_url(self) -> S3DownloadResponse:
        """
        Get a presigned URL for the latest desktop release.

        Finds the latest .exe file in the rsinsight-desktop/latest/ folder
        and generates a presigned download URL.

        Returns:
            S3DownloadResponse with download URL and file info

        Raises:
            DesktopReleaseNotFoundError: If no objects exist in the latest folder
            DesktopInstallerNotFoundError: If no .exe file is found
            ClientError: If S3 operation fails
        """
        try:
            logger.info(f"Looking for latest desktop release in s3://{self.bucket}/{DESKTOP_LATEST_PREFIX}")

            # List objects in the latest folder
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket,
                Prefix=DESKTOP_LATEST_PREFIX
            )

            if 'Contents' not in response:
                error_msg = f"No desktop release found in s3://{self.bucket}/{DESKTOP_LATEST_PREFIX}"
                logger.error(error_msg)
                raise DesktopReleaseNotFoundError(error_msg)

            # Find the .exe file (exclude .blockmap files)
            exe_object = None
            for obj in response['Contents']:
                key = obj['Key']
                if key.endswith('.exe') and '.blockmap' not in key:
                    exe_object = obj
                    break

            if not exe_object:
                error_msg = f"No installer (.exe) file found in s3://{self.bucket}/{DESKTOP_LATEST_PREFIX}"
                logger.error(error_msg)
                raise DesktopInstallerNotFoundError(error_msg)

            s3_key = exe_object['Key']
            file_size = exe_object.get('Size')

            # Extract filename from the key
            filename = s3_key.split('/')[-1]

            logger.info(f"Found latest release: {filename} ({file_size} bytes)")

            # Generate presigned URL using the S3 service
            s3_service = get_s3_service()
            presigned_url, expires_at = s3_service.generate_presigned_url(
                s3_key=s3_key,
                bucket=self.bucket,
                expires_in=PRESIGNED_URL_EXPIRATION_SECONDS
            )

            logger.info(f"Generated presigned URL for {filename}, expires at {expires_at}")

            return S3DownloadResponse(
                download_url=presigned_url,
                checksum_sha256=None,  # Could be added later from latest.yml
                filename=filename,
                size_bytes=file_size
            )

        except (DesktopReleaseNotFoundError, DesktopInstallerNotFoundError):
            # Re-raise our custom exceptions
            raise
        except ClientError as e:
            logger.error(f"S3 error getting latest desktop release: {e}")
            raise
        except Exception as e:
            logger.error(f"Error getting latest desktop release: {e}")
            raise


# Singleton instance
_desktop_service_instance: Optional[DesktopService] = None


def get_desktop_service() -> DesktopService:
    """
    Get or create the singleton DesktopService instance.

    Returns:
        DesktopService instance
    """
    global _desktop_service_instance
    if _desktop_service_instance is None:
        _desktop_service_instance = DesktopService()
    return _desktop_service_instance