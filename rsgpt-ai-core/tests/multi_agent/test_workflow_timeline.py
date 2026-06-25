"""Tests for cross-attempt workflow timeline consolidation."""

from app.services.multi_agent.mcp_evidence import McpEvidenceStore, ToolRecord
from app.services.multi_agent.messages import WorkResult
from app.services.multi_agent.workflow_timeline import (
    WorkflowTimeline,
    format_verified_timeline_lead,
    timeline_retry_notes,
)

_GET_15 = (
    '{\n  "type": "mcp_tool_result",\n  "is_error": false,\n  '
    '"content": [{"type": "float", "data": "15.0"}]\n}'
)
_GET_18 = (
    '{\n  "type": "mcp_tool_result",\n  "is_error": false,\n  '
    '"content": [{"type": "float", "data": "18.0"}]\n}'
)
_SETTER = "(setter completed with no return value — re-read the matching getter to confirm the change)"
_PILE = (
    '{"type":"mcp_tool_result","is_error":false,"content":[{"type":"dict","data":'
    '{"Pile 1":{"max":{"Displacement X":10.37,"Beam Moment X\'Z\'":157.56},'
    '"min":{"Displacement X":-0.22}}}}],'
)


def _result(server_id: str, *, ok: bool = True, validation_ok: bool = True) -> WorkResult:
    return WorkResult(
        server_id=server_id,
        summary="specialist summary",
        ok=ok,
        validation_ok=validation_ok,
        validation_issues=[] if validation_ok else ["issue"],
    )


def test_timeline_baseline_from_attempt_zero_after_retry_reads_eighteen():
    """Retry sees γ=18 live, but timeline keeps baseline 15 from attempt 0."""
    timeline = WorkflowTimeline()
    attempt0_tools = [
        ToolRecord("rspile_compute", True, "Successfully computed"),
        ToolRecord("RSP_Soft_Clay_getUnitWeight", True, _GET_15),
        ToolRecord("RSP_Soft_Clay_setUnitWeight", True, _SETTER),
        ToolRecord("RSP_Soft_Clay_getUnitWeight", True, _GET_18),
        ToolRecord("rspile_compute", True, "Successfully computed"),
        ToolRecord("rspile_get_model_results", True, "mounted successfully"),
    ]
    timeline.record_attempt(
        "rspile-server",
        attempt=0,
        tool_records=attempt0_tools,
        result=_result("rspile-server", validation_ok=False),
    )

    attempt1_tools = [
        ToolRecord("rspile_compute", True, "Successfully computed"),
        ToolRecord("RSPile_Results_get_pile_results", True, _PILE),
        ToolRecord("RSP_Soft_Clay_getUnitWeight", True, _GET_18),
        ToolRecord("rspile_compute", True, "Successfully computed"),
        ToolRecord("RSPile_Results_get_pile_results", True, _PILE),
    ]
    timeline.record_attempt(
        "rspile-server",
        attempt=1,
        tool_records=attempt1_tools,
        result=_result("rspile-server", validation_ok=True),
    )

    consolidated = timeline.consolidated("rspile-server")
    pu = consolidated["parameter_updates"][0]
    assert pu["baseline_value"] == "15.0"
    assert pu["updated_value"] == "18.0"
    assert pu["baseline_attempt"] == 0
    assert pu["setter_attempt"] == 0
    assert any("baseline was 15.0" in h for h in consolidated["narrative_hints"])
    assert any("retry" in h.lower() for h in consolidated["narrative_hints"])
    assert len(consolidated["pile_results"]) == 2


def test_timeline_records_via_evidence_store_pattern():
    evidence = McpEvidenceStore()
    evidence.record_tool("rspile-server", "RSP_Soft_Clay_getUnitWeight", _GET_15)
    evidence.record_tool("rspile-server", "RSP_Soft_Clay_setUnitWeight", _SETTER)
    evidence.record_tool("rspile-server", "RSP_Soft_Clay_getUnitWeight", _GET_18)

    timeline = WorkflowTimeline()
    timeline.record_attempt(
        "rspile-server",
        attempt=0,
        tool_records=evidence.tool_records("rspile-server"),
        result=_result("rspile-server"),
    )
    pu = timeline.consolidated("rspile-server")["parameter_updates"][0]
    assert pu["baseline_value"] == "15.0"
    assert pu["updated_value"] == "18.0"


def test_timeline_pile_before_update_when_read_before_setter():
    timeline = WorkflowTimeline()
    tools = [
        ToolRecord("rspile_compute", True, "ok"),
        ToolRecord("RSPile_Results_get_pile_results", True, _PILE),
        ToolRecord("RSP_Soft_Clay_getUnitWeight", True, _GET_15),
        ToolRecord("RSP_Soft_Clay_setUnitWeight", True, _SETTER),
        ToolRecord("RSP_Soft_Clay_getUnitWeight", True, _GET_18),
        ToolRecord("rspile_compute", True, "ok"),
        ToolRecord("RSPile_Results_get_pile_results", True, _PILE),
    ]
    timeline.record_attempt(
        "rspile-server",
        attempt=0,
        tool_records=tools,
        result=_result("rspile-server"),
    )
    piles = timeline.consolidated("rspile-server")["pile_results"]
    assert piles[0]["role"] == "before_update"
    assert piles[1]["role"] == "after_update"


def test_format_verified_timeline_lead_shows_baseline_from_attempt_zero():
    timeline = WorkflowTimeline()
    timeline.record_attempt(
        "rspile-server",
        attempt=0,
        tool_records=[
            ToolRecord("RSP_Soft_Clay_getUnitWeight", True, _GET_15),
            ToolRecord("RSP_Soft_Clay_setUnitWeight", True, _SETTER),
            ToolRecord("RSP_Soft_Clay_getUnitWeight", True, _GET_18),
        ],
        result=_result("rspile-server", validation_ok=False),
    )
    lead = format_verified_timeline_lead(timeline.all_consolidated(["rspile-server"]))
    assert "15.0" in lead
    assert "18.0" in lead
    assert "original" in lead.lower() or "→" in lead


def test_timeline_retry_notes_after_prior_update():
    timeline = WorkflowTimeline()
    timeline.record_attempt(
        "rspile-server",
        attempt=0,
        tool_records=[
            ToolRecord("RSP_Soft_Clay_getUnitWeight", True, _GET_15),
            ToolRecord("RSP_Soft_Clay_setUnitWeight", True, _SETTER),
            ToolRecord("RSP_Soft_Clay_getUnitWeight", True, _GET_18),
        ],
        result=_result("rspile-server", validation_ok=False),
    )
    notes = timeline_retry_notes(timeline.consolidated("rspile-server"))
    assert any("15.0" in n and "18.0" in n for n in notes)
    assert any("skip setUnitWeight" in n.lower() or "two" in n.lower() for n in notes)
