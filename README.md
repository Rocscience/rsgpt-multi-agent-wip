# rsgpt-multi-agent-wip

Work-in-progress **integration workspace** for RSInsight multi-agent Agent mode — orchestrating RS2, RSPile, RS3, Settle3, Slide2, and Dips MCP specialists via the user's Desktop.

This repo does **not** duplicate application source code. It pins, clones, and documents the Rocscience services that form the stack:

| Repo | Branch | Role |
|------|--------|------|
| [rsgpt-ai-core](https://github.com/Rocscience/rsgpt-ai-core) | `feat/multi-agent-production-integration` | Multi-agent orchestrator, planner, specialists |
| [rsgpt-be](https://github.com/Rocscience/rsgpt-be) | `feat/multi-agent-production-integration` | API gateway, timeline coalescer |
| [rsgpt-fe](https://github.com/Rocscience/rsgpt-fe) | `feat/multi-agent-production-integration` | Agent mode UI, workflow trace |
| [rsgpt-desktop](https://github.com/Rocscience/rsgpt-desktop) | `main` (+ local MCP fixes) | MCP gateway, WebSocket to ai-core |

## Quick start

```powershell
git clone https://github.com/Rocscience/rsgpt-multi-agent-wip.git
cd rsgpt-multi-agent-wip

# Link existing local clones (if integration branches not on GitHub yet)
.\scripts\clone-all.ps1 -UseLocal "c:\Users\YourName\rsgpt"

# Or clone fresh once branches are pushed
.\scripts\clone-all.ps1
```

Then follow **[docs/RUNNING.md](docs/RUNNING.md)** to start Desktop → BE → ai-core → FE.

## Documentation

| Doc | Contents |
|-----|----------|
| **[docs/RUNNING.md](docs/RUNNING.md)** | Prerequisites, env vars, start order, smoke tests, troubleshooting |
| **[docs/MULTI_AGENT.md](docs/MULTI_AGENT.md)** | Architecture, request flow, files added/changed, directory map |

## Integration status

- **ai-core** `495b1d3` — multi-agent port (+ local WIP cleanup: config-driven tool patterns/playbooks)
- **be** `98bfb93` — timeline coalescer
- **fe** `5aad934` — workflow trace UI (+ local uncommitted hook tweaks)
- **desktop** `96cd467` — MCP gateway timeout fixes (local, not pushed)

See `manifest.yaml` for pinned commits.

## Scripts

| Script | Purpose |
|--------|---------|
| `scripts/clone-all.ps1` | Clone or junction-link service repos into `repos/` |
| `scripts/smoke-test.ps1` | HTTP health check on ports 8090, 8080, 3000, 5173 |

## License

Same as constituent Rocscience repos — internal WIP.
