"""Resolve which model file each specialist opens for a workflow run."""

from __future__ import annotations

import re
from pathlib import Path, PureWindowsPath

from app.services.multi_agent.registry import ServerCatalog
from app.services.multi_agent.workflow_hints import goal_is_model_creation, path_is_absent


def normalize_extension(ext: str) -> str:
    e = (ext or "").strip().lower()
    if not e:
        return ""
    return e if e.startswith(".") else f".{e}"


def servers_for_extension(catalog: ServerCatalog, ext: str) -> list[str]:
    """Return server_id values whose registered extensions include ``ext``."""
    norm = normalize_extension(ext)
    if not norm:
        return []
    out: list[str] = []
    for sid in catalog.server_ids:
        allowed = [normalize_extension(x) for x in catalog.entry(sid).file_extensions]
        if norm in allowed:
            out.append(sid)
    return out


def all_accepted_extensions(catalog: ServerCatalog) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for sid in catalog.server_ids:
        for ext in catalog.entry(sid).file_extensions:
            norm = normalize_extension(ext)
            if norm and norm not in seen:
                seen.add(norm)
                out.append(norm)
    return sorted(out)


def _extensions_regex(catalog: ServerCatalog) -> str:
    parts = [re.escape(ext.lstrip(".")) for ext in all_accepted_extensions(catalog)]
    return "|".join(parts) if parts else "fez"


def extract_paths_from_text(text: str, catalog: ServerCatalog) -> list[str]:
    """
    Pull absolute model paths from free text (prompt, planner output).

    Supports Windows paths with spaces; de-duplicates while preserving first-seen order.
    """
    if not (text or "").strip():
        return []

    ext_group = _extensions_regex(catalog)
    patterns = [
        # C:\dir\file.fez  (backslashes, spaces ok)
        rf'([A-Za-z]:\\[^\r\n"]+?\.(?:{ext_group}))\b',
        # C:/dir/file.fez
        rf'([A-Za-z]:/[^\r\n"]+?\.(?:{ext_group}))\b',
        # Quoted paths
        rf'"([A-Za-z]:[\\/][^"]+?\.(?:{ext_group}))"',
        rf"'([A-Za-z]:[\\/][^']+?\.(?:{ext_group}))'",
    ]

    seen: set[str] = set()
    ordered: list[str] = []
    for pat in patterns:
        for match in re.finditer(pat, text, flags=re.IGNORECASE):
            raw = (match.group(1) or "").strip().rstrip(".,;)")
            if not raw:
                continue
            norm = normalize_path(raw)
            key = norm.casefold()
            if key not in seen:
                seen.add(key)
                ordered.append(norm)
    return ordered


def normalize_path(path: str) -> str:
    """Normalize to a consistent Windows-style string for MCP open tools."""
    p = (path or "").strip().strip('"').strip("'")
    if not p:
        return ""
    # PureWindowsPath keeps backslashes on Windows hosts.
    return str(PureWindowsPath(p))


def match_server_for_file(catalog: ServerCatalog, filename: str) -> str:
    """
    Pick the single server that owns ``filename`` by extension.

    Raises ValueError when no product or more than one product matches.
    """
    ext = Path(filename).suffix
    matches = servers_for_extension(catalog, ext)
    if not matches:
        known = all_accepted_extensions(catalog)
        raise ValueError(
            f"No registered product for extension {ext or '(none)'}. "
            f"Known extensions: {', '.join(known) or 'none'}"
        )
    if len(matches) > 1:
        raise ValueError(
            f"Extension {ext} matches multiple products ({', '.join(matches)}). "
            "Use a more specific filename or specify the product in your prompt."
        )
    return matches[0]


