"""Database models package"""

from .base import BaseDbModel
from .connection import engine, Session, get_db

# Import all models for alembic autogenerate to work
from .users import UsersORM, UserSettingsORM, RSLogUserSettingsORM
from .organizations import OrganizationsORM, UserOrganizationsORM
from .chats import ChatSessionsORM, UserMessagesORM, AIResponsesORM
from .feedback import MessageFeedbackORM
from .system import SystemConfigORM, ErrorLogsORM
from .devices import DevicesORM
from .mcp_registry import MCPRegistryORM, MCPVersionsORM
from .mcp_install_logs import MCPInstallLogsORM
from .quota_requests import QuotaRequestsORM, QuotaRequestStatus

# Use BaseDbModel as Base for compatibility
Base = BaseDbModel

__all__ = [
    "BaseDbModel",
    "Base",
    "engine", 
    "Session",
    "get_db",
    "UsersORM",
    "UserSettingsORM",
    "RSLogUserSettingsORM",
    "OrganizationsORM",
    "UserOrganizationsORM",
    "ChatSessionsORM",
    "UserMessagesORM",
    "AIResponsesORM",
    "MessageFeedbackORM",
    "SystemConfigORM",
    "ErrorLogsORM",
    "DevicesORM",
    "MCPRegistryORM",
    "MCPVersionsORM",
    "MCPInstallLogsORM",
    "QuotaRequestsORM",
    "QuotaRequestStatus",
]