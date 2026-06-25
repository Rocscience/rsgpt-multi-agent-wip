"""Orchestrator planner: pick which MCP specialists to run for a user goal."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from agents import Agent, Runner
from agents.exceptions import ModelBehaviorError
from pydantic import BaseModel, Field, ValidationError

from app.services.multi_agent.model_resolver import agent_model
from app.services.multi_agent.registry import ServerCatalog
from app.services.multi_agent.schema import V2DemoConfig

logger = logging.getLogger(__name__)

# Any logical MCP server id is "<product>-server"; match generically so new
# products work without editing this module (the catalog is the source of truth).
_SERVER_ID_RE = re.compile(r'"([a-z0-9][a-z0-9_-]*-server)"')
_AT_PATH_RE = re.compile(r"@\[([^\]]+)\]")
_ROW_FIELDS: dict[str, tuple[str, ...]] = {
    "file_paths": ("server_id", "file_path"),
    "task_hints": ("server_id", "task_hint"),
}


class ServerFilePath(BaseModel):
    server_id: str = Field(description="Must match an entry in selected_servers")
    file_path: str = Field(description="Absolute path for that server, or n/a")


class ServerTaskHint(BaseModel):
    server_id: str = Field(description="Must match an entry in selected_servers")
    task_hint: str = Field(default="", description="Optional focus for that specialist")


class RunPlan(BaseModel):
    """Which specialists to spawn for this request (strict-schema-safe: no dict fields)."""

    selected_servers: list[str] = Field(
        description="server_id values from the catalog, e.g. rs2-server, rspile-server",
    )
    file_paths: list[ServerFilePath] = Field(
        default_factory=list,
        description="One row per selected server with its model file path",
    )
    task_hints: list[ServerTaskHint] = Field(
        default_factory=list,
        description="Optional per-server task focus rows",
    )
    reasoning: str = ""

    def file_paths_map(self) -> dict[str, str]:
        return {row.server_id: row.file_path for row in self.file_paths}

    def task_hints_map(self) -> dict[str, str]:
        return {row.server_id: row.task_hint for row in self.task_hints if row.task_hint}


def _planner_instructions() -> str:
    return """You are the orchestrator planner for a multi-MCP geotechnical desktop demo.

You do NOT call MCP tools. You only emit a RunPlan JSON object.

Rules:
- selected_servers: pick the MINIMUM set of server_id entries needed for the USER GOAL.
  For cross-product work, include every product that must contribute data (not just one).
- file_paths: array with one object per selected server ({server_id, file_path}). Use absolute paths from
  the user message when given; otherwise default_file_path from the catalog; "n/a" only if no file needed.
- For "from scratch" / "do not open existing file" goals: set file_path to "n/a" for that server — the
  workflow opens scratch_model_path from the catalog (blank template), NOT default_file_path examples.
- task_hints: REQUIRED for multi-server goals. One row per selected server with a focused sub-task and
  explicit peer instructions, e.g. "Extract material E, nu, gamma; ask rspile-server for pile layout;
  ask settle3-server for layer Cc/cv if names match."
- reasoning: one short paragraph explaining why these servers were chosen and how they integrate.
- CRITICAL OUTPUT FORMAT: emit ONLY one JSON object. Do NOT wrap file_paths or task_hints in quotes.
  No markdown, no prose, no notes outside the JSON. Arrays must be JSON arrays, not stringified JSON.
- Use ONLY server_id keys that appear in SERVER CATALOG.
- Choosing servers: read each catalog entry's capabilities, integration_hints, peer_offers and
  peer_needs to decide which products must collaborate. When peer_needs of one server is satisfied
  by peer_offers of another, include both and wire the dependency through their task_hints.
- Prefer CROSS_PRODUCT_SCENARIOS when the user goal matches a named scenario id, title, or servers
  list; reuse that scenario's server set and goal_template/notes as the basis for task_hints."""


def _extract_first_json_object(text: str) -> str | None:
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def _coerce_row_list(value: Any, *, field: str) -> list[dict[str, Any]]:
    keys = _ROW_FIELDS[field]
    if value is None:
        return []
    if isinstance(value, list):
        rows: list[dict[str, Any]] = []
        for item in value:
            if isinstance(item, dict):
                rows.append(item)
        return rows
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return []
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, list):
            return [row for row in parsed if isinstance(row, dict)]
        rows = []
        pattern = (
            rf'"{keys[0]}"\s*:\s*"([^"]+)"\s*,\s*'
            rf'"{keys[1]}"\s*:\s*"((?:[^"\\]|\\.)*)"'
        )
        for sid, payload in re.findall(pattern, stripped, flags=re.S):
            rows.append({keys[0]: sid, keys[1]: payload.replace("\\/", "/")})
        return rows
    return []


