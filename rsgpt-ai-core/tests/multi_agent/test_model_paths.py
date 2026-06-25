from app.services.multi_agent.model_paths import (
    extract_paths_from_text,
    match_server_for_file,
    resolve_specialist_paths,
    route_paths_by_extension,
    servers_for_extension,
)
from app.services.multi_agent.registry import ServerCatalog
from app.services.multi_agent.schema import ServerEntry, V2DemoConfig

SSR = (
    r"C:\Users\Public\Documents\Rocscience\RS2 Examples\Tutorials"
    r"\Slope Stability\Shear Strength Reduction.fez"
)
PILED = (
    r"C:\Users\Public\Documents\Rocscience\RS2 Examples\Tutorials"
    r"\Support\Piled Raft Foundation.fez"
)
RSP = (
    r"C:\Users\Public\Documents\Rocscience\RSPile Examples\Tutorials"
    r"\Tutorial 2 - Lateral Pile Analysis.rspile2"
)


def _catalog() -> ServerCatalog:
    cfg = V2DemoConfig(
        servers={
            "rs2-server": ServerEntry(
                display_name="RS2",
                command="rs2.exe",
                cwd=".",
                file_extensions=[".fez"],
                default_file_path="C:\\default\\a.fez",
            ),
            "rspile-server": ServerEntry(
                display_name="RSPile",
                command="rspile.exe",
                cwd=".",
                file_extensions=[".rspile2"],
                default_file_path="C:\\default\\b.rspile2",
                scratch_model_path="C:\\templates\\rspile_scratch_empty.rspile2",
            ),
        }
    )
    return ServerCatalog(cfg)


def test_servers_for_extension():
    cat = _catalog()
    assert servers_for_extension(cat, ".fez") == ["rs2-server"]
    assert servers_for_extension(cat, "rspile2") == ["rspile-server"]


def test_extract_paths_from_cross_product_goal():
    cat = _catalog()
    goal = f"Use these models:\n1) RS2: {SSR}\n2) RS2 piled: {PILED}\n3) RSPile: {RSP}\n"
    extracted = extract_paths_from_text(goal, cat)
    assert extracted[0] == SSR
    assert PILED in extracted
    assert RSP in extracted


def test_path_router_picks_first_fez_for_rs2_and_rspile_file():
    cat = _catalog()
    goal = f"Models: {SSR} and {PILED} and {RSP}"
    paths, meta = resolve_specialist_paths(
        cat,
        selected=["rs2-server", "rspile-server"],
        planner_paths={
            "rs2-server": PILED,
            "rspile-server": "C:\\wrong\\default.rspile2",
        },
        goal=goal,
    )
    assert paths["rs2-server"] == SSR
    assert paths["rspile-server"] == RSP
    assert meta["routing_source"]["rs2-server"] == "path_router"
    assert PILED in meta["extra_paths"]["rs2-server"]


def test_uploaded_file_routes_without_goal_paths():
    cat = _catalog()
    upload = r"D:\uploads\rs2-server__abc__custom.fez"
    paths, meta = resolve_specialist_paths(
        cat,
        selected=["rs2-server"],
        planner_paths={"rs2-server": "n/a"},
        goal="Analyze my slope",
        uploaded_files=[upload],
    )
    assert paths["rs2-server"] == upload
    assert meta["routing_source"]["rs2-server"] == "path_router"


def test_planner_paths_when_no_goal_paths():
    cat = _catalog()
    paths, _ = resolve_specialist_paths(
        cat,
        selected=["rs2-server"],
        planner_paths={"rs2-server": r"C:\prompt\only.fez"},
        goal="No paths here",
    )
    assert paths["rs2-server"] == r"C:\prompt\only.fez"


def test_match_server_for_file():
    cat = _catalog()
    assert match_server_for_file(cat, "model.fez") == "rs2-server"


def test_from_scratch_goal_uses_scratch_template_not_planner_default():
    cat = _catalog()
    goal = (
        "Create a new RSPile lateral pile model from scratch (do not open an existing file). "
        "SI units, one pile, compute and save."
    )
    paths, meta = resolve_specialist_paths(
        cat,
        selected=["rspile-server"],
        planner_paths={
            "rspile-server": r"C:\Users\Public\Documents\Tutorial 1.rspile2",
        },
        goal=goal,
    )
    assert paths["rspile-server"] == r"C:\templates\rspile_scratch_empty.rspile2"
    assert meta["routing_source"]["rspile-server"] == "scratch_template"


def test_from_scratch_explicit_goal_path_wins_over_scratch():
    cat = _catalog()
    custom = r"D:\my_project\new_pile.rspile2"
    goal = f"Build from scratch using {custom}"
    paths, meta = resolve_specialist_paths(
        cat,
        selected=["rspile-server"],
        planner_paths={"rspile-server": "n/a"},
        goal=goal,
    )
    assert paths["rspile-server"] == custom
    assert meta["routing_source"]["rspile-server"] == "path_router"


def test_route_multiple_same_extension():
    cat = _catalog()
    primary, extras, unrouted = route_paths_by_extension(
        cat,
        selected=["rs2-server", "rspile-server"],
        candidate_paths=[SSR, PILED, RSP],
    )
    assert primary["rs2-server"] == SSR
    assert extras["rs2-server"] == [PILED]
    assert primary["rspile-server"] == RSP
    assert unrouted == []
