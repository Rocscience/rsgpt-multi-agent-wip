"""Compare specialist LLM summaries against recorded MCP tool evidence."""

from __future__ import annotations

import re
from typing import Any

from app.services.multi_agent.mcp_evidence import McpEvidenceStore
from app.services.multi_agent.messages import WorkResult
from app.services.multi_agent.schema import OrchestratorSettings
from app.services.multi_agent.workflow_hints import (
    goal_is_model_creation,
    goal_needs_before_after_comparison,
    path_is_absent,
)

_MISSING_FILE_PHRASES = (
    "file is missing",
    "file missing",
    "could not find the file",
    "cannot find the file",
    "model file not found",
    "no file path",
    "unable to open",
    "failed to open",
)

_MODEL_ACCESS_PHRASES = (
    "layer",
    "material",
    "soil",
    "mesh",
    "displacement",
    "settlement",
    "young's modulus",
    "youngs modulus",
    "modulus e",
    "unit weight",
    "cohesion",
    "friction angle",
    "cc=",
    "cv=",
    "es=",
)


def _summary_claims_model_facts(summary: str) -> bool:
    s = (summary or "").lower()
    if len(s) < 80:
        return False
    hits = sum(1 for p in _MODEL_ACCESS_PHRASES if p in s)
    return hits >= 2 or bool(re.search(r"\bE\s*[=:]\s*\d", summary, re.I))


def _summary_claims_missing_file(summary: str) -> bool:
    s = (summary or "").lower()
    return any(p in s for p in _MISSING_FILE_PHRASES)


_UPDATE_CLAIM_RE = re.compile(
    r"\b(updated|changed|set to|aligned|matches rs2|now\s+\d)",
    re.I,
)
_INCOMPLETE_TASK_RE = re.compile(
    r"\b(cannot proceed|unable to proceed|without rs2|not proceed with updating|"
    r"could not retrieve|would you like to proceed)\b",
    re.I,
)
_RHO_INFERENCE_RE = re.compile(
    r"rho\s*s|ρ\s*s|×\s*gravity|calculated unit weight|21\.5\s*kN",
    re.I,
)
_PILE_RESULTS_TOOL_RE = re.compile(r"get_pile_results", re.I)


_GAMMA_MISSING_RE = re.compile(
    r"not (directly )?(provided|specified|available)|placeholder|invalid placeholder|"
    r"additional steps",
    re.I,
)


def _summary_claims_parameter_update(summary: str) -> bool:
    return bool(_UPDATE_CLAIM_RE.search(summary or ""))


def _summary_claims_unit_weight_update(summary: str) -> bool:
    s = (summary or "").lower()
    if not _UPDATE_CLAIM_RE.search(summary or ""):
        return False
    return bool(
        re.search(r"unit weight|unit_weight|gamma|γ", s, re.I)
        and not re.search(r"young'?s modulus|modulus \(e\)|modulus e", s, re.I)
    ) or bool(
        re.search(r"unit weight.*(?:updated|set to|changed|aligned)", s, re.I)
    )


def _summary_signals_missing_gamma(summary: str) -> bool:
    if not re.search(r"unit weight|gamma|γ", summary or "", re.I):
        return False
    return bool(_GAMMA_MISSING_RE.search(summary or ""))


def _pile_results_record_has_data(record: Any) -> bool:
    if not record.ok:
        return False
    if not _PILE_RESULTS_TOOL_RE.search(record.tool_name):
        return False
    excerpt = (record.excerpt or "").lower()
    if "mounted successfully" in excerpt:
        return False
    if "input validation error" in excerpt or "not of type 'array'" in excerpt:
        return False
    return bool(
        "max" in excerpt or "min" in excerpt or '"pile 1"' in excerpt or "rsp_" in excerpt
    )


def _has_pile_results_data(tools: list) -> bool:
    return any(_pile_results_record_has_data(t) for t in tools)


def _pile_results_read_count(tools: list) -> int:
    return sum(1 for t in tools if _pile_results_record_has_data(t))


def _index_setunitweight(tools: list) -> int | None:
    for i, t in enumerate(tools):
        if (
            t.ok
            and re.search(r"setunitweight", t.tool_name, re.I)
            and "saturated" not in t.tool_name.lower()
        ):
            return i
    return None


def _index_first_pile_results_with_data(tools: list) -> int | None:
    for i, t in enumerate(tools):
        if _pile_results_record_has_data(t):
            return i
    return None


