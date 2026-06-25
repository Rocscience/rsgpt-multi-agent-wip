"""Enrich RS2 file-parsed materials with live BigTool InitialConditions reads."""

from __future__ import annotations

import logging
import re
from typing import Any

from app.services.multi_agent.mcp_protocol import McpSessionProtocol as ClientSession

from app.services.multi_agent.mcp_results import format_tool_result, tool_result_looks_failed

logger = logging.getLogger(__name__)

_PLACEHOLDER_WEIGHT_THRESHOLD = 1e19

_INITIAL_CONDITION_GETTERS: tuple[tuple[str, str], ...] = (
    ("unit_weight", "getUnitWeight"),
    ("moist_unit_weight", "getMoistUnitWeight"),
    ("saturated_unit_weight", "getSaturatedUnitWeight"),
    ("dry_unit_weight", "getDryUnitWeight"),
    ("account_for_moisture", "getAccountForMoistureContentInUnitWeight"),
)


def _find_tool(names: list[str], *patterns: str) -> str | None:
    for pat in patterns:
        for n in names:
            if pat.lower() in n.lower():
                return n
    return None


def _scalar_from_result(text: str) -> Any:
    if tool_result_looks_failed(text):
        return None
    m = re.search(r'"type":\s*"float"[^}]*"data":\s*"([\d.]+)"', text)
    if m:
        return float(m.group(1))
    m = re.search(r'"type":\s*"bool"[^}]*"data":\s*"(true|false)"', text, re.I)
    if m:
        return m.group(1).lower() == "true"
    m = re.search(r'"type":\s*"float"[^}]*"data":\s*([\d.]+)', text)
    if m:
        return float(m.group(1))
    return None


def _resolve_invoke_tool(names: list[str], activated_name: str) -> str | None:
    if activated_name in names:
        return activated_name
    prefixed = f"RS2_{activated_name}"
    if prefixed in names:
        return prefixed
    candidates = [n for n in names if activated_name in n or n.endswith("getUnitWeight")]
    return candidates[0] if len(candidates) == 1 else None


async def _call(session: ClientSession, tool: str, arguments: dict | None = None) -> str:
    result = await session.call_tool(tool, arguments=arguments or {})
    return format_tool_result(result)


def _extract_data_dict(text: str) -> dict | None:
    import ast

    m = re.search(r'"data":\s*"(\{.*\})"', text, re.DOTALL)
    if not m:
        return None
    try:
        return ast.literal_eval(m.group(1).replace("\\n", "\n"))
    except Exception:
        return None


def parse_rs2_materials_from_state_text(state_text: str) -> list[dict[str, Any]]:
    data = _extract_data_dict(state_text)
    if not isinstance(data, dict):
        return []
    ms = data.get("model_state") or data
    materials = ms.get("materials") if isinstance(ms, dict) else None
    return materials if isinstance(materials, list) else []


def material_missing_unit_weight(mat: dict[str, Any]) -> bool:
    if mat.get("unit_weight_kN_m3") is not None:
        return False
    solid = mat.get("solid_properties") or {}
    for key in ("saturatedUnitWeight", "moistUnitWeight"):
        val = solid.get(key)
        if isinstance(val, (int, float)) and val >= _PLACEHOLDER_WEIGHT_THRESHOLD:
            return True
    return False


def format_unit_weight_prefetch_block(live_by_name: dict[str, dict[str, Any]]) -> str:
    if not live_by_name:
        return ""
    lines = [
        "PRE-READ LIVE UNIT WEIGHTS (MCP BigTool — use these instead of rhoS×g or placeholders):"
    ]
    for name, props in live_by_name.items():
        uw = props.get("unit_weight")
        if uw is not None:
            lines.append(f"- {name}: unit_weight = {uw} kN/m³ (InitialConditions.getUnitWeight)")
    if len(lines) == 1:
        return ""
    return "\n".join(lines) + "\n\n"


async def read_unit_weight_via_bigtool(
    session: ClientSession,
    material_name: str,
    *,
    model_root: str = "Model",
    evidence: Any | None = None,
    server_id: str = "rs2-server",
    phase: str = "prefetch",
) -> float | None:
    """Activate and invoke getUnitWeight only (minimal BigTool path)."""
    ic = await read_material_initial_conditions_via_bigtool(
        session,
        material_name,
        model_root=model_root,
        getters=(("unit_weight", "getUnitWeight"),),
        evidence=evidence,
        server_id=server_id,
        phase=phase,
    )
    if not ic:
        return None
    uw = ic.get("unit_weight")
    return float(uw) if isinstance(uw, (int, float)) else None


