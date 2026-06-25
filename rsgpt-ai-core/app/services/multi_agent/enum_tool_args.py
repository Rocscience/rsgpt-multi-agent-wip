"""Normalize MCP enum setter arguments before call_tool, using enum maps embedded
in (activated) tool descriptions.

The logic here is product-agnostic: it reads ``Parameter 'x' (Enum): {0: 'NAME'}``
blocks out of any tool description and fuzzy-matches user text / getter output to a
member name or integer. It works with any frozen MCP server (originally needed for
the rspile-server exe) and contains no product-specific alias tables.
"""

from __future__ import annotations

import ast
import re
from typing import Any

_ENUM_PARAM_RE = re.compile(
    r"Parameter\s+'(\w+)'\s+\([^)]+\):\s*(\{[^}]+\})",
    re.I,
)
_ENUM_MEMBER_RE = re.compile(
    r"(?:[\.\<'\"]|^)([A-Za-z_]\w*)(?:\:\s*\d+)?(?:[\>'\"]|$)",
)


def parse_enum_mappings(description: str) -> dict[str, dict[str, int | str]]:
    """Parse ``Parameter 'x' (EnumClass): {0: 'NAME', ...}`` blocks from tool descriptions."""
    out: dict[str, dict[str, int | str]] = {}
    for param, mapping_text in _ENUM_PARAM_RE.findall(description or ""):
        try:
            raw = ast.literal_eval(mapping_text)
        except (SyntaxError, ValueError):
            continue
        if not isinstance(raw, dict):
            continue
        by_name: dict[str, int | str] = {}
        for key, name in raw.items():
            if isinstance(name, str):
                by_name[name] = key
                by_name[name.lower()] = key
        out[param.lower()] = by_name
    return out


def _member_entries(mapping: dict[str, int | str]) -> list[tuple[str, int | str]]:
    seen: set[str] = set()
    entries: list[tuple[str, int | str]] = []
    for name, key in mapping.items():
        if not isinstance(name, str) or name.isdigit():
            continue
        lower = name.lower()
        if lower in seen:
            continue
        seen.add(lower)
        entries.append((name, key))
    return entries


def resolve_enum_argument(value: str, mapping: dict[str, int | str]) -> int | str | None:
    """
    Map free text, UI labels, or getter output to an enum key/name using the tool description.

    Uses token overlap against member names in the mapping — no product-specific alias tables.
    """
    if not isinstance(value, str) or not mapping:
        return None

    stripped = value.strip()
    if stripped in mapping:
        return mapping[stripped]
    lower = stripped.lower()
    if lower in mapping:
        return mapping[lower]

    # Getter output often looks like ``<LateralType.SoftClay: 1>`` or ``SoftClay: 1``
    for match in _ENUM_MEMBER_RE.finditer(stripped):
        member = match.group(1)
        if member in mapping:
            return mapping[member]
        if member.lower() in mapping:
            return mapping[member.lower()]
        if member[0].isupper():
            return member

    tokens = [t for t in re.findall(r"[a-z]{2,}", lower)]
    best_key: int | str | None = None
    best_score = 0
    for name, key in _member_entries(mapping):
        name_lower = name.lower()
        score = 0
        if name_lower == lower:
            score = 100
        elif name_lower in lower or lower in name_lower:
            score = 60
        else:
            score = sum(12 for token in tokens if token in name_lower)
        if score > best_score:
            best_score = score
            best_key = key
    return best_key if best_score >= 12 else None


def normalize_enum_tool_arguments(
    tool_name: str,
    arguments: dict[str, Any],
    *,
    tool_description: str = "",
) -> dict[str, Any]:
    """
    Coerce string enum arguments to member names or integer values the MCP server accepts.

    Relies on enum mappings embedded in activated tool descriptions; falls back to fuzzy
    matching of user text against those member names. Product-agnostic.
    """
    if not arguments:
        return arguments

    mappings = parse_enum_mappings(tool_description)
    normalized = dict(arguments)
    for param, value in list(arguments.items()):
        if not isinstance(value, str):
            continue
        mapping = mappings.get(param.lower(), {})
        resolved = resolve_enum_argument(value, mapping)
        if resolved is not None:
            normalized[param] = resolved
    return normalized
