"""Tests for MCP evidence and specialist validation."""

from app.services.multi_agent.mcp_evidence import McpEvidenceStore
from app.services.multi_agent.mcp_results import tool_result_looks_failed
from app.services.multi_agent.messages import WorkResult
from app.services.multi_agent.schema import OrchestratorSettings
from app.services.multi_agent.validator import validate_specialist_output
from app.services.multi_agent.workflow_hints import goal_needs_before_after_comparison

_CROSS_PRODUCT_GOAL = (
    "Replace common parameters from RS2 and show a before and after comparison of the results."
)


def test_tool_result_looks_failed():
    assert tool_result_looks_failed("")
    assert tool_result_looks_failed("Error calling foo: timeout")
    assert not tool_result_looks_failed('{"layers": [{"name": "Clay"}]}')
    assert not tool_result_looks_failed(
        "(empty tool result)", tool_name="RSP_Soft_Clay_setUnitWeight"
    )
    assert tool_result_looks_failed("(empty tool result)", tool_name="rspile_compute")
    assert tool_result_looks_failed(
        '{"data": "Error computing RSPile model: Connection refused"}',
        tool_name="rspile_compute",
    )
    assert tool_result_looks_failed(
        "Error saving RSPile model: has no attribute 'value'",
        tool_name="rspile_save_model",
    )


def test_validate_no_tools_detailed_summary():
    evidence = McpEvidenceStore()
    settings = OrchestratorSettings()
    summary = (
        "Layer 1: Medium Clay with Es=10000 kPa and cv=0.01. "
        "Material embankment E=25000 kN/m2 and unit weight 18."
    )
    ok, issues, _ = validate_specialist_output(
        server_id="settle3-server",
        summary=summary,
        open_status="Model opened successfully",
        file_path="/tmp/model.s3",
        evidence=evidence,
        settings=settings,
    )
    assert not ok
    assert any("hallucination" in i.lower() or "no mcp" in i.lower() for i in issues)


def test_validate_missing_file_after_open():
    evidence = McpEvidenceStore()
    evidence.record_open("rs2-server", ok=True, tool_name="open_rs2_model")
    evidence.record_tool("rs2-server", "rs2_get_model_state", '{"materials": []}')
    settings = OrchestratorSettings()
    ok, issues, _ = validate_specialist_output(
        server_id="rs2-server",
        summary="The model file is missing and could not be opened.",
        open_status="ok",
        file_path="/tmp/a.fez",
        evidence=evidence,
        settings=settings,
    )
    assert not ok
    assert any("missing" in i.lower() for i in issues)


def test_validate_model_creation_without_open_session():
    evidence = McpEvidenceStore()
    evidence.record_open("rspile-server", ok=False, skipped=True)
    settings = OrchestratorSettings()
    goal = "Create RSPile pile model from scratch with Soft Clay Su=25 kPa"
    ok, issues, _ = validate_specialist_output(
        server_id="rspile-server",
        summary="Cannot configure — no model open.",
        open_status="No model is open and MCP cannot create one automatically.",
        file_path="n/a",
        evidence=evidence,
        settings=settings,
        goal=goal,
    )
    assert not ok
    assert any("no model open" in i.lower() for i in issues)


def test_apply_validation_strict():
    from app.services.multi_agent.validator import apply_validation_to_result

    evidence = McpEvidenceStore()
    result = WorkResult(
        server_id="x",
        summary=(
            "Layer 1: Medium Clay with Es=10000. Material embankment unit weight 18 kN/m3. "
            "Additional soil layer properties listed."
        ),
        ok=True,
    )
    out = apply_validation_to_result(
        result,
        open_status="ok",
        file_path="/p",
        evidence=evidence,
        settings=OrchestratorSettings(strict_validation=True),
    )
    assert not out.validation_ok
    assert not out.ok


