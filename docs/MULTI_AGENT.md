# Multi-Agent System — Architecture & Implementation

How RSInsight **Agent mode** orchestrates multiple Rocscience MCP specialists. All implementation lives in this monorepo under `rsgpt-ai-core/`, with supporting changes in `rsgpt-be/`, `rsgpt-fe/`, and `rsgpt-desktop/`.

---

## High-level picture

```
User (FE :3000)
    │  Agent mode + device_id
    ▼
rsgpt-be (:8080)  ──proxy──▶  rsgpt-ai-core (:8090)
                                    │
                    ┌───────────────┴───────────────┐
                    │  should_use_multi_agent()?    │
                    └───────────────┬───────────────┘
                          yes     │      no
                    ┌─────────────▼─────────┐   ┌──────────────────┐
                    │ MultiAgentOrchestr. │   │ Single-agent     │
                    │ (AutoGen + MCP)     │   │ orchestration    │
                    └─────────────┬───────┘   └──────────────────┘
                                  │
              Planner (LLM) picks specialists from YAML catalog
                                  │
         ┌────────────────────────┼────────────────────────┐
         ▼                        ▼                        ▼
   rs2-server              rspile-server              rs3-server  …
         │                        │                        │
         └──────────── WebSocket MCP gateway ──────────────┘
                                  │
                         rsgpt-desktop (device)
                         RS2 / RSPile / RS3 / … apps
```

**Key idea:** One user goal → **planner** selects minimum MCP specialists → specialists run **in parallel** on the user's Desktop → they **ask each other** via peer RPC → **validator** checks MCP evidence → **summarizer** produces the final answer. All progress streams to FE as SSE events.

---

## Request flow (step by step)

1. **FE** sends `POST /agent/stream` to **BE** with `mode=AGENT` and `device_id`.
2. **BE** forwards to **ai-core** `POST /api/v1/agent/stream`.
3. **ai-core** `should_use_multi_agent()` returns true when `device_id` is set and `MULTI_AGENT_ENABLED=true`.
4. **Planner** (`planner.py`) reads `multi_agent_servers.yaml` catalog + cross-product scenarios, emits a `RunPlan`: which servers, file paths, task hints.
5. **Workflow** (`workflow.py`) connects each specialist to Desktop via `DeviceMcpPool` → WebSocket `list_tools` / `call_tool`.
6. Each **MCPSpecialistAgent** (`agents/specialist.py`):
   - Bootstraps MCP (`enable_rs2_server`, etc.)
   - Opens model file (`open_model.py`, `model_readiness.py`)
   - Runs LLM tool loop (`specialist_llm.py`) with filtered MCP tools
   - Can call `ask_agent_peer` and `ask_software_consultant`
7. **Validator** (`validator.py`) checks tool evidence vs summary claims.
8. **Summarizer** (`summarizer.py`) LLM merges specialist reports + timeline into user-facing markdown.
9. **SSE bridge** (`sse_bridge.py`) maps internal activity → FE event types (`agent.transition`, `agent.tool_execution.*`, etc.).
10. **BE timeline coalescer** persists specialist handoffs in chat history for FE replay.

---

## What existed before (original ai-core)

The original repo (`rsgpt-ai-core` on `main` / `qa`) had:

| Component | Role |
|-----------|------|
| `app/services/agent/` | Single **Orchestrator** agent (OpenAI Agents SDK) with sub-agents as tools |
| `app/api/routes/agent.py` | `POST /stream` → `orchestration_service.stream_workflow()` |
| `app/services/streaming/` | WebSocket to Desktop, RAG, chat streaming |
| No `multi_agent/` package | Device tools invoked directly by one orchestrator LLM |

Agent mode without multi-agent: one LLM decides which **tool** to call on the device gateway.

---

## What was added (integration)

Integration commit **`495b1d3`** on `feat/multi-agent-production-integration` ports **demo v2** multi-MCP orchestration into production Agent mode.

### New package: `app/services/multi_agent/` (~35 files, ~6500 lines)

