"""Cross-attempt MCP timeline for accurate final reporting after retries."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.services.multi_agent.mcp_evidence import ToolRecord
from app.services.multi_agent.messages import WorkResult

_FLOAT_DATA_RE = re.compile(r'"type"\s*:\s*"float"[^}]*"data"\s*:\s*"([0-9.eE+-]+)"', re.I)
_FLOAT_DATA_ALT_RE = re.compile(r'"data"\s*:\s*"([0-9.eE+-]+)"', re.I)
_PILE_RESULTS_TOOL_RE = re.compile(r"get_pile_results", re.I)
_SET_UNIT_WEIGHT_RE = re.compile(r"setunitweight", re.I)
_GET_UNIT_WEIGHT_RE = re.compile(r"getunitweight", re.I)
_MATERIAL_FROM_TOOL_RE = re.compile(r"(?:^RSP_|^RS2_)(.+?)_(?:get|set)", re.I)


def _material_hint(tool_name: str) -> str:
    m = _MATERIAL_FROM_TOOL_RE.search(tool_name or "")
    if m:
        return m.group(1).replace("_", " ")
    return ""


def _parse_float_excerpt(excerpt: str) -> str | None:
    text = excerpt or ""
    m = _FLOAT_DATA_RE.search(text) or _FLOAT_DATA_ALT_RE.search(text)
    if not m:
        return None
    try:
        return str(float(m.group(1)))
    except ValueError:
        return m.group(1)


def _is_saturated_tool(tool_name: str) -> bool:
    return "saturated" in (tool_name or "").lower()


def _pile_results_has_data(record: ToolRecord) -> bool:
    if not record.ok or not _PILE_RESULTS_TOOL_RE.search(record.tool_name):
        return False
    excerpt = (record.excerpt or "").lower()
    if "mounted successfully" in excerpt:
        return False
    if "input validation error" in excerpt or "not of type 'array'" in excerpt:
        return False
    return bool(
        "max" in excerpt or "min" in excerpt or '"pile 1"' in excerpt or "rsp_" in excerpt
    )


def _pile_highlights(excerpt: str) -> dict[str, str]:
    """Extract a few numeric peaks from pile result JSON without hardcoding product paths."""
    highlights: dict[str, str] = {}
    patterns = (
        ("max_displacement_x", r'"Displacement X"\s*:\s*([0-9.eE+-]+)'),
        ("max_beam_moment_xz", r'"Beam Moment X\'Z\'"\s*:\s*([0-9.eE+-]+)'),
        ("max_soil_reaction_x", r'"Soil Reaction Force X\'"\s*:\s*([0-9.eE+-]+)'),
    )
    for key, pat in patterns:
        m = re.search(pat, excerpt or "", re.I)
        if m:
            highlights[key] = m.group(1)
    return highlights


@dataclass
class AttemptSnapshot:
    attempt: int
    validation_ok: bool
    validation_issues: list[str]
    summary_excerpt: str
    tool_records: list[ToolRecord] = field(default_factory=list)


@dataclass
class WorkflowTimeline:
    """Accumulates per-attempt MCP history; survives evidence clears on retry."""

    _attempts: dict[str, list[AttemptSnapshot]] = field(default_factory=dict)

    def record_attempt(
        self,
        server_id: str,
        *,
        attempt: int,
        tool_records: list[ToolRecord],
        result: WorkResult,
    ) -> None:
        self._attempts.setdefault(server_id, []).append(
            AttemptSnapshot(
                attempt=attempt,
                validation_ok=result.validation_ok,
                validation_issues=list(result.validation_issues),
                summary_excerpt=(result.summary or "")[:600],
                tool_records=list(tool_records),
            )
        )

    def attempts_for(self, server_id: str) -> list[AttemptSnapshot]:
        return list(self._attempts.get(server_id, []))

    def consolidated(self, server_id: str) -> dict[str, Any]:
        snapshots = self.attempts_for(server_id)
        if not snapshots:
            return {"server_id": server_id, "attempts": [], "narrative_hints": []}

        merged: list[tuple[int, ToolRecord]] = []
        for snap in snapshots:
            for rec in snap.tool_records:
                merged.append((snap.attempt, rec))

        parameter_updates = _extract_parameter_updates(merged)
        pile_results = _extract_pile_results(merged, parameter_updates)
        narrative_hints = _build_narrative_hints(
            snapshots, parameter_updates, pile_results
        )

        return {
            "server_id": server_id,
            "attempts": [
                {
                    "attempt": s.attempt,
                    "validation_ok": s.validation_ok,
                    "validation_issues": s.validation_issues,
                    "tool_calls_recorded": len(s.tool_records),
                    "summary_excerpt": s.summary_excerpt,
                }
                for s in snapshots
            ],
            "parameter_updates": parameter_updates,
            "pile_results": pile_results,
            "narrative_hints": narrative_hints,
        }

    def all_consolidated(self, server_ids: list[str]) -> dict[str, dict[str, Any]]:
        return {sid: self.consolidated(sid) for sid in server_ids}


def _extract_parameter_updates(
    merged: list[tuple[int, ToolRecord]],
) -> list[dict[str, Any]]:
    """First getUnitWeight before any setUnitWeight defines baseline; read-back after set is updated."""
    by_material: dict[str, dict[str, Any]] = {}
    setter_seen: dict[str, bool] = {}

    for attempt, rec in merged:
        if not rec.ok:
            continue
        name = rec.tool_name
        material = _material_hint(name) or "material"
        if material not in by_material:
            by_material[material] = {"material": material}

        if _GET_UNIT_WEIGHT_RE.search(name) and not _is_saturated_tool(name):
            val = _parse_float_excerpt(rec.excerpt)
            if val is None:
                continue
            entry = by_material[material]
            if not setter_seen.get(material):
                entry.setdefault("baseline_value", val)
                entry.setdefault("baseline_attempt", attempt)
                entry.setdefault("baseline_tool", name)
            else:
                if "updated_value" not in entry:
                    entry["updated_value"] = val
                    entry["updated_attempt"] = attempt
                    entry["updated_tool"] = name
                entry["final_read_value"] = val
                entry["final_read_attempt"] = attempt

        if (
            _SET_UNIT_WEIGHT_RE.search(name)
            and not _is_saturated_tool(name)
        ):
            setter_seen[material] = True
            entry = by_material[material]
            if "setter_tool" not in entry:
                entry["setter_tool"] = name
                entry["setter_attempt"] = attempt
                entry["parameter"] = "unit_weight"

    out: list[dict[str, Any]] = []
    for entry in by_material.values():
        if "baseline_value" in entry or "setter_tool" in entry:
            out.append(entry)
    return out


def _extract_pile_results(
    merged: list[tuple[int, ToolRecord]],
    parameter_updates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    reads: list[dict[str, Any]] = []
    seq = 0
    first_setter_idx: int | None = None
    for i, (attempt, rec) in enumerate(merged):
        if rec.ok and _SET_UNIT_WEIGHT_RE.search(rec.tool_name) and not _is_saturated_tool(
            rec.tool_name
        ):
            if first_setter_idx is None:
                first_setter_idx = i
    for i, (attempt, rec) in enumerate(merged):
        if not _pile_results_has_data(rec):
            continue
        seq += 1
        role = "pile_read"
        if seq == 1:
            role = (
                "before_update"
                if first_setter_idx is None or i < first_setter_idx
                else "after_parameter_change"
            )
        elif seq == 2:
            role = "after_update"
        reads.append(
            {
                "sequence": seq,
                "attempt": attempt,
                "role": role,
                "tool": rec.tool_name,
                "highlights": _pile_highlights(rec.excerpt),
            }
        )
    if len(reads) == 1 and first_setter_idx is not None:
        reads[0]["role"] = "after_parameter_change"
    return reads


def _build_narrative_hints(
    snapshots: list[AttemptSnapshot],
    parameter_updates: list[dict[str, Any]],
    pile_results: list[dict[str, Any]],
) -> list[str]:
    hints: list[str] = []

    failed_with_data = [s for s in snapshots if not s.validation_ok and s.tool_records]
    passed = [s for s in snapshots if s.validation_ok]
    if failed_with_data and passed:
        hints.append(
            "This specialist required a retry. Use workflow_timeline.parameter_updates "
            "for baseline vs updated values — do not treat the final attempt's live "
            "getter read as the original baseline if an earlier attempt recorded a "
            "different value before setUnitWeight."
        )

    for pu in parameter_updates:
        baseline = pu.get("baseline_value")
        updated = pu.get("updated_value") or pu.get("final_read_value")
        material = pu.get("material", "material")
        if baseline and updated and baseline != updated:
            hints.append(
                f"{material} unit weight baseline was {baseline} kN/m³ (attempt "
                f"{pu.get('baseline_attempt')}) and was updated to {updated} kN/m³ "
                f"(setter in attempt {pu.get('setter_attempt')})."
            )
        elif baseline and updated and baseline == updated and pu.get("setter_tool"):
            hints.append(
                f"{material} unit weight read {baseline} kN/m³ before and after "
                f"setUnitWeight — report that no effective change occurred."
            )
        elif baseline and not pu.get("setter_tool"):
            hints.append(
                f"{material} unit weight baseline {baseline} kN/m³ was read but "
                "no successful setUnitWeight was recorded across attempts."
            )

    if pile_results:
        before = [p for p in pile_results if p.get("role") == "before_update"]
        after = [p for p in pile_results if p.get("role") in ("after_update", "after_parameter_change")]
        if not before and after:
            hints.append(
                "No pile result read occurred before the first setUnitWeight — "
                "before/after pile comparison reflects post-update state only; "
                "still report parameter baseline from timeline if available."
            )
        if len(pile_results) >= 2:
            hints.append(
                "Use workflow_timeline.pile_results sequence 1 and 2 for side-by-side "
                "pile metrics in the final table."
            )

    return hints


def timeline_retry_notes(consolidated: dict[str, Any] | None) -> list[str]:
    """Actionable retry guidance from prior attempts (no hardcoded values)."""
    if not consolidated:
        return []
    notes: list[str] = []
    for pu in consolidated.get("parameter_updates") or []:
        baseline = pu.get("baseline_value")
        updated = pu.get("updated_value") or pu.get("final_read_value")
        material = pu.get("material", "material")
        if baseline and updated and baseline != updated:
            notes.append(
                f"Prior attempt MCP evidence: {material} unit weight was {baseline} kN/m³ "
                f"before setUnitWeight and was updated to {updated} kN/m³ in attempt "
                f"{pu.get('setter_attempt')}. The open model may already read {updated} — "
                f"do NOT report {updated} as the original RSPile baseline. If getUnitWeight "
                f"already matches RS2, skip setUnitWeight but still complete TWO "
                f"get_pile_results reads (compute → pile → compute → pile)."
            )
    piles = consolidated.get("pile_results") or []
    if len(piles) < 2:
        notes.append(
            "Prior attempt(s) did not record two numeric get_pile_results reads — "
            "complete that sequence on this retry even if no parameter change is needed."
        )
    return notes


def format_verified_timeline_lead(all_timelines: dict[str, dict[str, Any]]) -> str:
    """Deterministic MCP-backed facts for the final report (prepended to summarizer output)."""
    sections: list[str] = []
    for sid, tl in all_timelines.items():
        if not tl.get("parameter_updates") and not tl.get("pile_results"):
            continue
        lines = [f"### {sid} (cross-attempt MCP timeline)", ""]
        for pu in tl.get("parameter_updates") or []:
            material = pu.get("material", "material")
            param = pu.get("parameter", "parameter")
            baseline = pu.get("baseline_value")
            updated = pu.get("updated_value") or pu.get("final_read_value")
            if baseline and updated and baseline != updated:
                lines.append(
                    f"- **{material} {param}:** original **{baseline} kN/m³** "
                    f"(attempt {pu.get('baseline_attempt')}) → updated to **{updated} kN/m³** "
                    f"(setter attempt {pu.get('setter_attempt')})"
                )
            elif baseline:
                lines.append(
                    f"- **{material} {param}:** read **{baseline} kN/m³** "
                    f"(attempt {pu.get('baseline_attempt')}); no successful setter recorded"
                )
        piles = tl.get("pile_results") or []
        for p in piles:
            role = p.get("role", "read")
            hi = p.get("highlights") or {}
            hi_str = ", ".join(f"{k}={v}" for k, v in hi.items()) if hi else "numeric data recorded"
            lines.append(
                f"- **Pile results ({role}, attempt {p.get('attempt')}, "
                f"read #{p.get('sequence')}):** {hi_str}"
            )
        for hint in tl.get("narrative_hints") or []:
            lines.append(f"- _Note:_ {hint}")
        sections.append("\n".join(lines))
    if not sections:
        return ""
    return "## Verified timeline (MCP evidence across all attempts)\n\n" + "\n\n".join(sections) + "\n\n"


def specialist_result_score(
    result: WorkResult,
    consolidated: dict[str, Any],
) -> int:
    """Higher = better specialist outcome for choosing which attempt to surface."""
    score = 0
    if result.validation_ok:
        score += 1000
    if result.ok:
        score += 100
    score -= len(result.validation_issues or []) * 15
    evidence = result.mcp_evidence or {}
    pile_tools = [
        t
        for t in (evidence.get("successful_tools") or [])
        if "get_pile_results" in str(t).lower()
    ]
    score += len(pile_tools) * 25
    if any(pu.get("setter_tool") for pu in consolidated.get("parameter_updates") or []):
        score += 40
    elif any(
        "setunitweight" in str(t).lower() and "saturated" not in str(t).lower()
        for t in (evidence.get("successful_tools") or [])
    ):
        score += 40
    return score