def test_validate_rspile_incomplete_without_update():
    evidence = McpEvidenceStore()
    evidence.record_open("rspile-server", ok=True, tool_name="rspile_open_model")
    evidence.record_tool("rspile-server", "rspile_compute", "ok")
    evidence.record_tool("rspile-server", "RSPile_Results_get_pile_results", "max 10")
    settings = OrchestratorSettings()
    ok, issues, _ = validate_specialist_output(
        server_id="rspile-server",
        summary="We cannot proceed with updating without RS2 values. Would you like to proceed?",
        open_status="ok",
        file_path="/tmp/tutorial.rspile2",
        evidence=evidence,
        settings=settings,
        goal=_CROSS_PRODUCT_GOAL,
    )
    assert not ok
    assert any("incomplete" in i.lower() for i in issues)


def test_validate_rs2_rho_inference_without_bigtool():
    evidence = McpEvidenceStore()
    evidence.record_open("rs2-server", ok=True, tool_name="open_rs2_model")
    evidence.record_tool("rs2-server", "rs2_get_model_state", '{"materials": []}')
    settings = OrchestratorSettings()
    ok, issues, _ = validate_specialist_output(
        server_id="rs2-server",
        summary="Clay unit weight ≈ rhoS × Gravity ≈ 21.5 kN/m³ from get_model_state.",
        open_status="ok",
        file_path="/tmp/a.fez",
        evidence=evidence,
        settings=settings,
    )
    assert not ok
    assert any("rho" in i.lower() or "getunitweight" in i.lower() for i in issues)


def test_validate_rs2_missing_gamma_without_bigtool():
    evidence = McpEvidenceStore()
    evidence.record_open("rs2-server", ok=True, tool_name="open_rs2_model")
    evidence.record_tool("rs2-server", "rs2_get_model_state", '{"materials": []}')
    settings = OrchestratorSettings()
    ok, issues, _ = validate_specialist_output(
        server_id="rs2-server",
        summary=(
            "Clay layer: E=5000 kPa, nu=0.35. "
            "Unit Weight (gamma): Not specified (placeholders)."
        ),
        open_status="ok",
        file_path="/tmp/a.fez",
        evidence=evidence,
        settings=settings,
    )
    assert not ok
    assert any("getunitweight" in i.lower() or "bigtool" in i.lower() for i in issues)


def test_validate_rspile_saturated_instead_of_unit_weight():
    evidence = McpEvidenceStore()
    evidence.record_open("rspile-server", ok=True, tool_name="rspile_open_model")
    evidence.record_tool("rspile-server", "rspile_compute", "Successfully computed")
    evidence.record_tool(
        "rspile-server",
        "RSPile_Results_get_pile_results",
        '{"Pile 1": {"max": {"Displacement X": 10.6}}}',
    )
    evidence.record_tool("rspile-server", "RSP_Soft_Clay_getUnitWeight", "15.0")
    evidence.record_tool(
        "rspile-server",
        "RSP_Soft_Clay_setSaturatedUnitWeight",
        "(setter completed with no return value — re-read the matching getter to confirm the change)",
    )
    evidence.record_tool("rspile-server", "RSP_Soft_Clay_getSaturatedUnitWeight", "18.0")
    evidence.record_tool("rspile-server", "rspile_compute", "Successfully computed")
    evidence.record_tool(
        "rspile-server",
        "RSPile_Results_get_pile_results",
        '{"Pile 1": {"max": {"Displacement X": 10.6}}}',
    )
    settings = OrchestratorSettings()
    ok, issues, _ = validate_specialist_output(
        server_id="rspile-server",
        summary=(
            "Updated RSPile Saturated Unit Weight for Soft Clay to match RS2 unit weight (18.0 kN/m³)."
        ),
        open_status="ok",
        file_path="/tmp/tutorial.rspile2",
        evidence=evidence,
        settings=settings,
    )
    assert not ok
    assert any("setunitweight" in i.lower() or "ui field" in i.lower() for i in issues)