| File / directory | Purpose |
|------------------|---------|
| **`schema.py`** | Pydantic models for YAML config (`ServerEntry`, `MultiAgentConfig`, `tool_patterns`, `agent_playbook`) |
| **`registry.py`** | `ServerCatalog` — exposes catalog to planner, validates server selection |
| **`planner.py`** | LLM planner → `RunPlan` (servers, paths, task hints); JSON repair fallbacks |
| **`workflow.py`** | Main orchestration: connect pool → parallel specialists → validate → retry → summarize |
| **`orchestration_service.py`** | Production entry: SSE stream, activity queue, wires to `agent.py` |
| **`agents/specialist.py`** | AutoGen `MCPSpecialistAgent` — open model, main work, peer answers |
| **`agents/consultant.py`** | RAG-backed software consultant (workflow HOW-TO, not live model values) |
| **`device_mcp_pool.py`** | One WebSocket MCP session per logical `server_id` |
| **`device_mcp_adapter.py`** | Implements MCP protocol over Desktop WebSocket (`list_tools`, `call_tool`) |
| **`tool_filter.py`** | Routes gateway tools to specialists via config `tool_patterns` |
| **`bootstrap.py`** | Runs per-server enable/bootstrap tool calls from YAML |
| **`open_model.py`** | Calls `open_rs2_model`, `rspile_open_model`, `enable_rs3_server`, etc. |
| **`model_readiness.py`** | Probe open session, scratch template, manual-prep messages |
| **`model_paths.py`** | Path normalization, `@[path]` extraction, scratch path resolution |
| **`specialist_llm.py`** | Runs OpenAI Agents SDK loop for one specialist with MCP FunctionTools |
| **`mcp_function_tools.py`** | Wraps MCP tools as Agent SDK tools; RSPile compute guard, enum arg prep |
| **`mcp_tool_registry.py`** | Live tool catalog snapshots + playbook guidance for prompts |
| **`mcp_evidence.py`** | Records every tool call for validation |
| **`mcp_session_guard.py`** | Per-server asyncio lock (peer + main work don't corrupt MCP stream) |
| **`peer_tools.py`** / **`peer_guard.py`** | `ask_agent_peer` RPC between specialists with depth/timeout limits |
| **`consultant_tools.py`** | `ask_software_consultant` wrapper |
| **`validator.py`** | Post-run checks (tool success, before/after, RS2 gamma, RSPile compute) |
| **`orchestrator_review.py`** | Retry hints when validation fails |
| **`workflow_timeline.py`** | Cross-attempt MCP timeline for accurate summarizer input |
| **`summarizer.py`** | Final LLM synthesis |
| **`sse_bridge.py`** | Activity → production SSE events |
| **`activity.py`** | In-memory event log for one workflow run |
| **`messages.py`** | AutoGen message types (`RunWorkRequest`, `WorkResult`, `PeerQuery`) |
| **`workflow_hints.py`** | Goal-derived hints (from-scratch, before/after) |
| **`rs2_live_enrichment.py`** | RS2-specific BigTool unit-weight prefetch |
| **`enum_tool_args.py`** | Generic enum setter normalization from tool descriptions |
| **`model_resolver.py`** | Thin wrapper → `agent_config.resolve_model()` |

### New config: `app/config/multi_agent_servers.yaml`

Declarative registry of all specialists — **no new Python per product**:

- `display_name`, `capabilities`, `integration_hints`, `peer_offers`, `peer_needs`
- `file_extensions`, `open_tool`, `state_tool`, `default_file_path`
- `tool_patterns` — regex for tool-name routing (config-driven, not hardcoded)
- `agent_playbook` — per-product MCP workflow instructions for the LLM
- `bootstrap_tool_calls`, `cross_product_scenarios`

### Modified in ai-core (integration commit + local WIP)

| File | Change |
|------|--------|
| `app/api/routes/agent.py` | Branch: `should_use_multi_agent` → `MultiAgentOrchestrationService` |
| `app/config.py` | `MULTI_AGENT_ENABLED` setting |
| `pyproject.toml` | Added `autogen-agentchat`, `autogen-core` dependencies |
| `app/llm/providers/openai_client.py` | `_convert_chat_messages_to_responses_input` for RS3 `/chat` tool loops |
| `app/models/chat.py` | `tool_calls` on `ChatMessage` for multi-turn tool history |

### rsgpt-be (`98bfb93`)

| File | Change |
|------|--------|
| `app/services/timeline_coalescer.py` | Persist multi-agent specialist handoff events in chat timeline |

### rsgpt-fe (`5aad934` + local)

| File | Change |
|------|--------|
| `src/hooks/useStreamPrompt.ts` | Handle multi-agent SSE events, tool failure logging |
| `src/hooks/useTimelineProcessor.ts` | Workflow trace / specialist transitions |
| `src/components/chat/display/agent-transition-indicator.tsx` | UI for specialist handoffs |
| `src/lib/types.ts` | New event types |

### rsgpt-desktop (local, not on integration branch)

| File | Change |
|------|--------|
| `src/main/mcp/mcpServer.ts` | Background MCP server load; 180s per-server timeout |
| `src/main/mcp/mcpClient.ts` | 300s gateway connect timeout |
| `python-servers/mcp-servers.json` | Enable RS2, RSPile, RS3, Settle3, Slide2 MCP servers |

---

## Config vs code (design principle)

After WIP cleanup, **product-specific data lives in YAML**:

- Tool name patterns → `ServerEntry.tool_patterns`
- Specialist playbooks → `ServerEntry.agent_playbook`
- Cross-product recipes → `cross_product_scenarios`
- Display names → `ServerEntry.display_name`

**Product-specific behavior** stays in Python only when it's an algorithm:

- `rs2_live_enrichment.py` — RS2 BigTool InitialConditions reads
- `enum_tool_args.py` — generic enum coercion (used heavily by RSPile)
- `validator.py` — evidence-based checks with some RS2/RSPile branches

---

## Peer RPC (cross-specialist Q&A)

Specialists expose `ask_agent_peer(target_server_id, question)`:

```
rspile-server  ──PeerQuery──▶  rs3-server
       ▲                            │
       └──────── PeerResponse ──────┘
```

- Handled in `specialist.py` → `run_specialist_llm(phase="peer_answer")`
- `peer_guard.py` limits depth and circular calls
- Timeout: `peer_rpc_timeout_seconds` in YAML (default 300s)
- RS3 peer answers are slow (inner coding agent via `/api/v1/chat`)

---

## SSE events (FE contract)

`MultiAgentSSEBridge` maps internal activity to events the production FE already understands:

| Event | Meaning |
|-------|---------|
| `agent.workflow.started` | Multi-agent run began |
| `agent.transition` | Planner picked specialist / handoff |
| `agent.tool_execution.started/completed/failed` | MCP tool on Desktop |
| `agent.thinking` | Specialist LLM step |
| `agent.workflow.completed` | Summarizer done |

---

## Adding a new Rocscience product

1. Add MCP server to Desktop `mcp-servers.json`
2. Add block under `servers:` in `multi_agent_servers.yaml` (patterns, open_tool, playbook)
3. Add `bootstrap_tool_calls` if needed
4. Optionally add `cross_product_scenarios` entry
5. **No new Python folder required** unless custom behavior (subclass `MCPSpecialistAgent` or add a hook)

---

## Monorepo layout

```
rsgpt-multi-agent-wip/
├── rsgpt-ai-core/          # Orchestrator + multi_agent package
├── rsgpt-be/               # API + timeline coalescer
├── rsgpt-fe/               # Agent mode UI
├── rsgpt-desktop/          # MCP gateway
└── docs/
```

All paths below are relative to **`rsgpt-ai-core/`** unless noted.

---

## Relation to demo repos

The integration ports logic from:

- `rsgpt-multi-agent-mcp-demo-v2` — AutoGen specialists, planner, validator, YAML catalog

Production differences:

- MCP via **Desktop WebSocket** (not local stdio MCP processes)
- SSE events match **production FE** types
- Wired into existing **`/api/v1/agent/stream`** behind feature flag
- Coexists with original single-agent orchestrator

---

## Known limitations (WIP)

| Area | Limitation |
|------|------------|
| RS3 | No simple material read — uses script agent (`run_rs3_agent`); slow, background jobs |
| Slide2 | No compute/FOS via MCP — edit `.slmd` only |
| Planner | Can mis-assign file paths when user attaches `.fez` but RS3 is selected |
| Desktop | Concurrent specialists contend on single MCP gateway → `list_tools` timeouts |
| Integration branches | Not yet merged to `qa` / `main` in individual repos |

See [RUNNING.md](./RUNNING.md) for local setup and troubleshooting.
