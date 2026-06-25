"""Database interface for MCP Registry operations"""

import logging
from typing import Optional, List, Tuple
from uuid import UUID
from datetime import datetime
from sqlalchemy import select, func, or_, and_, desc
from sqlalchemy.orm import selectinload

from app.db_models.mcp_registry import MCPRegistryORM, MCPVersionsORM
from app.db_models.mcp_install_logs import MCPInstallLogsORM
from app.models.mcp_registry import (
    MCPRegistryCreate,
    MCPRegistryUpdate,
    MCPInstallLogRequest
)
from app.db_models.connection import Session, with_db_retry

logger = logging.getLogger(__name__)


@with_db_retry(max_retries=3, retry_delay=1.0)
def get_mcp_registry_list(
    page: int = 1,
    limit: int = 20,
    category: Optional[str] = None,
    search: Optional[str] = None,
    official_only: bool = False,
    active_only: bool = True
) -> Tuple[List[MCPRegistryORM], int]:
    """
    Get paginated list of MCP registries with filters
    Returns tuple of (mcps, total_count)
    """
    with Session() as session:
        query = session.query(MCPRegistryORM)

        # Apply filters
        if active_only:
            query = query.filter(MCPRegistryORM.is_active == True)

        if official_only:
            query = query.filter(MCPRegistryORM.is_official == True)

        if category:
            query = query.filter(MCPRegistryORM.category == category)

        if search:
            search_term = f"%{search}%"
            query = query.filter(
                or_(
                    MCPRegistryORM.name.ilike(search_term),
                    MCPRegistryORM.display_name.ilike(search_term),
                    MCPRegistryORM.description.ilike(search_term)
                )
            )

        # Get total count
        total_count = query.count()

        # Order by downloads count descending (must come before offset/limit)
        query = query.order_by(desc(MCPRegistryORM.downloads_count))

        # Apply pagination
        offset = (page - 1) * limit
        query = query.offset(offset).limit(limit)

        mcps = query.all()
        for mcp in mcps:
            session.expunge(mcp)
        return mcps, total_count


@with_db_retry(max_retries=3, retry_delay=1.0)
def get_mcp_registry_by_id(mcp_id: UUID) -> Optional[MCPRegistryORM]:
    """Get an MCP registry by ID"""
    with Session() as session:
        mcp = session.query(MCPRegistryORM).filter(
            MCPRegistryORM.id == mcp_id
        ).first()
        if mcp:
            session.expunge(mcp)
        return mcp


@with_db_retry(max_retries=3, retry_delay=1.0)
def get_mcp_registry_by_name(name: str) -> Optional[MCPRegistryORM]:
    """Get an MCP registry by name"""
    with Session() as session:
        mcp = session.query(MCPRegistryORM).filter(
            MCPRegistryORM.name == name
        ).first()
        if mcp:
            session.expunge(mcp)
        return mcp


@with_db_retry(max_retries=3, retry_delay=1.0)
def get_mcp_versions(mcp_id: UUID) -> List[MCPVersionsORM]:
    """Get all versions for an MCP"""
    with Session() as session:
        versions = session.query(MCPVersionsORM).filter(
            MCPVersionsORM.mcp_id == mcp_id
        ).order_by(desc(MCPVersionsORM.release_date)).all()
        for version in versions:
            session.expunge(version)
        return versions


@with_db_retry(max_retries=3, retry_delay=1.0)
def get_mcp_version(mcp_id: UUID, version: str) -> Optional[MCPVersionsORM]:
    """Get a specific version for an MCP"""
    with Session() as session:
        mcp_version = session.query(MCPVersionsORM).filter(
            and_(
                MCPVersionsORM.mcp_id == mcp_id,
                MCPVersionsORM.version == version
            )
        ).first()
        if mcp_version:
            session.expunge(mcp_version)
        return mcp_version


