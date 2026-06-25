"""Shared runtime context for a single workflow run."""

from __future__ import annotations

from dataclasses import dataclass, field

from autogen_core import AgentId
from app.services.multi_agent.mcp_protocol import McpSessionProtocol as ClientSession

from app.services.multi_agent.activity import ActivityLog
from app.services.multi_agent.mcp_evidence import McpEvidenceStore
from app.services.multi_agent.mcp_session_guard import McpSessionGuard
from app.services.multi_agent.mcp_tool_registry import McpToolRegistry
from app.services.multi_agent.peer_guard import PeerGuard
from app.services.multi_agent.registry import ServerCatalog
from app.services.multi_agent.model_paths import normalize_path
from app.services.multi_agent.schema import BootstrapCall, MultiAgentConfig
from app.services.multi_agent.workflow_timeline import WorkflowTimeline
from app.models.channels import SourceChannel, UserPermission


@dataclass
class OpenSession:
    file_path: str
    status_text: str
    ok: bool = True


@dataclass
class AppContext:
    cfg: MultiAgentConfig
    catalog: ServerCatalog
    activity: ActivityLog
    device_id: str = ""
    user_permission: UserPermission = UserPermission.BASIC
    source_channels: list[SourceChannel] = field(
        default_factory=lambda: [SourceChannel.ROC]
    )
    evidence: McpEvidenceStore = field(default_factory=McpEvidenceStore)
    timeline: WorkflowTimeline = field(default_factory=WorkflowTimeline)
    tool_registry: McpToolRegistry = field(default_factory=McpToolRegistry)
    open_status_by_server: dict[str, str] = field(default_factory=dict)
    open_sessions: dict[str, OpenSession] = field(default_factory=dict)
    peer_guard: PeerGuard = field(default_factory=PeerGuard)
    mcp_guard: McpSessionGuard = field(default_factory=McpSessionGuard)
    active_servers: list[str] = field(default_factory=list)
    agent_ids: dict[str, AgentId] = field(default_factory=dict)
    consultant_agent_id: AgentId | None = None
    sessions: dict[str, ClientSession] = field(default_factory=dict)

    def bootstrap_for(self, server_id: str) -> list[BootstrapCall]:
        raw = self.cfg.bootstrap_tool_calls.get(server_id, [])
        return [
            c if isinstance(c, BootstrapCall) else BootstrapCall.model_validate(c)
            for c in raw
        ]

    def agent_type_for(self, server_id: str) -> str:
        return self.catalog.agent_type_for(server_id)

    def peer_targets_for(self, server_id: str) -> list[str]:
        return [s for s in self.active_servers if s != server_id]

    def record_open_session(
        self,
        server_id: str,
        *,
        file_path: str,
        status_text: str,
        ok: bool,
    ) -> None:
        norm = normalize_path(file_path)
        if not norm:
            return
        self.open_sessions[server_id] = OpenSession(
            file_path=norm,
            status_text=status_text,
            ok=ok,
        )
        self.open_status_by_server[server_id] = status_text

    def open_session(self, server_id: str) -> OpenSession | None:
        return self.open_sessions.get(server_id)

    def open_is_ok(self, server_id: str, file_path: str) -> bool:
        sess = self.open_sessions.get(server_id)
        if not sess or not sess.ok:
            return False
        want = normalize_path(file_path)
        return bool(want) and sess.file_path.casefold() == want.casefold()

    def cached_open_status(self, server_id: str) -> str | None:
        sess = self.open_sessions.get(server_id)
        if sess and sess.ok:
            return sess.status_text
        return self.open_status_by_server.get(server_id)
