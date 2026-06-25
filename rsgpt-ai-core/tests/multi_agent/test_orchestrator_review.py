"""Tests for orchestrator retry decisions."""

from app.services.multi_agent.messages import WorkResult
from app.services.multi_agent.orchestrator_review import (
    build_retry_hint,
    review_workflow_results,
)
from app.services.multi_agent.schema import OrchestratorSettings


def test_retry_includes_strict_validation_failure():
    settings = OrchestratorSettings(retry_on_validation_failure=True, strict_validation=True)
    results = [
        WorkResult(
            server_id="rspile-server",
            summary="Updated unit weight.",
            ok=False,
            validation_ok=False,
            validation_issues=["Missing pile results"],
        )
    ]
    decision = review_workflow_results(results, settings=settings)
    assert "rspile-server" in decision.retry_servers


def test_no_retry_when_disabled():
    settings = OrchestratorSettings(retry_on_validation_failure=False)
    results = [
        WorkResult(
            server_id="rspile-server",
            summary="x",
            ok=False,
            validation_ok=False,
            validation_issues=["issue"],
        )
    ]
    decision = review_workflow_results(results, settings=settings)
    assert decision.retry_servers == []


def test_build_retry_hint_includes_diagnosis():
    hint = build_retry_hint(
        WorkResult(
            server_id="rspile-server",
            summary="Updated Soft Clay.",
            validation_issues=[
                "RSPile compute ran but no pile result numbers were read",
            ],
            mcp_evidence={"successful_tools": ["rspile_compute"], "failed_tools": []},
        ),
        goal="Update RSPile and compare before/after",
    )
    assert "ORCHESTRATOR RETRY" in hint
    assert "get_pile_results" in hint
    assert "before/after" in hint.lower() or "User goal" in hint


def test_build_retry_hint_from_scratch_uses_results_workflow_not_rs2():
    hint = build_retry_hint(
        WorkResult(
            server_id="rspile-server",
            summary="Model saved.",
            validation_issues=[
                "From-scratch goal: compute ran but pile results were not read",
            ],
            mcp_evidence={"successful_tools": ["rspile_compute"], "failed_tools": []},
        ),
        goal="create a new RSPile model from scratch and save",
    )
    assert "WORKFLOW HINT" in hint or "list_graphing" in hint or "get_pile_results" in hint
