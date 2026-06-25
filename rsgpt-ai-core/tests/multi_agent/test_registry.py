from app.services.multi_agent.registry import ServerCatalog
from app.services.multi_agent.schema import ServerEntry, V2DemoConfig


def test_catalog_and_validation():
    cfg = V2DemoConfig(
        servers={
            "a-server": ServerEntry(command="x", cwd=".", capabilities="test"),
            "b-server": ServerEntry(command="y", cwd="."),
        }
    )
    cat = ServerCatalog(cfg)
    assert len(cat.server_ids) == 2
    assert cat.agent_type_for("a-server") == "a_server"
    cat.validate_selection(["a-server"])
    try:
        cat.validate_selection([])
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for empty selection")
