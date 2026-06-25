"""Desktop application API endpoints"""

import logging
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Depends

from app.models.mcp_registry import S3DownloadResponse
from app.services.desktop_service import (
    get_desktop_service,
    DesktopReleaseNotFoundError,
    DesktopInstallerNotFoundError
)
from app.dependencies import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/desktop", tags=["Desktop"])


@router.get("/get-presigned-url", response_model=S3DownloadResponse)
async def get_desktop_presigned_url(
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> S3DownloadResponse:
    """
    Get a presigned URL for the latest RSInsight Desktop release.

    This endpoint requires authentication and returns a time-limited (15 min)
    presigned URL that allows downloading the latest desktop installer from S3.

    Args:
        current_user: Authenticated user from JWT token (injected by Depends)

    Returns:
        S3DownloadResponse with:
        - download_url: Presigned URL for downloading the installer (expires in 15 min)
        - filename: Name of the installer file
        - size_bytes: Size of the installer in bytes
        - checksum_sha256: SHA256 checksum (if available)

    Raises:
        HTTPException 401: If user is not authenticated
        HTTPException 500: If no release is found in S3 (DesktopReleaseNotFoundError)
        HTTPException 500: If no installer file exists (DesktopInstallerNotFoundError)
        HTTPException 500: If an S3 or other error occurs
    """
    try:
        desktop_service = get_desktop_service()
        download_info = desktop_service.get_latest_release_presigned_url()
        return download_info

    except DesktopReleaseNotFoundError as e:
        # No release folder/objects in S3 - this is a server configuration issue
        logger.error(f"Desktop release not found: {e}")
        raise HTTPException(
            status_code=500,
            detail="Desktop release not available. No release found in storage."
        )

    except DesktopInstallerNotFoundError as e:
        # Release folder exists but no .exe file - corrupted release or deployment issue
        logger.error(f"Desktop installer not found: {e}")
        raise HTTPException(
            status_code=500,
            detail="Desktop release not available. Installer file missing."
        )

    except Exception as e:
        # S3 errors or other unexpected errors
        logger.error(f"Error getting desktop presigned URL: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to generate download URL. Please try again later."
        )