def test_validate_rspile_e_update_no_unit_weight_false_positive():
    evidence = McpEvidenceStore()
    evidence.record_open("rspile-server", ok=True, tool_name="rspile_open_model")
    evidence.record_tool("rspile-server", "rspile_compute", "Successfully computed")
    evidence.record_tool(
        "rspile-server",
        "RSPile_Results_get_pile_results",
        '{"Pile 1": {"max": {"Displacement X": 10.6}}}',
    )
    evidence.record_tool(
        "rspile-server",
        "RSP_Pile_Section_1_PileAnalysis_Elastic_setYoungsModulus",
        "(setter completed with no return value — re-read the matching getter to confirm the change)",
    )
    evidence.record_tool(
        "rspile-server",
        "RSP_Pile_Section_1_PileAnalysis_Elastic_getYoungsModulus",
        "5000.0",
    )
    evidence.record_tool("rspile-server", "rspile_compute", "Successfully computed")
    evidence.record_tool(
        "rspile-server",
        "RSPile_Results_get_pile_results",
        '{"Pile 1": {"max": {"Displacement X": 10.6}}}',
    )
    settings = OrchestratorSettings()
    ok, issues, _ = validate_specialist_output(
        server_id="rspile-server",
        summary=(
            "Young's Modulus Updated to: 5,000 kPa (from RS2 Clay Layer). "
            "If other parameters such as Unit Weight were available, further updates could have been done."
        ),
        open_status="ok",
        file_path="/tmp/tutorial.rspile2",
        evidence=evidence,
        settings=settings,
    )
    assert ok, issues
    assert not any("getunitweight" in i.lower() for i in issues)


def test_validate_rspile_setter_without_before_pile_results():
    evidence = McpEvidenceStore()
    evidence.record_open("rspile-server", ok=True, tool_name="rspile_open_model")
    evidence.record_tool("rspile-server", "rspile_compute", "ok")
    evidence.record_tool("rspile-server", "RSP_Soft_Clay_getUnitWeight", "15.0")
    evidence.record_tool(
        "rspile-server",
        "RSP_Soft_Clay_setUnitWeight",
        "(setter completed with no return value — re-read the matching getter to confirm the change)",
    )
    evidence.record_tool("rspile-server", "RSP_Soft_Clay_getUnitWeight", "18.0")
    evidence.record_tool("rspile-server", "rspile_compute", "ok")
    evidence.record_tool(
        "rspile-server",
        "RSPile_Results_get_pile_results",
        '{"Pile 1": {"max": {"Displacement X": 10.6}}}',
    )
    settings = OrchestratorSettings()
    ok, issues, _ = validate_specialist_output(
        server_id="rspile-server",
        summary="Updated unit weight from 15 to 18 kN/m³ and recomputed.",
        open_status="ok",
        file_path="/tmp/tutorial.rspile2",
        evidence=evidence,
        settings=settings,
        goal=_CROSS_PRODUCT_GOAL,
    )
    assert not ok
    assert any("twice" in i.lower() or "before" in i.lower() for i in issues)


def test_validate_rspile_already_aligned_without_two_pile_reads():
    evidence = McpEvidenceStore()
    evidence.record_open("rspile-server", ok=True, tool_name="rspile_open_model")
    evidence.record_tool("rspile-server", "rspile_compute", "ok")
    evidence.record_tool("rspile-server", "RSP_Soft_Clay_setUnitWeight", "(setter ok)")
    evidence.record_tool("rspile-server", "rspile_compute", "ok")
    evidence.record_tool(
        "rspile-server",
        "RSPile_Results_get_pile_results",
        '{"Pile 1": {"max": {"Beam Moment X\'Z\'": 157.56}}}',
    )
    settings = OrchestratorSettings()
    ok, issues, _ = validate_specialist_output(
        server_id="rspile-server",
        summary="Unit weights are already aligned; no update is needed.",
        open_status="ok",
        file_path="/tmp/tutorial.rspile2",
        evidence=evidence,
        settings=settings,
        goal=_CROSS_PRODUCT_GOAL,
    )
    assert not ok
    assert any("already aligned" in i.lower() or "twice" in i.lower() for i in issues)


