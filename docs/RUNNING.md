# Running the Multi-Agent Stack Locally

This guide covers end-to-end local development for RSInsight **Agent mode** with the multi-MCP orchestrator (RS2, RSPile, RS3, Settle3, Slide2, Dips).

The WIP repo ([rsgpt-multi-agent-wip](https://github.com/Rocscience/rsgpt-multi-agent-wip)) is a **workspace orchestrator**. Application code lives in the individual Rocscience repos under `repos/` (cloned or linked).

---

## Prerequisites

| Requirement | Notes |
|-------------|--------|
| **Windows 10/11** | Primary dev target (Desktop + MCP servers are Windows) |
| **Python 3.11+** | ai-core, rsgpt-be |
| **Poetry** | Dependency management for Python services |
| **Node.js 20+** | rsgpt-fe, rsgpt-desktop |
| **Rocscience apps** | RS2, RSPile, RS3, Settle3, Slide2 as needed for MCP servers |
| **API keys** | OpenAI, Anthropic (planner/specialists), Pinecone (optional RAG) |

---

## 1. Get the repos

From the root of this WIP repo:

```powershell
# Option A — clone integration branches from GitHub (once pushed)
.\scripts\clone-all.ps1

# Option B — link your existing local clones (recommended today)
.\scripts\clone-all.ps1 -UseLocal "c:\Users\KexuanZhang\rsgpt"
```

Expected layout:

```
rsgpt-multi-agent-wip/
├── repos/
│   ├── rsgpt-ai-core/    # branch: feat/multi-agent-production-integration
│   ├── rsgpt-be/         # branch: feat/multi-agent-production-integration
│   ├── rsgpt-fe/         # branch: feat/multi-agent-production-integration
│   └── rsgpt-desktop/    # branch: main (+ local MCP gateway fixes)
├── manifest.yaml
└── docs/
```

**Note:** Integration branches may not be on GitHub yet. Use `-UseLocal` with your working copies until they are pushed.

---

## 2. Configure environment

### rsgpt-ai-core (`repos/rsgpt-ai-core`)

Copy `.env.example` → `.env` (if present) or set:

| Variable | Purpose |
|----------|---------|
| `OPENAI_API_KEY` | LLM calls (summarizer, RS3 inner agent via `/chat`) |
| `ANTHROPIC_API_KEY` | Planner + specialist agents (default in config) |
| `MULTI_AGENT_ENABLED` | `true` (default) — routes Agent mode to multi-agent workflow |
| Service tokens | Match rsgpt-be dev token for `X-Service-Token` |

Install and verify:

```powershell
cd repos\rsgpt-ai-core
poetry install
poetry run pytest tests/multi_agent -q
```

### rsgpt-be (`repos/rsgpt-be`)

Standard BE `.env` — Postgres, Auth0, ai-core URL (`http://localhost:8090`), service token.

```powershell
cd repos\rsgpt-be
poetry install
```

### rsgpt-fe (`repos/rsgpt-fe`)

Point FE at local BE (usually via `.env.local`):

```
NEXT_PUBLIC_API_URL=http://localhost:8080
```

```powershell
cd repos\rsgpt-fe
npm install
```

### rsgpt-desktop (`repos/rsgpt-desktop`)

1. Enable MCP servers in `python-servers/mcp-servers.json` (RS2, RSPile, RS3, Settle3, Slide2).
2. Ensure MCP server `.exe` files exist under `python-servers/`.
3. **Kill** any running production **RSInsight Desktop** (single-instance lock).
4. Apply local gateway timeout fixes in `src/main/mcp/mcpClient.ts` / `mcpServer.ts` if not merged yet.

```powershell
cd repos\rsgpt-desktop
npm install
npm run dev
```

---

## 3. Start services (order matters)

Open **four terminals**:

| # | Service | Directory | Command | URL |
|---|---------|-----------|---------|-----|
| 1 | **Desktop** (MCP gateway) | `repos/rsgpt-desktop` | `npm run dev` | webpack `5173` |
| 2 | **Backend** | `repos/rsgpt-be` | `poetry run start` | `http://localhost:8080` |
| 3 | **AI Core** | `repos/rsgpt-ai-core` | `poetry run start` | `http://localhost:8090` |
| 4 | **Frontend** | `repos/rsgpt-fe` | `npm run dev` | `http://localhost:3000` |

Smoke test from WIP root:

```powershell
.\scripts\smoke-test.ps1
```

All four should return **200** (or OK for health endpoints).

---

## 4. Use Agent mode in the UI

1. Open **http://localhost:3000**
2. Sign in (Auth0 dev)
3. Ensure **RSInsight Desktop** is running and connected (WebSocket to ai-core)
4. Switch chat to **Agent** mode
5. Attach model files with `@[C:\path\to\model.fez]` syntax or pick from Desktop
6. Example prompts:
   - Single product: *"Open RSPile Tutorial 1 and list soil layer properties"*
   - Cross-product: *"Compare RS2 embankment materials with RSPile Tutorial 1 soils"*

The UI shows workflow trace events: planner → specialist transitions → tool execution → summarizer.

---

## 5. Verify multi-agent config loaded

```powershell
cd repos\rsgpt-ai-core
poetry run python -c "from app.services.multi_agent.schema import load_default_config; from app.services.multi_agent.registry import ServerCatalog; c=load_default_config(); print(ServerCatalog(c).server_ids)"
```

Expected: `['dips-server', 'rs2-server', 'rs3-server', 'rspile-server', 'settle3-server', 'slide2-server']`

---

## 6. Run tests

```powershell
# ai-core multi-agent suite
cd repos\rsgpt-ai-core
poetry run pytest tests/multi_agent tests/llm/providers/test_openai_client.py tests/api/test_chat.py -q

# ai-core only (quick)
poetry run pytest tests/multi_agent -q
```

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| Agent mode falls back to single-agent | Missing `device_id` or `MULTI_AGENT_ENABLED=false` | Connect Desktop; check ai-core config |
| `RSP_grep_tool failed: Tool failed` | Desktop MCP `list_tools` timeout (60s) under concurrent specialists | Retry single-product prompt; restart Desktop |
| Workflow runs 5–10+ minutes | RS3 script agent + cross-peer RPC + BigTool loops | Use RS2+RSPile instead of RS3 for material reads |
| Desktop won't start dev | Production Desktop still running | Task Manager → end RSInsight Desktop |
| Planner opens wrong file | `.fez` mapped to RS3 instead of RS2 | Mention file extensions explicitly in prompt |
| MCP gateway timeout on startup | Slide2 or slow server blocks sequential load | Use Desktop gateway background-load fix |

---

## Port reference

| Port | Service |
|------|---------|
| 3000 | rsgpt-fe |
| 8080 | rsgpt-be |
| 8090 | rsgpt-ai-core |
| 5173 | rsgpt-desktop dev webpack |
| 5432 | Postgres (BE) |

---

## Branch / commit pins

See `manifest.yaml` → `pins` for last known-good SHAs. Update after each verified integration run.