def route_paths_by_extension(
    catalog: ServerCatalog,
    *,
    selected: list[str],
    candidate_paths: list[str],
) -> tuple[dict[str, str], dict[str, list[str]], list[str]]:
    """
    Assign candidate paths to specialists by registered file extension.

    Returns ``(primary_paths, extra_paths, unrouted)`` where primary is the first
    path per server (goal order) and extras are additional paths for the same product.
    """
    primary: dict[str, str] = {}
    extras: dict[str, list[str]] = {sid: [] for sid in selected}
    unrouted: list[str] = []

    for raw in candidate_paths:
        path = normalize_path(raw)
        if not path:
            continue
        try:
            owner = match_server_for_file(catalog, path)
        except ValueError:
            unrouted.append(path)
            continue
        if owner not in selected:
            unrouted.append(path)
            continue
        if owner not in primary:
            primary[owner] = path
        else:
            extras[owner].append(path)

    extras = {sid: paths for sid, paths in extras.items() if paths}
    return primary, extras, unrouted


def _clean_path(value: str | None) -> str:
    return (value or "").strip()


def scratch_model_path_for(catalog: ServerCatalog, server_id: str) -> str:
    """Configured blank-model template path for from-scratch workflows (may not exist yet)."""
    return normalize_path(catalog.entry(server_id).scratch_model_path or "")


def resolve_specialist_paths(
    catalog: ServerCatalog,
    selected: list[str],
    planner_paths: dict[str, str],
    *,
    goal: str = "",
    uploaded_files: list[str] | None = None,
    user_model_file: str | None = None,
    path_overrides: dict[str, str] | None = None,
) -> tuple[dict[str, str], dict[str, object]]:
    """
    Build per-server open paths.

    Priority per specialist:
    1. CLI ``path_overrides`` (``server_id=path``)
    2. Path router — paths extracted from the user goal + uploaded files, matched by extension
    3. For from-scratch goals: ``scratch_model_path`` (blank template), not example defaults
    4. Planner-assigned paths from the goal
    5. ``default_file_path`` from config (last resort)

    When multiple paths map to the same product (e.g. two ``.fez`` for RS2), the first path
    in goal/upload order is auto-opened; the rest are listed in ``extra_paths`` metadata.
    """
    overrides = path_overrides or {}
    uploads = [normalize_path(p) for p in (uploaded_files or []) if _clean_path(p)]
    legacy = normalize_path(user_model_file) if _clean_path(user_model_file) else ""
    if legacy and legacy not in uploads:
        uploads.append(legacy)

    extracted = extract_paths_from_text(goal, catalog)
    candidates: list[str] = []
    seen: set[str] = set()
    for p in extracted + uploads:
        key = p.casefold()
        if p and key not in seen:
            seen.add(key)
            candidates.append(p)

    routed_primary, routed_extras, unrouted = route_paths_by_extension(
        catalog, selected=selected, candidate_paths=candidates
    )

    meta: dict[str, object] = {
        "extracted_paths": extracted,
        "uploaded_paths": uploads,
        "routed_primary": dict(routed_primary),
    }
    if routed_extras:
        meta["extra_paths"] = routed_extras
    if unrouted:
        meta["unrouted_paths"] = unrouted

    paths: dict[str, str] = {}
    for sid in selected:
        if sid in overrides and _clean_path(overrides[sid]):
            paths[sid] = normalize_path(overrides[sid])
            meta.setdefault("routing_source", {})[sid] = "cli_override"  # type: ignore[index]
            continue

        if sid in routed_primary:
            paths[sid] = routed_primary[sid]
            meta.setdefault("routing_source", {})[sid] = "path_router"  # type: ignore[index]
            continue

        if goal_is_model_creation(goal):
            scratch = scratch_model_path_for(catalog, sid)
            if scratch:
                paths[sid] = scratch
                meta.setdefault("routing_source", {})[sid] = "scratch_template"  # type: ignore[index]
            else:
                paths[sid] = "n/a"
                meta.setdefault("routing_source", {})[sid] = "scratch_not_configured"  # type: ignore[index]
            continue

        planner_path = normalize_path(planner_paths.get(sid, ""))
        if planner_path and not path_is_absent(planner_path):
            paths[sid] = planner_path
            meta.setdefault("routing_source", {})[sid] = "planner"  # type: ignore[index]
            continue

        default_path = normalize_path(catalog.entry(sid).default_file_path)
        paths[sid] = default_path or "n/a"
        meta.setdefault("routing_source", {})[sid] = "config_default"  # type: ignore[index]

    return paths, meta