def test_validate_rspile_critical_tool_failure():
    evidence = McpEvidenceStore()
    evidence.record_open("rspile-server", ok=True, tool_name="rspile_open_model")
    evidence.record_tool("rspile-server", "rspile_compute", "ok")
    evidence.record_tool(
        "rspile-server",
        "RSP_Soft_Clay_setUnitWeight",
        "Error calling tool: Connection refused",
    )
    settings = OrchestratorSettings()
    ok, issues, _ = validate_specialist_output(
        server_id="rspile-server",
        summary="Connectivity issue prevented updating parameters.",
        open_status="ok",
        file_path="/tmp/tutorial.rspile2",
        evidence=evidence,
        settings=settings,
    )
    assert not ok
    assert any("failed" in i.lower() for i in issues)


def test_validate_rspile_update_without_readback():
    evidence = McpEvidenceStore()
    evidence.record_open("rspile-server", ok=True, tool_name="rspile_open_model")
    evidence.record_tool("rspile-server", "RSP_Soft_Clay_getUnitWeight", "15.0")
    evidence.record_tool(
        "rspile-server",
        "RSP_Soft_Clay_setUnitWeight",
        "(setter completed with no return value — re-read the matching getter to confirm the change)",
    )
    evidence.record_tool("rspile-server", "rspile_compute", "Successfully computed")
    settings = OrchestratorSettings()
    ok, issues, _ = validate_specialist_output(
        server_id="rspile-server",
        summary="Unit weight was updated to 21.52 kN/m³ and the model was recomputed.",
        open_status="ok",
        file_path="/tmp/tutorial.rspile2",
        evidence=evidence,
        settings=settings,
        goal=_CROSS_PRODUCT_GOAL,
    )
    assert not ok
    assert any("re-read" in i.lower() or "getunitweight" in i.lower() for i in issues)
    assert any("pile result" in i.lower() for i in issues)


def test_goal_needs_before_after_comparison():
    assert goal_needs_before_after_comparison("Show before and after pile results")
    assert not goal_needs_before_after_comparison("List soil layers only")


def test_evidence_clear_server_resets_tool_history():
    evidence = McpEvidenceStore()
    evidence.record_tool("rspile-server", "rspile_compute", "ok")
    assert len(evidence.tool_records("rspile-server")) == 1
    evidence.clear_server("rspile-server")
    assert evidence.tool_records("rspile-server") == []


def test_validate_rspile_retry_already_aligned_two_pile_reads_passes():
    """Retry attempt: no setter, two pile reads + two computes — ordering must not fail."""
    evidence = McpEvidenceStore()
    evidence.record_open("rspile-server", ok=True, tool_name="rspile_open_model")
    evidence.record_tool("rspile-server", "rspile_compute", "ok")
    evidence.record_tool(
        "rspile-server",
        "RSPile_Results_get_pile_results",
        '{"Pile 1": {"max": {"Displacement X": 10.0}}}',
    )
    evidence.record_tool("rspile-server", "RSP_Soft_Clay_getUnitWeight", "18.0")
    evidence.record_tool("rspile-server", "rspile_compute", "ok")
    evidence.record_tool(
        "rspile-server",
        "RSPile_Results_get_pile_results",
        '{"Pile 1": {"max": {"Displacement X": 10.0}}}',
    )
    settings = OrchestratorSettings()
    ok, issues, _ = validate_specialist_output(
        server_id="rspile-server",
        summary=(
            "Soft Clay unit weight already matches RS2 (18.0 kN/m³). "
            "Before and after pile results are unchanged."
        ),
        open_status="ok",
        file_path="/tmp/tutorial.rspile2",
        evidence=evidence,
        settings=settings,
        goal=_CROSS_PRODUCT_GOAL,
    )
    assert ok, issues