def _normalize_run_plan_payload(data: dict[str, Any]) -> dict[str, Any]:
    out = dict(data)
    if isinstance(out.get("selected_servers"), str):
        try:
            parsed = json.loads(out["selected_servers"])
            if isinstance(parsed, list):
                out["selected_servers"] = parsed
        except json.JSONDecodeError:
            out["selected_servers"] = _SERVER_ID_RE.findall(out["selected_servers"])
    out["file_paths"] = _coerce_row_list(out.get("file_paths"), field="file_paths")
    out["task_hints"] = _coerce_row_list(out.get("task_hints"), field="task_hints")
    if not isinstance(out.get("reasoning"), str):
        out["reasoning"] = str(out.get("reasoning") or "")
    return out


def _regex_extract_plan(raw: str) -> dict[str, Any]:
    servers: list[str] = []
    seen: set[str] = set()
    for block in re.findall(r'"selected_servers"\s*:\s*\[(.*?)\]', raw, flags=re.S):
        for sid in _SERVER_ID_RE.findall(block):
            if sid not in seen:
                servers.append(sid)
                seen.add(sid)
    if not servers:
        for sid in _SERVER_ID_RE.findall(raw):
            if sid not in seen:
                servers.append(sid)
                seen.add(sid)

    file_paths = _coerce_row_list(raw, field="file_paths")
    if not file_paths:
        for sid, fpath in re.findall(
            r'"server_id"\s*:\s*"([^"]+)"\s*,\s*'
            r'"file_path"\s*:\s*"((?:[^"\\]|\\.)*)"',
            raw,
            flags=re.S,
        ):
            file_paths.append(
                {
                    "server_id": sid,
                    "file_path": fpath.replace("\\\\", "\\").replace("\\/", "/"),
                }
            )

    task_hints = _coerce_row_list(raw, field="task_hints")
    if not task_hints:
        for sid, hint in re.findall(
            r'"server_id"\s*:\s*"([^"]+)"\s*,\s*'
            r'"task_hint"\s*:\s*"((?:[^"\\]|\\.)*)"',
            raw,
            flags=re.S,
        ):
            task_hints.append({"server_id": sid, "task_hint": hint})

    reasoning = ""
    m = re.search(r'"reasoning"\s*:\s*"((?:[^"\\]|\\.)*)"', raw, flags=re.S)
    if m:
        try:
            reasoning = json.loads(f'"{m.group(1)}"')
        except json.JSONDecodeError:
            reasoning = m.group(1)

    return {
        "selected_servers": servers,
        "file_paths": file_paths,
        "task_hints": task_hints,
        "reasoning": reasoning,
    }


def _parse_run_plan_loose(raw: str | dict[str, Any]) -> RunPlan:
    if isinstance(raw, dict):
        return RunPlan.model_validate(_normalize_run_plan_payload(raw))

    text = raw.strip()
    if not text:
        raise ValueError("empty planner output")

    candidates = [text]
    extracted = _extract_first_json_object(text)
    if extracted and extracted not in candidates:
        candidates.append(extracted)

    prefix = "Invalid JSON when parsing "
    if prefix in text:
        start = text.index(prefix) + len(prefix)
        end = text.find(" for TypeAdapter", start)
        if end > start:
            candidates.insert(0, text[start:end])

    last_error: Exception | None = None
    for candidate in candidates:
        try:
            data = json.loads(candidate)
        except json.JSONDecodeError as exc:
            last_error = exc
            data = _regex_extract_plan(candidate)
        if not isinstance(data, dict):
            last_error = ValueError("planner output is not a JSON object")
            continue
        try:
            return RunPlan.model_validate(_normalize_run_plan_payload(data))
        except ValidationError as exc:
            last_error = exc
            try:
                return RunPlan.model_validate(_normalize_run_plan_payload(_regex_extract_plan(candidate)))
            except ValidationError as exc2:
                last_error = exc2

    raise ValueError(f"could not parse RunPlan: {last_error}")


def _extract_at_file_paths(user_goal: str) -> list[str]:
    return [m.group(1).strip() for m in _AT_PATH_RE.finditer(user_goal)]


