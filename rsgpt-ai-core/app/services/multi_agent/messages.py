"""AutoGen RPC message types."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class PeerQuery:
    question: str
    from_server: str
    to_server: str
    request_id: str
    depth: int = 0


@dataclass
class PeerResponse:
    answer: str
    request_id: str
    from_server: str
    ok: bool = True


@dataclass
class ConsultantQuery:
    question: str
    from_server: str
    request_id: str
    software: str = ""


@dataclass
class ConsultantResponse:
    answer: str
    request_id: str
    ok: bool = True
    sources: list[str] = field(default_factory=list)


@dataclass
class RunWorkRequest:
    goal: str
    file_path: str
    server_id: str
    task_hint: str = ""
    validation_feedback: str = ""
    retry_attempt: int = 0


@dataclass
class WorkResult:
    server_id: str
    summary: str
    ok: bool = True
    error: str | None = None
    validation_ok: bool = True
    validation_issues: list[str] = field(default_factory=list)
    mcp_evidence: dict[str, Any] = field(default_factory=dict)