async def read_material_initial_conditions_via_bigtool(
    session: ClientSession,
    material_name: str,
    *,
    model_root: str = "Model",
    getters: tuple[tuple[str, str], ...] | None = None,
    evidence: Any | None = None,
    server_id: str = "rs2-server",
    phase: str = "",
) -> dict[str, Any] | None:
    """Activate and invoke InitialConditions getters for one RS2 material."""
    lr = await session.list_tools()
    names = [t.name for t in lr.tools]
    activate = _find_tool(names, "activate_function_by_name", "RS2_activate")
    if not activate:
        return None

    ic_root = [model_root, material_name, "InitialConditions"]
    props: dict[str, Any] = {"root_path": ic_root}
    use_getters = getters or _INITIAL_CONDITION_GETTERS

    for key, fn_name in use_getters:
        act_text = await _call(
            session,
            activate,
            {"function_name": fn_name, "root_object": ic_root},
        )
        if evidence is not None:
            evidence.record_tool(server_id, activate, act_text, phase=phase)
        if tool_result_looks_failed(act_text) or "Successfully activated" not in act_text:
            continue
        m = re.search(r"as tool '([^']+)'", act_text)
        if not m:
            continue
        lr2 = await session.list_tools()
        invoke = _resolve_invoke_tool([t.name for t in lr2.tools], m.group(1))
        if not invoke:
            continue
        invoke_text = await _call(session, invoke, {})
        if evidence is not None:
            evidence.record_tool(server_id, invoke, invoke_text, phase=phase)
        val = _scalar_from_result(invoke_text)
        if val is not None:
            props[key] = val

    return props if len(props) > 1 else None


async def prefetch_rs2_unit_weights_if_missing(
    session: ClientSession,
    *,
    evidence: Any | None = None,
    server_id: str = "rs2-server",
    phase: str = "prefetch",
) -> str:
    """
    Regular tool first (rs2_get_model_state), then BigTool getUnitWeight for materials
    whose file-parse still lacks unit weight. Returns prompt block for the specialist.
    """
    state_text = await _call(session, "rs2_get_model_state", {})
    if evidence is not None:
        evidence.record_tool(server_id, "rs2_get_model_state", state_text, phase=phase)

    materials = parse_rs2_materials_from_state_text(state_text)
    if not materials:
        return ""

    live: dict[str, dict[str, Any]] = {}
    for mat in materials:
        if not isinstance(mat, dict) or not material_missing_unit_weight(mat):
            continue
        name = mat.get("name")
        if not name:
            continue
        ic = await read_material_initial_conditions_via_bigtool(
            session,
            str(name),
            getters=(("unit_weight", "getUnitWeight"),),
            evidence=evidence,
            server_id=server_id,
            phase=phase,
        )
        if ic and ic.get("unit_weight") is not None:
            live[str(name)] = ic

    return format_unit_weight_prefetch_block(live)


def question_asks_unit_weight(question: str) -> bool:
    q = (question or "").lower()
    return bool(re.search(r"unit weight|unit_weight|gamma|γ|kn/m", q, re.I))


_question_asks_unit_weight = question_asks_unit_weight


def merge_live_initial_conditions(
    materials: list[dict[str, Any]],
    live_by_name: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Merge BigTool reads into material dicts (same shape as rs2_get_model_state enrichment)."""
    if not live_by_name:
        return {"enriched": False, "materials_matched": 0, "live_materials_found": []}

    live_by_lower = {k.lower(): v for k, v in live_by_name.items()}
    matched = 0
    for mat in materials:
        if not isinstance(mat, dict):
            continue
        name = mat.get("name")
        if not name:
            continue
        live = live_by_name.get(name) or live_by_lower.get(str(name).lower())
        if not live:
            continue
        matched += 1
        mat["initial_conditions"] = live
        unit_weight = live.get("unit_weight")
        if isinstance(unit_weight, (int, float)):
            mat["unit_weight_kN_m3"] = float(unit_weight)
            mat["unit_weight_source"] = "live_initial_conditions"
        solid = mat.get("solid_properties") or {}
        rho_s = solid.get("rhoS")
        if isinstance(rho_s, (int, float)):
            gravity = solid.get("Gravity") or 9.80665
            mat["gamma_rhoS_estimate_kN_m3"] = round(float(rho_s) * float(gravity), 2)

    return {
        "enriched": matched > 0,
        "materials_matched": matched,
        "live_materials_found": list(live_by_name.keys()),
        "source": "bigtool_client_enrichment",
    }


async def enrich_rs2_materials_via_bigtool(
    session: ClientSession,
    materials: list[dict[str, Any]],
) -> dict[str, Any]:
    """Read live InitialConditions for each named material and merge into the list."""
    live: dict[str, dict[str, Any]] = {}
    for mat in materials:
        name = mat.get("name") if isinstance(mat, dict) else None
        if not name:
            continue
        ic = await read_material_initial_conditions_via_bigtool(session, str(name))
        if ic:
            live[str(name)] = ic
    return merge_live_initial_conditions(materials, live)
