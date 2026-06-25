"""Serialize MCP CallTool results for LLM consumption."""

from __future__ import annotations

import json
import re
from typing import Any

_SETTER_TOOL_RE = re.compile(r"(^|_)set[A-Z]", re.I)
_VOID_SETTER_OK = (
    "(setter completed with no return value — re-read the matching getter to confirm the change)"
)


def is_setter_tool_name(tool_name: str) -> bool:
    return bool(_SETTER_TOOL_RE.search(tool_name or ""))


def format_tool_result(result: Any, *, tool_name: str = "") -> str:
    chunks: list[str] = []
    content = getattr(result, "content", None) or []
    for block in content:
        text = getattr(block, "text", None)
        if text is not None:
            chunks.append(text)
        else:
            chunks.append(str(block))
    structured = getattr(result, "structured_content", None) or getattr(
        result, "structuredContent", None
    )
    if structured is not None:
        chunks.append("\n--- structured ---\n" + json.dumps(structured, default=str, indent=2))
    if chunks:
        return "\n".join(chunks)
    if tool_name and is_setter_tool_name(tool_name):
        return _VOID_SETTER_OK
    return "(empty tool result)"


def tool_result_looks_failed(text: str, *, tool_name: str = "") -> bool:
    """Heuristic: MCP tool output indicates failure (for anti-hallucination checks)."""
    t = (text or "").strip()
    if not t or t == "(empty tool result)":
        if tool_name and is_setter_tool_name(tool_name):
            return False
        return True
    if t == _VOID_SETTER_OK:
        return False
    lower = t.lower()
    if t.startswith("Error calling ") or t.startswith("Invalid tool arguments"):
        return True
    if lower.startswith("open failed:"):
        return True
    fail_markers = (
        '"iserror": true',
        '"is_error": true',
        "iserror: true",
        "tool execution failed",
        "traceback (most recent call last)",
        "status: error",
        "result: error",
        "error computing rspile model",
        "error saving rspile model",
        "error saving model before reading state",
        "connection refused",
        "inactiverpcerror",
        "has no attribute 'value'",
        "failed to connect to all addresses",
        "input validation error",
    )
    if any(m in lower for m in fail_markers):
        return True
    if lower.startswith("error computing ") or lower.startswith("error saving "):
        return True
    if re.search(r"function\s+['\"][^'\"]+['\"]\s+not found", lower):
        return True
    if "not found on root object" in lower:
        return True
    if "no functions found on root object" in lower:
        return True
    if lower.count("error") >= 3 and len(t) < 800:
        return True
    return False
