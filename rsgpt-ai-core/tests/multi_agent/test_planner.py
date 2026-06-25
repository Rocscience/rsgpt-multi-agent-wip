import json

from app.services.multi_agent.planner import (
    RunPlan,
    ServerFilePath,
    _parse_run_plan_loose,
    _reconcile_file_paths_from_goal,
)
from app.services.multi_agent.registry import ServerCatalog
from app.services.multi_agent.schema import ServerEntry, V2DemoConfig


def _catalog() -> ServerCatalog:
    cfg = V2DemoConfig(
        servers={
            "rs2-server": ServerEntry(
                file_extensions=[".fez"],
                default_file_path="C:\\default\\rs2.fez",
            ),
            "rspile-server": ServerEntry(
                file_extensions=[".rspile2"],
                default_file_path="C:\\default\\pile.rspile2",
            ),
        }
    )
    return ServerCatalog(cfg)


def test_parse_run_plan_coerces_stringified_file_paths():
    raw = {
        "selected_servers": ["rs2-server", "rspile-server"],
        "file_paths": json.dumps(
            [
                {"server_id": "rs2-server", "file_path": "C:\\models\\a.fez"},
                {"server_id": "rspile-server", "file_path": "C:\\models\\b.rspile2"},
            ]
        ),
        "task_hints": "[]",
        "reasoning": "compare models",
    }
    plan = _parse_run_plan_loose(raw)
    assert plan.selected_servers == ["rs2-server", "rspile-server"]
    assert plan.file_paths_map()["rs2-server"] == "C:\\models\\a.fez"
    assert plan.file_paths_map()["rspile-server"] == "C:\\models\\b.rspile2"


def test_parse_run_plan_repairs_corrupted_model_behavior_error():
    malformed = (
        'Invalid JSON when parsing {"selected_servers": ["rs2-server", "rspile-server"], '
        '"file_paths": "[\\n  {\\n    \\"server_id\\": \\"rs2-server\\",\\n    '
        '\\"file_path\\": \\"C:\\\\\\\\models\\\\\\\\a.fez\\"\\n  },\\n  {\\n    '
        '\\"server_id\\": \\"rspile-server\\",\\n    \\"file_path\\": \\"C:\\\\\\\\models\\\\\\\\b.rspile2\\"'
        'antml:function_calls>\\n**Note:** extra prose", '
        '"reasoning": "compare"} for TypeAdapter(RunPlan); validation error'
    )
    plan = _parse_run_plan_loose(malformed)
    assert plan.selected_servers == ["rs2-server", "rspile-server"]
    assert "a.fez" in plan.file_paths_map()["rs2-server"]
    assert "b.rspile2" in plan.file_paths_map()["rspile-server"]


def test_reconcile_file_paths_from_goal_by_extension():
    catalog = _catalog()
    plan = RunPlan(
        selected_servers=["rs2-server", "rspile-server"],
        file_paths=[
            ServerFilePath(
                server_id="rs2-server",
                file_path="C:\\wrong\\pile.rspile2",
            ),
            ServerFilePath(
                server_id="rspile-server",
                file_path="C:\\wrong\\embankment.fez",
            ),
        ],
    )
    goal = (
        "@[C:\\models\\embankment.fez] "
        "@[C:\\models\\pile.rspile2] compare parameters"
    )
    fixed = _reconcile_file_paths_from_goal(plan, user_goal=goal, catalog=catalog)
    assert fixed.file_paths_map()["rs2-server"] == "C:\\models\\embankment.fez"
    assert fixed.file_paths_map()["rspile-server"] == "C:\\models\\pile.rspile2"