def _summary_claims_skipped_update(summary: str) -> bool:
    return bool(
        re.search(
            r"already aligned|no update (is )?needed|no update required|"
            r"does not need (to be )?updated|without updating",
            summary or "",
            re.I,
        )
    )


def _summary_claims_connectivity_failure(summary: str) -> bool:
    return bool(
        re.search(
            r"connectivity|connection (error|refused|issue)|grpc|activemq|"
            r"unable to update|tool interface",
            summary or "",
            re.I,
        )
    )


def _has_tool_named(tools: list, fragment: str) -> bool:
    frag = fragment.lower()
    return any(frag in t.tool_name.lower() for t in tools if t.ok)


_EMPTY_ACTIVE_PILES_RE = re.compile(
    r"""['"]active_piles['"]\s*:\s*\[\s*\]""",
    re.I,
)


def _rspile_state_shows_no_piles(tools: list) -> bool:
    """True when rspile_get_model_state reported zero piles in the model file."""
    for t in tools:
        if t.tool_name != "rspile_get_model_state":
            continue
        if _EMPTY_ACTIVE_PILES_RE.search(t.excerpt or ""):
            return True
    return False


def _tool_output_contains(tools: list, tool_name: str, phrase: str) -> bool:
    phrase_lower = phrase.lower()
    for t in tools:
        if t.tool_name != tool_name:
            continue
        if phrase_lower in (t.excerpt or "").lower():
            return True
    return False


def _tool_calls_with_failure_excerpt(tools: list, tool_name: str) -> bool:
    from app.services.multi_agent.mcp_results import tool_result_looks_failed

    for t in tools:
        if t.tool_name == tool_name and tool_result_looks_failed(
            t.excerpt or "", tool_name=tool_name
        ):
            return True
    return False


def _summary_signals_incomplete_task(summary: str) -> bool:
    return bool(_INCOMPLETE_TASK_RE.search(summary or ""))


def _getter_read_count(tools: list, getter_fragment: str, *, exclude_fragment: str = "") -> int:
    frag = getter_fragment.lower()
    excl = exclude_fragment.lower()
    return sum(
        1
        for t in tools
        if t.ok
        and frag in t.tool_name.lower()
        and "get" in t.tool_name.lower()
        and (not excl or excl not in t.tool_name.lower())
    )


def _open_status_failed(open_status: str) -> bool:
    s = (open_status or "").lower()
    return "open failed" in s or "fail" in s[:40]


