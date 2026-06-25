# Running the Multi-Agent Stack Locally

End-to-end local development for RSInsight **Agent mode** with the multi-MCP orchestrator (RS2, RSPile, RS3, Settle3, Slide2, Dips).

This monorepo contains all four services at the top level — no separate clones or feature-branch setup required.

---

## Prerequisites

| Requirement | Notes |
|-------------|--------|
| **Windows 10/11** | Desktop + MCP servers run on Windows |
| **Python 3.11+** | ai-core, rsgpt-be |
| **Poetry** | Python dependency management |
| **Node.js 20+** | rsgpt-fe, rsgpt-desktop |
| **Rocscience apps** | RS2, RSPile, RS3, Settle3, Slide2 as needed |
| **API keys** | OpenAI, Anthropic; Pinecone optional (RAG) |
| **MCP server `.exe` files** | Not in git — copy into `rsgpt-desktop/python-servers/` (see below) |

---

## 1. Clone this repo

```powershell
git clone https://github.com/Rocscience/rsgpt-multi-agent-wip.git
cd rsgpt-multi-agent-wip
```

Layout:

```
rsgpt-multi-agent-wip/
├── rsgpt-ai-core/
├── rsgpt-be/
├── rsgpt-fe/
├── rsgpt-desktop/
└── docs/
```

---

## 2. MCP server binaries (Desktop)

Git excludes large `.exe` files. Copy MCP servers from your existing Desktop install or build output into:

```
rsgpt-desktop/python-servers/
├── rs2-server-v0.3.92.exe
├── rspile-server-v0.0.32.exe
├── rs3-server-v0.1.23.exe
├── settle3-server-v0.0.47.exe
├── slide2-server-v0.0.14.exe
└── mcp-servers.json          # already in repo — enable desired servers
```

Enable servers in `rsgpt-desktop/python-servers/mcp-servers.json`.

---

## 3. Configure environment

### rsgpt-ai-core

```powershell
cd rsgpt-ai-core
poetry install
poetry run pytest tests/multi_agent -q
```

| Variable | Purpose |
|----------|---------|
| `OPENAI_API_KEY` | Summarizer, RS3 inner agent via `/chat` |
| `ANTHROPIC_API_KEY` | Planner + specialists |
| `MULTI_AGENT_ENABLED` | `true` — routes Agent mode to multi-agent workflow |

### rsgpt-be

```powershell
cd rsgpt-be
poetry install
```

Postgres, Auth0, ai-core URL (`http://localhost:8090`), service token in `.env`.

### rsgpt-fe

```powershell
cd rsgpt-fe
npm install
```

`.env.local`: `NEXT_PUBLIC_API_URL=http://localhost:8080`

### rsgpt-desktop

```powershell
cd rsgpt-desktop
npm install
```

**Kill** production RSInsight Desktop before dev (single-instance lock). Gateway timeout fixes are in `src/main/mcp/mcpClient.ts` and `mcpServer.ts`.

---

## 4. Start services (order matters)

| # | Service | Directory | Command | URL |
|---|---------|-----------|---------|-----|
| 1 | Desktop (MCP) | `rsgpt-desktop` | `npm run dev` | `5173` |
| 2 | Backend | `rsgpt-be` | `poetry run start` | `http://localhost:8080` |
| 3 | AI Core | `rsgpt-ai-core` | `poetry run start` | `http://localhost:8090` |
| 4 | Frontend | `rsgpt-fe` | `npm run dev` | `http://localhost:3000` |

From repo root:

```powershell
.\scripts\smoke-test.ps1
```

---

## 5. Use Agent mode

1. Open **http://localhost:3000**
2. Sign in
3. RSInsight Desktop connected (WebSocket to ai-core)
4. **Agent** mode — attach files with `@[C:\path\to\model.fez]`
5. Example: *"Compare RSPile Tutorial 1 soils with RS2 embankment materials"*

---

## 6. Verify multi-agent config

```powershell
cd rsgpt-ai-core
poetry run python -c "from app.services.multi_agent.schema import load_default_config; from app.services.multi_agent.registry import ServerCatalog; c=load_default_config(); print(ServerCatalog(c).server_ids)"
```

Expected: `['dips-server', 'rs2-server', 'rs3-server', 'rspile-server', 'settle3-server', 'slide2-server']`

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `RSP_grep_tool failed: Tool failed` | Desktop MCP `list_tools` timeout — retry single-product prompt; restart Desktop |
| Workflow 5–10+ min | RS3 script agent + peer RPC — use RS2+RSPile for material reads |
| Desktop won't start dev | End production RSInsight Desktop process |
| No MCP tools | Copy `.exe` files into `python-servers/`; check `mcp-servers.json` |

See [MULTI_AGENT.md](./MULTI_AGENT.md) for architecture details.
