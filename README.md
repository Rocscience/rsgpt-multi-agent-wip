# rsgpt-multi-agent-wip

Monorepo work-in-progress for RSInsight **multi-agent Agent mode** — all service source in one place.

| Directory | Role |
|-----------|------|
| `rsgpt-ai-core/` | Multi-agent orchestrator, planner, MCP specialists, `/api/v1/agent/stream` |
| `rsgpt-be/` | API gateway, auth, timeline coalescer for specialist handoffs |
| `rsgpt-fe/` | Agent mode UI, workflow trace, SSE event handling |
| `rsgpt-desktop/` | MCP gateway, WebSocket to ai-core, `mcp-servers.json` |

## Quick start

```powershell
git clone https://github.com/Rocscience/rsgpt-multi-agent-wip.git
cd rsgpt-multi-agent-wip
```

Follow **[docs/RUNNING.md](docs/RUNNING.md)** — install deps in each service directory, start Desktop → BE → ai-core → FE.

Architecture and file map: **[docs/MULTI_AGENT.md](docs/MULTI_AGENT.md)**.

## Layout

```
rsgpt-multi-agent-wip/
├── rsgpt-ai-core/     # Python / Poetry — port 8090
├── rsgpt-be/          # Python / Poetry — port 8080
├── rsgpt-fe/          # Next.js — port 3000
├── rsgpt-desktop/     # Electron — MCP gateway (dev webpack 5173)
└── docs/
    ├── RUNNING.md
    └── MULTI_AGENT.md
```

## Note on MCP server binaries

MCP `.exe` files under `rsgpt-desktop/python-servers/` are **not** in git (too large). Copy them from your Rocscience Desktop install or build pipeline before running Agent mode. Config is in `python-servers/mcp-servers.json`.

## Scripts

| Script | Purpose |
|--------|---------|
| `scripts/smoke-test.ps1` | HTTP health check on ports 8090, 8080, 3000, 5173 |
