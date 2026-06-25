"""Service layer for MCP Registry business logic"""

import logging
import math
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime

from app.db_interface import mcp_registry as mcp_db
from app.services.s3_service import get_s3_service
from app.models.mcp_registry import (
    MCPRegistryListRequest,
    MCPRegistryListResponse,
    MCPRegistrySummary,
    MCPRegistryDetailResponse,
    MCPVersionInfo,
    MCPDownloadResponse,
    MCPInstallLogRequest,
    MCPInstallLogResponse,
    MCPRegistryCreate,
    MCPRegistryUpdate,
    MCPRegistryRegisterRequest,
    MCPRegistryRegisterResponse
)
from app.utils.version import (
    parse_semver,
    is_newer_version,
    validate_version_format
)

logger = logging.getLogger(__name__)


class MCPRegistryService:
    """Service class for MCP Registry operations"""

    def __init__(self):
        pass

    def get_mcp_list(self, request: MCPRegistryListRequest) -> MCPRegistryListResponse:
        """
        Get paginated list of MCP registries with filters
        """
        try:
            logger.info(f"Getting MCP list - page: {request.page}, category: {request.category}")

            # Get data from database
            mcp_list, total_count = mcp_db.get_mcp_registry_list(
                page=request.page,
                limit=request.limit,
                category=request.category,
                search=request.search,
                official_only=request.official_only,
                active_only=True  # Always filter active only
            )

            # Convert ORM objects to Pydantic models
            mcp_summaries = []
            for mcp in mcp_list:
                summary = MCPRegistrySummary(
                    id=mcp.id,
                    name=mcp.name,
                    display_name=mcp.display_name,
                    description=mcp.description,
                    category=mcp.category,
                    author=mcp.author,
                    latest_version=mcp.latest_version,
                    downloads_count=mcp.downloads_count,
                    is_official=mcp.is_official,
                    # Include version compatibility fields
                    rocscience_app=mcp.rocscience_app,
                    required_app_version=mcp.required_app_version,
                    rocscience_app_path=mcp.rocscience_app_path
                )
                mcp_summaries.append(summary)

            # Calculate total pages
            total_pages = math.ceil(total_count / request.limit) if total_count > 0 else 0

            return MCPRegistryListResponse(
                mcps=mcp_summaries,
                total=total_count,
                page=request.page,
                pages=total_pages
            )

        except Exception as e:
            logger.error(f"Error getting MCP list: {e}")
            raise e

    def get_mcp_details(self, mcp_id: UUID) -> Optional[MCPRegistryDetailResponse]:
        """
        Get full details for a specific MCP server
        """
        try:
            logger.info(f"Getting MCP details for ID: {mcp_id}")

            # Get MCP from database
            mcp = mcp_db.get_mcp_registry_by_id(mcp_id)

            if not mcp:
                logger.warning(f"MCP not found: {mcp_id}")
                return None

            # Get versions
            versions = mcp_db.get_mcp_versions(mcp_id)
            version_info_list = [
                MCPVersionInfo(
                    version=v.version,
                    release_date=v.release_date,
                    release_notes=v.release_notes
                )
                for v in versions
            ]

            # Prepare metadata - handle both extra_metadata field name and potential None
            metadata = mcp.extra_metadata if mcp.extra_metadata else {}

            # Create response
            return MCPRegistryDetailResponse(
                id=mcp.id,
                name=mcp.name,
                display_name=mcp.display_name,
                description=mcp.description,
                category=mcp.category,
                author=mcp.author,
                repo_url=mcp.repo_url,
                latest_version=mcp.latest_version,
                checksum_sha256=mcp.checksum_sha256,
                min_app_version=mcp.min_app_version,
                release_date=mcp.release_date,
                downloads_count=mcp.downloads_count,
                is_official=mcp.is_official,
                is_active=mcp.is_active,
                metadata=metadata,
                versions=version_info_list,
                created_at=mcp.created_at,
                updated_at=mcp.updated_at
            )

        except Exception as e:
            logger.error(f"Error getting MCP details: {e}")
            raise e

    def get_mcp_download_info(
        self,
        mcp_id: UUID,
        version: Optional[str] = None
    ) -> Optional[MCPDownloadResponse]:
        """
        Get download information for a specific MCP version.

        Generates S3 presigned URL for secure, time-limited download access.
        If no version specified, returns latest version.
        """
        try:
            logger.info(f"Getting download info - MCP: {mcp_id}, version: {version}")

            # Get MCP registry
            mcp = mcp_db.get_mcp_registry_by_id(mcp_id)

            if not mcp:
                logger.warning(f"MCP not found: {mcp_id}")
                return None

            # Determine which version to use
            if version and version != mcp.latest_version:
                # Get specific version
                mcp_version = mcp_db.get_mcp_version(mcp_id, version)
                if not mcp_version:
                    logger.warning(f"Version {version} not found for MCP {mcp_id}")
                    return None

                s3_bucket = mcp_version.s3_bucket
                s3_key = mcp_version.s3_key
                file_size = mcp_version.file_size
                checksum = mcp_version.checksum_sha256
                version_str = mcp_version.version
            else:
                # Use latest version from main registry
                s3_bucket = mcp.s3_bucket
                s3_key = mcp.s3_key
                file_size = None  # Not stored in mcp_registry, only in mcp_versions
                checksum = mcp.checksum_sha256
                version_str = mcp.latest_version

            # Generate filename
            filename = f"{mcp.name}-v{version_str}.exe"

            # Generate S3 presigned URL
            logger.info(f"Generating S3 presigned URL for s3://{s3_bucket}/{s3_key}")
            s3_service = get_s3_service()
            presigned_url, expires_at = s3_service.generate_presigned_url(
                s3_key=s3_key,
                bucket=s3_bucket,
                expires_in=900  # 15 minutes
            )

            logger.info(f"S3 presigned URL generated, expires at {expires_at}")

            return MCPDownloadResponse(
                download_url=presigned_url,
                checksum_sha256=checksum,
                filename=filename,
                size_bytes=file_size
            )

        except Exception as e:
            logger.error(f"Error getting download info: {e}")
            raise e

    def log_mcp_installation(
        self, 
        install_request: MCPInstallLogRequest
    ) -> MCPInstallLogResponse:
        """
        Log an MCP installation/update/uninstall action
        """
        try:
            logger.info(
                f"Logging installation - MCP: {install_request.mcp_id}, "
                f"Device: {install_request.device_id}, Action: {install_request.action}"
            )

            # Validate MCP exists
            mcp = mcp_db.get_mcp_registry_by_id(install_request.mcp_id)
            if not mcp:
                raise ValueError(f"MCP not found: {install_request.mcp_id}")

            # Create install log (this also increments download count if action is "install")
            install_log = mcp_db.create_install_log(install_request)

            # Build success message
            action_messages = {
                "install": f"Successfully installed {mcp.display_name} v{install_request.version}",
                "update": f"Successfully updated {mcp.display_name} to v{install_request.version}",
                "uninstall": f"Successfully uninstalled {mcp.display_name}"
            }
            message = action_messages.get(
                install_request.action,
                f"Action {install_request.action} logged for {mcp.display_name}"
            )

            return MCPInstallLogResponse(
                id=install_log.id,
                mcp_id=install_log.mcp_id,
                device_id=install_log.device_id,
                version=install_log.version,
                action=install_log.action,
                installed_at=install_log.installed_at,
                message=message
            )

        except Exception as e:
            logger.error(f"Error logging installation: {e}")
            raise e

    def create_mcp_registry(self, mcp_data: MCPRegistryCreate) -> MCPRegistryDetailResponse:
        """
        Create a new MCP registry entry (admin function)
        """
        try:
            logger.info(f"Creating MCP registry: {mcp_data.name}")

            # Check if name already exists
            existing = mcp_db.get_mcp_registry_by_name(mcp_data.name)
            if existing:
                raise ValueError(f"MCP with name '{mcp_data.name}' already exists")

            # Create the MCP
            mcp = mcp_db.create_mcp_registry(mcp_data)

            # Create initial version entry
            mcp_db.create_mcp_version(
                mcp_id=mcp.id,
                version=mcp.latest_version,
                s3_bucket=mcp_data.s3_bucket,
                s3_key=mcp_data.s3_key,
                checksum_sha256=mcp.checksum_sha256,
                release_notes="Initial release"
            )

            # Return the created MCP details
            return self.get_mcp_details(mcp.id)

        except Exception as e:
            logger.error(f"Error creating MCP registry: {e}")
            raise e

    def update_mcp_registry(
        self, 
        mcp_id: UUID, 
        mcp_update: MCPRegistryUpdate
    ) -> Optional[MCPRegistryDetailResponse]:
        """
        Update an existing MCP registry entry (admin function)
        """
        try:
            logger.info(f"Updating MCP registry: {mcp_id}")

            # Check if updating version
            if mcp_update.latest_version:
                # Get current MCP
                current_mcp = mcp_db.get_mcp_registry_by_id(mcp_id)
                if not current_mcp:
                    return None

                # If version is different, create a new version entry
                if mcp_update.latest_version != current_mcp.latest_version:
                    mcp_db.create_mcp_version(
                        mcp_id=mcp_id,
                        version=mcp_update.latest_version,
                        s3_bucket=mcp_update.s3_bucket or current_mcp.s3_bucket,
                        s3_key=mcp_update.s3_key or current_mcp.s3_key,
                        checksum_sha256=mcp_update.checksum_sha256,
                        release_notes=f"Updated to version {mcp_update.latest_version}"
                    )

            # Update the MCP registry
            mcp = mcp_db.update_mcp_registry(mcp_id, mcp_update)

            if not mcp:
                return None

            # Return updated details
            return self.get_mcp_details(mcp.id)

        except Exception as e:
            logger.error(f"Error updating MCP registry: {e}")
            raise e

    def get_mcp_categories(self) -> List[str]:
        """
        Get list of available MCP categories
        """
        try:
            logger.info("Getting MCP categories")
            return mcp_db.get_mcp_categories()
        except Exception as e:
            logger.error(f"Error getting MCP categories: {e}")
            raise e

    def get_device_installations(self, device_id: UUID) -> List[Dict[str, Any]]:
        """
        Get list of MCPs installed on a specific device
        """
        try:
            logger.info(f"Getting installations for device: {device_id}")

            install_logs = mcp_db.get_device_install_logs(device_id)

            # Group by MCP and get latest installation for each
            mcp_installations = {}
            for log in install_logs:
                if log.action != "uninstall":
                    if log.mcp_id not in mcp_installations or \
                        log.installed_at > mcp_installations[log.mcp_id]['installed_at']:
                        mcp_installations[log.mcp_id] = {
                            'mcp_id': log.mcp_id,
                            'version': log.version,
                            'installed_at': log.installed_at,
                            'action': log.action
                        }

            return list(mcp_installations.values())

        except Exception as e:
            logger.error(f"Error getting device installations: {e}")
            raise e

    def register_mcp(
        self,
        request: MCPRegistryRegisterRequest
    ) -> MCPRegistryRegisterResponse:
        """
        Register a new MCP or update an existing one.

        This method is called by GitHub Actions when a new release is published.
        It handles both creation of new MCPs and updates to existing ones.

        Args:
            request: Registration request from GitHub Actions

        Returns:
            Response indicating success/failure and action taken
        """
        try:
            # Validate version format
            if not validate_version_format(request.version):
                return MCPRegistryRegisterResponse(
                    success=False,
                    error="Invalid version format",
                    message=f"Version '{request.version}' is not a valid semantic version",
                    details={"provided_version": request.version}
                )

            # Check if MCP already exists
            existing_mcp = mcp_db.get_mcp_registry_by_name(request.name)

            if existing_mcp:
                # UPDATE PATH: MCP exists, check if version is newer
                logger.info(f"MCP '{request.name}' exists, checking version")

                # Compare versions
                if not is_newer_version(request.version, existing_mcp.latest_version):
                    return MCPRegistryRegisterResponse(
                        success=False,
                        error="Version not newer",
                        message=f"Version {request.version} is not newer than current version {existing_mcp.latest_version}",
                        details={
                            "current_version": existing_mcp.latest_version,
                            "provided_version": request.version
                        }
                    )

                # Prepare update data
                update_data = MCPRegistryUpdate(
                    display_name=request.display_name,
                    description=request.description,
                    category=request.category,
                    author=request.author,
                    repo_url=request.repo_url,
                    latest_version=request.version,
                    min_app_version=request.min_app_version,
                    checksum_sha256=request.checksums.get("windows", list(request.checksums.values())[0]),
                    release_date=datetime.utcnow(),
                    is_official=request.is_official,
                    s3_bucket=request.s3_bucket,
                    s3_key=request.s3_key,
                    extra_metadata={
                        "checksums": request.checksums,
                        "metadata": request.metadata or {},
                        "platforms": list(request.checksums.keys())
                    },
                    # Rocscience application version compatibility
                    rocscience_app=request.rocscience_app,
                    required_app_version=request.required_app_version,
                    rocscience_app_path=request.rocscience_app_path
                )

                # Update the registry
                updated_mcp = mcp_db.update_mcp_registry(existing_mcp.id, update_data)
                if not updated_mcp:
                    raise Exception("Failed to update MCP registry")

                # Create new version entry
                mcp_db.create_mcp_version(
                    mcp_id=existing_mcp.id,
                    version=request.version,
                    s3_bucket=request.s3_bucket,
                    s3_key=request.s3_key,
                    checksum_sha256=request.checksums.get("windows", list(request.checksums.values())[0]),
                    release_notes=request.release_notes,
                    file_size=request.file_size
                )

                logger.info(f"Successfully updated MCP '{request.name}' to version {request.version}")

                return MCPRegistryRegisterResponse(
                    success=True,
                    mcp_id=existing_mcp.id,
                    message=f"MCP '{request.name}' updated to version {request.version}",
                    action="updated"
                )

            else:
                # CREATE PATH: New MCP registration
                logger.info(f"Registering new MCP: {request.name}")

                # Prepare creation data
                create_data = MCPRegistryCreate(
                    name=request.name,
                    display_name=request.display_name,
                    description=request.description,
                    category=request.category,
                    author=request.author,
                    repo_url=request.repo_url,
                    latest_version=request.version,
                    min_app_version=request.min_app_version,
                    checksum_sha256=request.checksums.get("windows", list(request.checksums.values())[0]),
                    release_date=datetime.utcnow(),
                    is_official=request.is_official,
                    is_active=True,
                    s3_bucket=request.s3_bucket,
                    s3_key=request.s3_key,
                    extra_metadata={
                        "checksums": request.checksums,
                        "metadata": request.metadata or {},
                        "platforms": list(request.checksums.keys())
                    },
                    # Rocscience application version compatibility
                    rocscience_app=request.rocscience_app,
                    required_app_version=request.required_app_version,
                    rocscience_app_path=request.rocscience_app_path
                )

                # Create the MCP registry entry
                new_mcp = mcp_db.create_mcp_registry(create_data)

                # Create initial version entry
                mcp_db.create_mcp_version(
                    mcp_id=new_mcp.id,
                    version=request.version,
                    s3_bucket=request.s3_bucket,
                    s3_key=request.s3_key,
                    checksum_sha256=request.checksums.get("windows", list(request.checksums.values())[0]),
                    release_notes=request.release_notes or "Initial release",
                    file_size=request.file_size
                )

                logger.info(f"Successfully registered new MCP '{request.name}' with version {request.version}")

                return MCPRegistryRegisterResponse(
                    success=True,
                    mcp_id=new_mcp.id,
                    message=f"MCP '{request.name}' registered successfully",
                    action="created"
                )

        except ValueError as ve:
            logger.error(f"Validation error in register_mcp: {ve}")
            return MCPRegistryRegisterResponse(
                success=False,
                error="Validation error",
                message=str(ve),
                details={"validation_error": str(ve)}
            )
        except Exception as e:
            logger.error(f"Unexpected error in register_mcp: {e}", exc_info=True)
            return MCPRegistryRegisterResponse(
                success=False,
                error="Registration failed",
                message="An unexpected error occurred during registration",
                details={"error": str(e)}
            )