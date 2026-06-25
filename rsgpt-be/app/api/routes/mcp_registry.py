"""MCP Registry API endpoints"""

import logging
from typing import Optional, Dict, Any
from uuid import UUID
from fastapi import APIRouter, HTTPException, Query, Path, Depends

from app.models.mcp_registry import (
    MCPRegistryListRequest,
    MCPRegistryListResponse,
    MCPRegistryDetailResponse,
    MCPDownloadResponse,
    MCPInstallLogRequest,
    MCPInstallLogResponse,
    MCPRegistryRegisterRequest,
    MCPRegistryRegisterResponse
)
from app.services.mcp_registry_service import MCPRegistryService
from app.dependencies import get_current_user, verify_github_actions_token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/mcp/registry", tags=["MCP Registry"])
mcp_service = MCPRegistryService()


@router.get("/list", response_model=MCPRegistryListResponse)
async def get_mcp_list(
    category: Optional[str] = Query(None, description="Filter by category"),
    search: Optional[str] = Query(None, description="Search by name/description"),
    official_only: bool = Query(False, description="Show only official MCPs"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    # TODO: Re-enable auth after testing
    # current_user: Dict[str, Any] = Depends(get_current_user)
) -> MCPRegistryListResponse:
    """
    Get paginated list of available MCP servers

    Returns:
        List of MCP servers with pagination info
    """
    try:
        request = MCPRegistryListRequest(
            category=category,
            search=search,
            official_only=official_only,
            page=page,
            limit=limit
        )

        response = mcp_service.get_mcp_list(request)
        return response

    except Exception as e:
        logger.error(f"Error getting MCP list: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve MCP list")


@router.get("/details/{mcp_id}", response_model=MCPRegistryDetailResponse)
async def get_mcp_details(
    mcp_id: UUID = Path(..., description="MCP Registry ID"),
    # TODO: Re-enable auth after testing
    # current_user: Dict[str, Any] = Depends(get_current_user)
) -> MCPRegistryDetailResponse:
    """
    Get detailed information about a specific MCP server

    Args:
        mcp_id: UUID of the MCP registry entry

    Returns:
        Detailed MCP information including all versions
    """
    try:
        mcp_details = mcp_service.get_mcp_details(mcp_id)

        if not mcp_details:
            raise HTTPException(status_code=404, detail="MCP not found")

        return mcp_details

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting MCP details for {mcp_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve MCP details")


@router.get("/download/{mcp_id}", response_model=MCPDownloadResponse)
async def get_mcp_download_info(
    mcp_id: UUID = Path(..., description="MCP Registry ID"),
    version: Optional[str] = Query(None, description="Specific version to download"),
    # TODO: Re-enable auth after testing
    # current_user: Dict[str, Any] = Depends(get_current_user)
) -> MCPDownloadResponse:
    """
    Get download information for an MCP server

    Args:
        mcp_id: UUID of the MCP registry entry
        version: Optional specific version (defaults to latest)

    Returns:
        Download URL and verification information
    """
    try:
        download_info = mcp_service.get_mcp_download_info(mcp_id, version)

        if not download_info:
            if version:
                raise HTTPException(
                    status_code=404,
                    detail=f"Version {version} not found for MCP"
                )
            else:
                raise HTTPException(status_code=404, detail="MCP not found")

        return download_info

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting download info for MCP {mcp_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve download information")


@router.post("/install-log", response_model=MCPInstallLogResponse)
async def log_mcp_installation(
    install_request: MCPInstallLogRequest,
    current_user: dict = Depends(get_current_user)
) -> MCPInstallLogResponse:
    """
    Log an MCP installation, update, or uninstallation

    This endpoint is called by the Electron app to track MCP installations
    and increment download counts.

    Args:
        install_request: Installation log details

    Returns:
        Confirmation of logged installation
    """
    try:
        # Validate the action
        valid_actions = ["install", "update", "uninstall"]
        if install_request.action not in valid_actions:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid action. Must be one of: {', '.join(valid_actions)}"
            )

        log_response = mcp_service.log_mcp_installation(install_request)
        return log_response

    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"Validation error for install log: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error logging MCP installation: {e}")
        raise HTTPException(status_code=500, detail="Failed to log installation")


@router.get("/download/{mcp_id}/{version}", response_model=MCPDownloadResponse)
async def get_mcp_version_download(
    mcp_id: UUID = Path(..., description="MCP Registry ID"),
    version: str = Path(..., description="Version to download"),
    # current_user: Dict[str, Any] = Depends(get_current_user)
) -> MCPDownloadResponse:
    """
    Get download information for a specific version of an MCP server

    Args:
        mcp_id: UUID of the MCP registry entry
        version: Specific version to download

    Returns:
        Download URL and verification information for the specified version
    """
    try:
        download_info = mcp_service.get_mcp_download_info(mcp_id, version)

        if not download_info:
            raise HTTPException(
                status_code=404,
                detail=f"Version {version} not found for MCP"
            )

        return download_info

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting download info for MCP {mcp_id} version {version}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve download information")


@router.post("/register", response_model=MCPRegistryRegisterResponse)
async def register_mcp(
    register_request: MCPRegistryRegisterRequest,
    is_authenticated: bool = Depends(verify_github_actions_token)
) -> MCPRegistryRegisterResponse:
    """
    Register a new MCP server or update an existing one.

    This endpoint is designed to be called by GitHub Actions when a new release
    is published. It handles both creation of new MCPs and updates to existing ones.

    - Creates new MCP if name doesn't exist
    - Updates existing MCP only if version is newer
    - Prevents version downgrades
    - Stores multi-platform download URLs and checksums

    Args:
        register_request: MCP registration details including version, platforms, etc.

    Returns:
        Response indicating success and action taken (created/updated)

    Raises:
        HTTPException: 400 for validation errors, 409 for version conflicts, 500 for server errors

    Examples:
        Create new MCP:
        ```
        POST /mcp/registry/register
        {
            "name": "my-mcp",
            "version": "1.0.0",
            "download_urls": {...}
        }
        Response: 201 {"success": true, "action": "created"}
        ```

        Update existing:
        ```
        POST /mcp/registry/register
        {
            "name": "my-mcp",
            "version": "2.0.0",
            "download_urls": {...}
        }
        Response: 200 {"success": true, "action": "updated"}
        ```
    """
    try:
        logger.info(f"Registration request for MCP '{register_request.name}' version {register_request.version}")

        # Call the service layer to handle registration logic
        response = mcp_service.register_mcp(register_request)

        # Check if registration failed and throw appropriate HTTP error
        if not response.success:
            # Determine appropriate HTTP status code based on error type
            if response.error == "Invalid version format":
                raise HTTPException(
                    status_code=400,
                    detail={
                        "message": response.message,
                        "error": response.error,
                        "details": response.details
                    }
                )
            elif response.error == "Version not newer":
                raise HTTPException(
                    status_code=409,  # Conflict
                    detail={
                        "message": response.message,
                        "error": response.error,
                        "details": response.details
                    }
                )
            else:
                # Generic failure
                raise HTTPException(
                    status_code=400,
                    detail={
                        "message": response.message,
                        "error": response.error,
                        "details": response.details
                    }
                )

        # Success - log and return
        logger.info(f"Successfully {response.action} MCP '{register_request.name}'")
        return response

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Unexpected error registering MCP: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "message": "An unexpected error occurred while registering MCP",
                "error": "Internal server error",
                "details": {"error": str(e)}
            }
        )