def validate_specialist_output(
    *,
    server_id: str,
    summary: str,
    open_status: str,
    file_path: str,
    evidence: McpEvidenceStore,
    settings: OrchestratorSettings,
    goal: str = "",
) -> tuple[bool, list[str], dict[str, Any]]:
    """
    Return (validation_ok, issues, evidence_snapshot).
    validation_ok=False means the orchestrator should not trust the summary as grounded.
    """
    issues: list[str] = []
    snap = evidence.server_summary(server_id)
    open_rec = evidence.open_record(server_id)

    fp = (file_path or "").strip()
    has_path = bool(fp) and not path_is_absent(fp)
    creation_goal = goal_is_model_creation(goal, fp)

    if settings.require_successful_open and has_path:
        if open_rec and not open_rec.skipped and not open_rec.ok:
            issues.append(f"Model open failed ({open_rec.error or 'see open result'})")
        elif _open_status_failed(open_status):
            issues.append("Open status text indicates failure")

    if creation_goal and not has_path:
        if open_rec and open_rec.skipped and not open_rec.ok:
            issues.append(
                "No model open — create/save a blank model in the desktop app (File > New, "
                "Save As) or provide a .rspile2/.fez path, then retry"
            )
        elif _open_status_failed(open_status) and "no model is open" in (open_status or "").lower():
            issues.append(
                "Model creation requires an open desktop session — follow manual prep in open "
                "status or re-run with a saved new-model file path"
            )

    tools_total = snap["tool_calls_total"]
    tools_ok = snap["tool_calls_ok"]
    tools_failed = snap["tool_calls_failed"]

    if settings.require_mcp_tool_success and tools_ok == 0:
        if tools_total == 0:
            issues.append("No successful MCP tool calls recorded during work")
        elif tools_failed > 0:
            issues.append(
                f"All {tools_failed} MCP tool call(s) failed: {', '.join(snap['failed_tools'][:5])}"
            )

    if tools_total == 0 and _summary_claims_model_facts(summary):
        issues.append(
            "Summary cites model parameters but no MCP tools were recorded — possible hallucination"
        )

    if open_rec and open_rec.ok and _summary_claims_missing_file(summary):
        issues.append("Summary claims file missing/unopenable but MCP open succeeded")

    if tools_failed > 0 and tools_ok == 0 and len((summary or "").strip()) > 150:
        issues.append(
            "Every MCP tool failed yet the specialist produced a detailed summary — unverified"
        )

    failed_excerpts = snap.get("recent_excerpts") or []
    if any(
        "not found" in (e.get("excerpt") or "").lower()
        for e in failed_excerpts
        if isinstance(e, dict)
    ):
        issues.append(
            "MCP BigTool/activate calls returned 'function not found' — summary may be incomplete"
        )

    if not (summary or "").strip() and tools_ok == 0:
        issues.append("Empty specialist summary with no successful MCP evidence")

    tool_records = evidence.tool_records(server_id)
    failed_setters = [
        t for t in tool_records
        if not t.ok and re.search(r"(^|_)set[A-Z]", t.tool_name, re.I)
    ]
    if failed_setters and _summary_claims_parameter_update(summary):
        issues.append(
            "Summary claims a parameter update but setter tool(s) failed: "
            + ", ".join(t.tool_name for t in failed_setters[:3])
        )

    if server_id == "rspile-server":
        compute_count = sum(
            1 for t in tool_records if t.ok and t.tool_name == "rspile_compute"
        )
        pile_reads = _pile_results_read_count(tool_records)
        has_unit_weight_setter = any(
            t.ok
            and re.search(r"setunitweight", t.tool_name, re.I)
            and "saturated" not in t.tool_name.lower()
            for t in tool_records
        )
        needs_before_after = goal_needs_before_after_comparison(goal)
        cross_product_complete = pile_reads >= 2 and compute_count >= 2

        critical_failed = [
            t.tool_name
            for t in tool_records
            if not t.ok
            and re.search(r"setunitweight|getunitweight", t.tool_name, re.I)
            and "saturated" not in t.tool_name.lower()
        ]
        if critical_failed:
            issues.append(
                "Soil unit-weight MCP tools failed: "
                + ", ".join(critical_failed[:3])
                + " — parameter update is not verified"
            )
        if _summary_claims_connectivity_failure(summary) and critical_failed:
            issues.append(
                "Summary cites connectivity failure and critical tools failed — "
                "fix RSPile desktop/gRPC before claiming any update"
            )
        elif _summary_claims_connectivity_failure(summary) and _summary_claims_parameter_update(
            summary
        ):
            issues.append(
                "Summary claims parameter updates but also reports connectivity failure — "
                "unverified"
            )

        if creation_goal:
            if _tool_calls_with_failure_excerpt(tool_records, "rspile_compute"):
                issues.append(
                    "From-scratch goal: rspile_compute failed (connection or model error) — "
                    "model was not analyzed"
                )
            elif not _tool_output_contains(
                tool_records, "rspile_compute", "successfully computed"
            ):
                compute_attempted = any(
                    t.tool_name == "rspile_compute" for t in tool_records
                )
                if compute_attempted or _summary_claims_model_facts(summary):
                    issues.append(
                        "From-scratch goal requires successful rspile_compute before save"
                    )

            if _tool_calls_with_failure_excerpt(tool_records, "rspile_save_model"):
                issues.append(
                    "From-scratch goal: rspile_save_model failed — file was not saved"
                )
            elif not _tool_output_contains(
                tool_records, "rspile_save_model", "successfully saved"
            ):
                save_attempted = any(
                    t.tool_name == "rspile_save_model" for t in tool_records
                )
                if save_attempted or "save" in (goal or "").lower():
                    issues.append(
                        "From-scratch goal requires successful rspile_save_model"
                    )

            if pile_reads == 0 and compute_count >= 1:
                issues.append(
                    "From-scratch goal: compute ran but pile results were not read "
                    "(rspile_get_model_results → list_graphing_options → get_pile_results)"
                )

            if compute_count >= 1 and _rspile_state_shows_no_piles(tool_records):
                issues.append(
                    "From-scratch goal: rspile_compute ran but rspile_get_model_state "
                    "showed active_piles=[] — no pile was placed in the borehole. "
                    "RSPile GUI may show 'No files in the queue'. Configure pile section, "
                    "pile type/length, assign pile at borehole, apply lateral load, re-read "
                    "state until active_piles is non-empty, then compute."
                )

        if needs_before_after:
            if compute_count >= 1 and pile_reads == 0:
                issues.append(
                    "RSPile compute ran but no pile result numbers were read "
                    "(call rspile_get_model_results then RSPile_Results_get_pile_results; "
                    "use graphing_options from RSPile_Results_list_graphing_options as an array)"
                )

            if has_unit_weight_setter:
                if pile_reads < 2:
                    issues.append(
                        "setUnitWeight was called but pile results were not read twice "
                        "(before update and after recompute) via RSPile_Results_get_pile_results"
                    )
                setter_idx = _index_setunitweight(tool_records)
                first_pile_idx = _index_first_pile_results_with_data(tool_records)
                if (
                    setter_idx is not None
                    and first_pile_idx is not None
                    and first_pile_idx > setter_idx
                ):
                    issues.append(
                        "Pile results must be read BEFORE setUnitWeight, then after the second "
                        "rspile_compute — order: compute → get_pile_results → setUnitWeight → "
                        "compute → get_pile_results"
                    )
            elif not cross_product_complete and (
                _summary_claims_parameter_update(summary)
                or _summary_claims_unit_weight_update(summary)
            ):
                issues.append(
                    "Cross-product comparison requires two pile result reads (before and "
                    "after compute) and either setUnitWeight or an honest 'already aligned' "
                    "report with both reads in this attempt"
                )

            if (
                _summary_claims_skipped_update(summary)
                and not cross_product_complete
            ):
                issues.append(
                    "Cannot report 'already aligned' without two numeric pile result reads "
                    "from get_pile_results in this attempt"
                )

        if _summary_claims_parameter_update(summary):
            has_saturated_only_setter = any(
                re.search(r"setsaturatedunitweight", t.tool_name, re.I)
                for t in tool_records
                if t.ok
            )
            claims_uw_alignment = bool(
                re.search(
                    r"unit weight|gamma|γ",
                    summary or "",
                    re.I,
                )
                and _UPDATE_CLAIM_RE.search(summary or "")
            )
            if claims_uw_alignment and has_saturated_only_setter and not has_unit_weight_setter:
                issues.append(
                    "RS2 gamma maps to RSPile setUnitWeight — only setSaturatedUnitWeight was "
                    "called, so the layer unit weight (UI field) likely did not change"
                )
            if has_unit_weight_setter and _getter_read_count(
                tool_records, "unitweight", exclude_fragment="saturated"
            ) < 2:
                if needs_before_after or (
                    not creation_goal and _summary_claims_parameter_update(summary)
                ):
                    issues.append(
                        "Summary claims unit weight was updated but getUnitWeight was not "
                        "re-read after the setter — 'after' value is unverified"
                    )
        if needs_before_after and _summary_signals_incomplete_task(summary):
            has_setter = any(
                re.search(r"setunitweight|set[a-z]+", t.tool_name, re.I)
                for t in tool_records
                if t.ok
            )
            if not has_setter and not cross_product_complete and compute_count >= 1:
                issues.append(
                    "Task appears incomplete — analysis ran but no parameter update was "
                    "attempted despite missing peer data; retry with BigTool or ask peer again"
                )

    if server_id == "rs2-server":
        used_state = _has_tool_named(tool_records, "rs2_get_model_state")
        has_uw_getter = _has_tool_named(tool_records, "getunitweight")
        cites_rho_inference = bool(_RHO_INFERENCE_RE.search(summary or ""))
        gamma_missing = _summary_signals_missing_gamma(summary or "")

        if used_state and not has_uw_getter and (cites_rho_inference or gamma_missing):
            issues.append(
                "Unit weight/gamma missing from get_model_state but BigTool getUnitWeight "
                "was not invoked — use grep_tool on material name then activate InitialConditions getter"
            )

    validation_ok = len(issues) == 0
    return validation_ok, issues, snap


def apply_validation_to_result(
    result: WorkResult,
    *,
    open_status: str,
    file_path: str,
    evidence: McpEvidenceStore,
    settings: OrchestratorSettings,
    goal: str = "",
) -> WorkResult:
    """Attach validation fields; downgrade ok when validation fails and settings are strict."""
    v_ok, issues, snap = validate_specialist_output(
        server_id=result.server_id,
        summary=result.summary,
        open_status=open_status,
        file_path=file_path,
        evidence=evidence,
        settings=settings,
        goal=goal,
    )
    result.validation_ok = v_ok
    result.validation_issues = issues
    result.mcp_evidence = snap
    if not v_ok and settings.strict_validation:
        result.ok = False
        if not result.error:
            result.error = "; ".join(issues)
    return result