@with_db_retry(max_retries=3, retry_delay=1.0)
def create_mcp_registry(mcp_data: MCPRegistryCreate) -> MCPRegistryORM:
    """Create a new MCP registry entry"""
    with Session() as session:
        mcp = MCPRegistryORM(
            name=mcp_data.name,
            display_name=mcp_data.display_name,
            description=mcp_data.description,
            category=mcp_data.category,
            author=mcp_data.author,
            repo_url=mcp_data.repo_url,
            latest_version=mcp_data.latest_version,
            min_app_version=mcp_data.min_app_version,
            s3_bucket=mcp_data.s3_bucket,
            s3_key=mcp_data.s3_key,
            checksum_sha256=mcp_data.checksum_sha256,
            release_date=mcp_data.release_date,
            downloads_count=0,
            is_official=mcp_data.is_official,
            is_active=mcp_data.is_active,
            extra_metadata=mcp_data.extra_metadata,
            # Rocscience application version compatibility
            rocscience_app=mcp_data.rocscience_app,
            required_app_version=mcp_data.required_app_version,
            rocscience_app_path=mcp_data.rocscience_app_path
        )
        session.add(mcp)
        session.commit()
        session.refresh(mcp)
        session.expunge(mcp)
        return mcp


@with_db_retry(max_retries=3, retry_delay=1.0)
def update_mcp_registry(
    mcp_id: UUID,
    mcp_update: MCPRegistryUpdate
) -> Optional[MCPRegistryORM]:
    """Update an existing MCP registry entry"""
    with Session() as session:
        mcp = session.query(MCPRegistryORM).filter(
            MCPRegistryORM.id == mcp_id
        ).first()

        if not mcp:
            return None

        # Update only provided fields
        update_data = mcp_update.dict(exclude_unset=True)
        for field, value in update_data.items():
            if hasattr(mcp, field):
                setattr(mcp, field, value)

        session.commit()
        session.refresh(mcp)
        session.expunge(mcp)
        return mcp


@with_db_retry(max_retries=3, retry_delay=1.0)
def create_mcp_version(
    mcp_id: UUID,
    version: str,
    s3_bucket: str,
    s3_key: str,
    checksum_sha256: Optional[str] = None,
    release_notes: Optional[str] = None,
    file_size: Optional[int] = None
) -> MCPVersionsORM:
    """Create a new version entry for an MCP"""
    with Session() as session:
        mcp_version = MCPVersionsORM(
            mcp_id=mcp_id,
            version=version,
            s3_bucket=s3_bucket,
            s3_key=s3_key,
            checksum_sha256=checksum_sha256,
            release_notes=release_notes,
            release_date=datetime.utcnow(),
            file_size=file_size
        )
        session.add(mcp_version)
        session.commit()
        session.refresh(mcp_version)
        session.expunge(mcp_version)
        return mcp_version


@with_db_retry(max_retries=3, retry_delay=1.0)
def create_install_log(
    install_data: MCPInstallLogRequest
) -> MCPInstallLogsORM:
    """Create an installation log entry"""
    with Session() as session:
        install_log = MCPInstallLogsORM(
            mcp_id=install_data.mcp_id,
            device_id=install_data.device_id,
            version=install_data.version,
            action=install_data.action,
            installed_at=datetime.utcnow()
        )
        session.add(install_log)

        # Increment download count for install actions
        if install_data.action == "install":
            mcp = session.query(MCPRegistryORM).filter(
                MCPRegistryORM.id == install_data.mcp_id
            ).first()
            if mcp:
                mcp.downloads_count += 1

        session.commit()
        session.refresh(install_log)
        session.expunge(install_log)
        return install_log


@with_db_retry(max_retries=3, retry_delay=1.0)
def get_device_install_logs(device_id: UUID) -> List[MCPInstallLogsORM]:
    """Get all installation logs for a device"""
    with Session() as session:
        logs = session.query(MCPInstallLogsORM).filter(
            MCPInstallLogsORM.device_id == device_id
        ).order_by(desc(MCPInstallLogsORM.installed_at)).all()
        for log in logs:
            session.expunge(log)
        return logs


@with_db_retry(max_retries=3, retry_delay=1.0)
def get_mcp_categories() -> List[str]:
    """Get distinct list of MCP categories"""
    with Session() as session:
        categories = session.query(MCPRegistryORM.category).filter(
            and_(
                MCPRegistryORM.category.isnot(None),
                MCPRegistryORM.is_active == True
            )
        ).distinct().all()
        return [cat[0] for cat in categories if cat[0]]