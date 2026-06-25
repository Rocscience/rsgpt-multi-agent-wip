"""S3 Service for managing MCP releases storage and presigned URLs"""

import logging
from datetime import datetime, timedelta
from typing import Tuple, Optional

import boto3
from botocore.exceptions import ClientError, NoCredentialsError

from app.config import settings

logger = logging.getLogger(__name__)


class S3Service:
    """Service for generating presigned URLs for MCP releases stored in S3"""

    def __init__(self):
        """Initialize S3 client with AWS credentials from ECS task role"""
        try:
            # In production (ECS), boto3 automatically uses the task role
            # In development, it will use AWS CLI credentials or environment variables
            self.s3_client = boto3.client('s3', region_name=settings.aws_region)
            self.default_bucket = settings.mcp_releases_s3_bucket
            logger.info(
                f"S3Service initialized with region={settings.aws_region}, "
                f"bucket={self.default_bucket}"
            )
        except NoCredentialsError:
            logger.error(
                "No AWS credentials found. In production, ensure ECS task role "
                "has S3 permissions. In development, configure AWS CLI or set "
                "AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY environment variables."
            )
            raise
        except Exception as e:
            logger.error(f"Failed to initialize S3 client: {e}")
            raise

    def generate_presigned_url(
        self,
        s3_key: str,
        bucket: Optional[str] = None,
        expires_in: int = 900  # 15 minutes default
    ) -> Tuple[str, datetime]:
        """
        Generate a presigned URL for downloading an S3 object.

        Args:
            s3_key: S3 object key (e.g., "rs2-server/v1.0.0/rs2-server-v1.0.0.exe")
            bucket: S3 bucket name (uses default if not provided)
            expires_in: URL expiration time in seconds (default: 900 = 15 minutes)

        Returns:
            Tuple of (presigned_url, expires_at_datetime)

        Raises:
            ClientError: If S3 operation fails
            ValueError: If s3_key is empty or invalid
        """
        if not s3_key or not s3_key.strip():
            raise ValueError("s3_key cannot be empty")

        bucket = bucket or self.default_bucket
        if not bucket:
            raise ValueError("S3 bucket not configured")

        try:
            # Generate presigned URL
            presigned_url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': bucket,
                    'Key': s3_key
                },
                ExpiresIn=expires_in
            )

            # Calculate expiration timestamp
            expires_at = datetime.utcnow() + timedelta(seconds=expires_in)

            logger.info(
                f"Generated presigned URL for s3://{bucket}/{s3_key}, "
                f"expires in {expires_in}s at {expires_at.isoformat()}"
            )

            return presigned_url, expires_at

        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            logger.error(
                f"Failed to generate presigned URL for s3://{bucket}/{s3_key}: "
                f"{error_code} - {str(e)}"
            )
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error generating presigned URL for "
                f"s3://{bucket}/{s3_key}: {str(e)}"
            )
            raise

    def check_object_exists(self, s3_key: str, bucket: Optional[str] = None) -> bool:
        """
        Check if an S3 object exists.

        Args:
            s3_key: S3 object key
            bucket: S3 bucket name (uses default if not provided)

        Returns:
            True if object exists, False otherwise
        """
        bucket = bucket or self.default_bucket
        try:
            self.s3_client.head_object(Bucket=bucket, Key=s3_key)
            return True
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                return False
            # Re-raise other errors (permissions, etc.)
            logger.error(f"Error checking if s3://{bucket}/{s3_key} exists: {e}")
            raise

    def get_object_metadata(self, s3_key: str, bucket: Optional[str] = None) -> dict:
        """
        Get metadata for an S3 object.

        Args:
            s3_key: S3 object key
            bucket: S3 bucket name (uses default if not provided)

        Returns:
            Dictionary with metadata (ContentLength, ContentType, ETag, etc.)

        Raises:
            ClientError: If object doesn't exist or other S3 error occurs
        """
        bucket = bucket or self.default_bucket
        try:
            response = self.s3_client.head_object(Bucket=bucket, Key=s3_key)
            return {
                'content_length': response.get('ContentLength'),
                'content_type': response.get('ContentType'),
                'etag': response.get('ETag'),
                'last_modified': response.get('LastModified'),
                'metadata': response.get('Metadata', {})
            }
        except ClientError as e:
            logger.error(f"Failed to get metadata for s3://{bucket}/{s3_key}: {e}")
            raise


# Singleton instance
_s3_service_instance: Optional[S3Service] = None


def get_s3_service() -> S3Service:
    """
    Get or create the singleton S3Service instance.

    Returns:
        S3Service instance
    """
    global _s3_service_instance
    if _s3_service_instance is None:
        _s3_service_instance = S3Service()
    return _s3_service_instance