def _reconcile_file_paths_from_goal(
    plan: RunPlan, *, user_goal: str, catalog: ServerCatalog
) -> RunPlan:
    """Map @[path] mentions to specialists by file extension when the planner mis-assigns."""
    mentioned = _extract_at_file_paths(user_goal)
    if not mentioned:
        return plan

    ext_to_path: dict[str, str] = {}
    for path in mentioned:
        ext = Path(path).suffix.lower()
        if ext:
            ext_to_path[ext] = path

    if not ext_to_path:
        return plan

    path_map = plan.file_paths_map()
    reconciled: list[ServerFilePath] = []
    changed = False
    for sid in plan.selected_servers:
        ent = catalog.entry(sid)
        exts = {ext.lower() for ext in ent.file_extensions}
        matched = next((ext_to_path[ext] for ext in exts if ext in ext_to_path), None)
        current = path_map.get(sid, "n/a")
        if matched and matched != current:
            reconciled.append(ServerFilePath(server_id=sid, file_path=matched))
            changed = True
        elif matched:
            reconciled.append(ServerFilePath(server_id=sid, file_path=matched))
        elif current and current != "n/a":
            current_ext = Path(current).suffix.lower()
            if exts and current_ext and current_ext not in exts:
                reconciled.append(
                    ServerFilePath(server_id=sid, file_path=ent.default_file_path or "n/a")
                )
                changed = True
            else:
                reconciled.append(ServerFilePath(server_id=sid, file_path=current))
        else:
            reconciled.append(
                ServerFilePath(server_id=sid, file_path=ent.default_file_path or "n/a")
            )

    if changed:
        logger.info("Planner file_paths reconciled from user goal by extension")
        plan.file_paths = reconciled
    return plan


def _finalize_plan(plan: RunPlan, *, user_goal: str, catalog: ServerCatalog) -> RunPlan:
    plan = _reconcile_file_paths_from_goal(plan, user_goal=user_goal, catalog=catalog)
    catalog.validate_selection(plan.selected_servers)
    path_map = plan.file_paths_map()
    for sid in plan.selected_servers:
        if sid not in path_map:
            ent = catalog.entry(sid)
            plan.file_paths.append(
                ServerFilePath(server_id=sid, file_path=ent.default_file_path or "n/a")
            )
    logger.info("Planner selected: %s", plan.selected_servers)
    return plan


def _build_planner_input(*, user_goal: str, catalog: ServerCatalog) -> str:
    ctx: dict[str, Any] = {
        "server_catalog": catalog.planner_context(),
        "cross_product_scenarios": catalog.cross_product_scenarios(),
    }
    return (
        "USER GOAL:\n"
        f"{user_goal.strip()}\n\n"
        "SERVER CATALOG AND CROSS-PRODUCT SCENARIOS:\n"
        f"{json.dumps(ctx, indent=2)}"
    )


async def run_planner(
    *,
    user_goal: str,
    cfg: V2DemoConfig,
    catalog: ServerCatalog,
) -> RunPlan:
    planner_model = cfg.effective_planner_model
    agent = Agent(
        name="orchestrator-planner",
        instructions=_planner_instructions(),
        model=agent_model(planner_model),
        output_type=RunPlan,
    )
    user_input = _build_planner_input(user_goal=user_goal, catalog=catalog)
    logger.info("Planner running (model=%s)", planner_model)
    try:
        try:
            result = await Runner.run(agent, input=user_input, max_turns=12)
        except TypeError:
            result = await Runner.run(agent, input=user_input)
    except ModelBehaviorError as exc:
        err_text = str(getattr(exc, "message", exc))
        logger.warning("Planner strict parse failed; attempting repair: %s", err_text[:240])
        plan = _parse_run_plan_loose(err_text)
        return _finalize_plan(plan, user_goal=user_goal, catalog=catalog)

    final = getattr(result, "final_output", None)
    if isinstance(final, RunPlan):
        plan = final
    elif isinstance(final, dict):
        plan = _parse_run_plan_loose(final)
    elif isinstance(final, str) and final.strip():
        try:
            plan = RunPlan.model_validate_json(final)
        except ValidationError:
            logger.warning("Planner JSON validation failed; attempting repair")
            plan = _parse_run_plan_loose(final)
    else:
        raise RuntimeError(f"Planner returned unexpected output: {type(final)!r}")

    return _finalize_plan(plan, user_goal=user_goal, catalog=catalog)