def test_validate_rspile_modulus_only_goal_no_before_after_rules():
    evidence = McpEvidenceStore()
    evidence.record_open("rspile-server", ok=True, tool_name="rspile_open_model")
    evidence.record_tool("rspile-server", "rspile_compute", "ok")
    evidence.record_tool(
        "rspile-server",
        "RSPile_Results_get_pile_results",
        '{"Pile 1": {"max": {"Displacement X": 10.6}}}',
    )
    settings = OrchestratorSettings()
    ok, issues, _ = validate_specialist_output(
        server_id="rspile-server",
        summary="We cannot proceed with updating without RS2 values.",
        open_status="ok",
        file_path="/tmp/tutorial.rspile2",
        evidence=evidence,
        settings=settings,
        goal="Update Young's modulus from RS2 only.",
    )
    assert ok, issues


_CREATION_GOAL = (
    "create a new RSPile lateral pile model from scratch, compute, read pile results, save"
)


def test_validate_from_scratch_requires_compute_save_and_results():
    evidence = McpEvidenceStore()
    evidence.record_open("rspile-server", ok=True, tool_name="rspile_open_model")
    evidence.record_tool("rspile-server", "rspile_compute", "Error computing RSPile model: refused")
    evidence.record_tool("rspile-server", "rspile_save_model", "Error saving RSPile model: refused")
    settings = OrchestratorSettings()
    ok, issues, _ = validate_specialist_output(
        server_id="rspile-server",
        summary="Model configured and saved successfully with pile head displacement 12 mm.",
        open_status="ok",
        file_path="/tmp/scratch.rspile2",
        evidence=evidence,
        settings=settings,
        goal=_CREATION_GOAL,
    )
    assert not ok
    assert any("compute failed" in i.lower() for i in issues)
    assert any("save_model failed" in i.lower() for i in issues)


def test_validate_from_scratch_fails_when_compute_with_empty_piles():
    evidence = McpEvidenceStore()
    evidence.record_open("rspile-server", ok=True, tool_name="rspile_open_model")
    evidence.record_tool(
        "rspile-server",
        "rspile_get_model_state",
        "{'status': 'ok', 'pile_state': {'active_piles': [], 'active_pile_types': []}}",
    )
    evidence.record_tool("rspile-server", "rspile_compute", "Successfully computed RSPile model")
    evidence.record_tool(
        "rspile-server",
        "rspile_save_model",
        "Successfully saved RSPile model: C:\\out\\new_model.rspile2",
    )
    settings = OrchestratorSettings()
    ok, issues, _ = validate_specialist_output(
        server_id="rspile-server",
        summary="Soil layers configured. Compute and save completed.",
        open_status="ok",
        file_path="/tmp/scratch.rspile2",
        evidence=evidence,
        settings=settings,
        goal=_CREATION_GOAL,
    )
    assert not ok
    assert any("active_piles=[]" in i for i in issues)
    assert any("no files in the queue" in i.lower() for i in issues)


def test_validate_from_scratch_ok_when_compute_save_and_results_present():
    evidence = McpEvidenceStore()
    evidence.record_open("rspile-server", ok=True, tool_name="rspile_open_model")
    evidence.record_tool("rspile-server", "rspile_compute", "Successfully computed RSPile model")
    evidence.record_tool(
        "rspile-server",
        "RSPile_Results_get_pile_results",
        '{"Pile 1": {"max": {"Displacement X": 10.6}}}',
    )
    evidence.record_tool(
        "rspile-server",
        "rspile_save_model",
        "Successfully saved RSPile model: C:\\out\\new_model.rspile2",
    )
    settings = OrchestratorSettings()
    ok, issues, _ = validate_specialist_output(
        server_id="rspile-server",
        summary="Compute OK. Saved to new_model.rspile2. Max displacement X 10.6 mm from get_pile_results.",
        open_status="ok",
        file_path="/tmp/scratch.rspile2",
        evidence=evidence,
        settings=settings,
        goal=_CREATION_GOAL,
    )
    assert ok, issues
