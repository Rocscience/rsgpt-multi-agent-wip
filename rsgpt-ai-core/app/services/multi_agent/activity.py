"""Structured activity log for CLI and future chatbot UI."""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ActivityEvent:
    kind: str
    ts: float
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "ts": self.ts, **self.payload}


class ActivityLog:
    """Append-only event stream; subscribers can mirror to WebSocket/UI later."""

    def __init__(self) -> None:
        self.events: list[ActivityEvent] = []
        self._subscribers: list[Callable[[ActivityEvent], None]] = []

    def subscribe(self, callback: Callable[[ActivityEvent], None]) -> None:
        self._subscribers.append(callback)

    def emit(self, kind: str, **payload: Any) -> ActivityEvent:
        evt = ActivityEvent(kind=kind, ts=time.time(), payload=dict(payload))
        self.events.append(evt)
        for cb in self._subscribers:
            cb(evt)
        return evt

    def dump_json_lines(self) -> str:
        return "\n".join(json.dumps(e.to_dict(), default=str) for e in self.events)
