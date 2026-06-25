"""Server catalog: discover MCP specialists from config (no per-server Python folders)."""

from __future__ import annotations

from app.services.multi_agent.schema import ServerEntry, V2DemoConfig


class ServerCatalog:
    """
    Registry of available MCP-backed specialists.

    To add a new Rocscience product agent:
      1. Add a block under ``servers:`` in configs/default.yaml (command, cwd, capabilities, open_tool).
      2. Add bootstrap_tool_calls for that server id.
      No new Python package folder is required unless you need custom agent behavior
      (subclass MCPSpecialistAgent in app.services.multi_agent/agents/).
    """

    def __init__(self, cfg: V2DemoConfig) -> None:
        self._cfg = cfg

    @property
    def server_ids(self) -> list[str]:
        return sorted(self._cfg.servers.keys())

    def entry(self, server_id: str) -> ServerEntry:
        if server_id not in self._cfg.servers:
            raise KeyError(f"Unknown server_id: {server_id}")
        return self._cfg.servers[server_id]

    def agent_type_for(self, server_id: str) -> str:
        if server_id in self._cfg.agent_types:
            return self._cfg.agent_types[server_id]
        ent = self.entry(server_id)
        if ent.agent_type:
            return ent.agent_type
        return server_id.replace("-", "_")

    def planner_context(self) -> list[dict]:
        """Compact catalog for the orchestrator LLM."""
        rows: list[dict] = []
        for sid in self.server_ids:
            e = self.entry(sid)
            rows.append(
                {
                    "server_id": sid,
                    "display_name": e.display_name or sid,
                    "capabilities": e.capabilities,
                    "integration_hints": e.integration_hints,
                    "peer_offers": e.peer_offers,
                    "peer_needs": e.peer_needs,
                    "file_extensions": e.file_extensions,
                    "open_tool": e.open_tool,
                    "default_file_path": e.default_file_path or "n/a",
                    "scratch_model_path": e.scratch_model_path or "n/a",
                }
            )
        return rows

    def cross_product_scenarios(self) -> list[dict]:
        return [s.model_dump() for s in self._cfg.cross_product_scenarios]

    def validate_selection(self, selected: list[str]) -> list[str]:
        unknown = [s for s in selected if s not in self._cfg.servers]
        if unknown:
            raise ValueError(f"Planner selected unknown server_id(s): {unknown}")
        if not selected:
            raise ValueError("Planner must select at least one server")
        return selected
