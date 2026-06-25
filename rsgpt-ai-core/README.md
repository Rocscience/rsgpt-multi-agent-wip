# RSGPT AI Core (`rsgpt-ai-core`)

## What Is This?

`rsgpt-ai-core` is a **FastAPI microservice** that serves as the **AI engine** for RSInsight. It receives requests from the backend (`rsgpt-be`), orchestrates LLM agent workflows, performs RAG (Retrieval-Augmented Generation) over Rocscience knowledge bases, communicates with desktop devices via WebSocket, and streams results back as SSE events.

**In one sentence:** rsgpt-ai-core takes a user prompt, runs it through an AI agent with access to knowledge search, web search, and desktop device tools, then streams the response back in real-time.

The frontend **never** communicates with this service directly — all requests come through `rsgpt-be`.

---

## System Architecture

```
                                    ┌──────────────────────────────────────────┐
                                    │           rsgpt-ai-core                  │
                                    │                                          │
  ┌──────────┐    HTTP/SSE          │  ┌─────────────────┐                     │
  │ rsgpt-be │ ──────────────────►  │  │  Agent Engine    │                     │
  │ (Backend)│ ◄──────────────────  │  │  (OpenAI Agents  │                     │
  └──────────┘                      │  │   SDK + LiteLLM) │                     │
                                    │  └────────┬────────┘                     │
                                    │           │                              │
                                    │     ┌─────┴─────┐                        │
                                    │     │           │                        │
                                    │  ┌──▼──┐   ┌───▼────┐   ┌───────────┐   │
                                    │  │Tools│   │Context │   │ Streaming │   │
                                    │  │     │   │Manager │   │ (SSE)     │   │
                                    │  └──┬──┘   └───┬────┘   └───────────┘   │
                                    │     │          │                         │
                                    └─────┼──────────┼─────────────────────────┘
                                          │          │
                        ┌─────────────────┼──────────┼─────────────────┐
                        │                 │          │                 │
                 ┌──────▼──────┐   ┌─────▼────┐  ┌──▼─────┐   ┌─────▼──────┐
                 │ LLM APIs    │   │ Pinecone │  │ Cohere │   │ Desktop    │
                 │ OpenAI      │   │ Vector   │  │Reranker│   │ Devices    │
                 │ Anthropic   │   │ Database │  │        │   │ (WebSocket)│
                 │ Perplexity  │   └──────────┘  └────────┘   └────────────┘
                 │ xAI         │
                 └─────────────┘
```

### How It Fits in the System

| Flow | Description |
|------|-------------|
| **BE → AI Core** | Backend sends streaming requests to `/api/v1/agent/stream`. Auth is M2M JWT (production) or `X-Service-Token` (development). |
| **AI Core → BE** | Streams SSE events back: text deltas, tool executions, search results, workflow status, usage data. |
| **AI Core → LLM APIs** | Calls OpenAI/Anthropic/Perplexity/xAI for completions via LiteLLM abstraction. |
| **AI Core → Pinecone** | Vector search for RAG — embeds queries, searches across channel-specific indexes/namespaces. |
| **AI Core → Cohere** | Reranks retrieved documents for relevance before injecting into LLM context. |
| **AI Core ↔ Desktop** | Bidirectional WebSocket connections with desktop apps for device tool execution (RS2, RSPile). |
| **MCP Servers → AI Core** | MCP servers call `/search/semantic` and `/rerank` endpoints for knowledge access (authenticated via `X-Service-Token`). |

---

## Key Responsibilities

### 1. Agent Orchestration (Core Feature)
- Single-agent architecture with two modes: **Ask** (knowledge-only) and **Agent** (full tools)
- Uses [OpenAI Agents SDK](https://github.com/openai/openai-agents-python) (custom Rocscience fork) with LiteLLM for cross-model support
- Dynamic tool loading based on mode and connected devices
- Automatic context pruning when token limits are reached
- Conversation persistence via SDK sessions (PostgreSQL-backed)

### 2. RAG Pipeline
- Embeds user queries with OpenAI `text-embedding-3-small`
- Searches Pinecone vector databases across channel-specific indexes
- Reranks results with Cohere `rerank-v3.5`
- Supports encrypted channels (tech_support uses AES encryption)
- Permission-aware: BASIC users get docs only, FLEXIBLE users get docs + tech support

### 3. Multi-Provider LLM Support
- OpenAI (GPT-5, GPT-5.1, GPT-5.2)
- Anthropic (Claude Sonnet 4.5, Haiku 4.5, Opus 4.5)
- xAI (Grok 4.1 Fast — reasoning and non-reasoning)
- Perplexity (Sonar, Sonar Reasoning — Ask mode only, no tool support)
- Unified interface via LiteLLM — models can be switched mid-conversation

### 4. Device Communication
- WebSocket connections from desktop apps (RS2, RSPile)
- Dynamic tool discovery — agent loads device-specific tools at runtime
- Tool invocation with 30-minute timeout (for slow simulation operations)
- File path selection requests (native OS file dialog on device)

### 5. Streaming SSE Events
- Real-time event streaming with 20+ event types
- Heartbeat mechanism (15s interval) to prevent Vercel Edge timeout
- Events cover: text deltas, tool execution lifecycle, workflow status, context usage, search results

### 6. Context Management
- Token tracking per session (persisted to PostgreSQL)
- Automatic summarization when context exceeds 90% of model's input limit
- Pruned history persistence to SDK session
- Model-specific token counting via tiktoken

---

## Project Structure

```
rsgpt-ai-core/
├── app/
│   ├── main.py                          # FastAPI app, CORS, lifespan, tracing setup
│   ├── config.py                        # Pydantic Settings (all env vars + config.yml loading)
│   ├── auth.py                          # Auth0 FastAPI plugin setup
│   ├── dependencies.py                  # FastAPI Depends() — auth verification
│   │
│   ├── api/
│   │   ├── main.py                      # /api/v1 sub-application, router registration
│   │   └── routes/
│   │       ├── agent.py                 # POST /agent/stream — main agent endpoint
│   │       ├── chat.py                  # POST /chat/stream — legacy chat endpoint
│   │       ├── config.py               # Channel configuration endpoints
│   │       ├── context.py              # Context search endpoint
│   │       ├── health.py               # Health check endpoints
│   │       ├── rerank.py               # Document reranking endpoint (MCP use)
│   │       ├── search.py              # Raw semantic search endpoint (MCP use)
│   │       └── websocket.py           # WebSocket device connections + HTTP helpers
│   │
│   ├── services/
│   │   ├── agent/                       # Agent orchestration (the big one)
│   │   │   ├── orchestration_service.py # Main workflow: creates agent, runs stream, collects results
│   │   │   ├── main_agent.py           # Agent creation (OpenAI Agents SDK + LiteLLM)
│   │   │   ├── agent_config.py         # Agent configuration (turns, model defaults)
│   │   │   ├── instructions.py         # System prompts for agent and ask modes
│   │   │   ├── session_factory.py      # SQLAlchemy SDK session management
│   │   │   ├── sse_event_emitter.py    # Transforms SDK events → SSE events
│   │   │   ├── summarizer_agent.py     # Summarizer agent for context pruning
│   │   │   └── tools/
│   │   │       ├── base_tools.py       # search_knowledge + search_web tools
│   │   │       ├── device_tools.py     # Dynamic device tool loading via WebSocket
│   │   │       ├── limited_tools.py    # Rate-limited tools for Ask mode
│   │   │       └── tool_initializer.py # Mode-aware tool assembly
│   │   │
│   │   ├── auth/
│   │   │   └── auth_service.py         # JWT validation (Auth0 JWKS)
│   │   │
│   │   ├── config/
│   │   │   ├── config_service.py       # YAML config loading (channels, models)
│   │   │   └── conductor_service.py    # Source channel → internal channel mapping
│   │   │
│   │   ├── context_manager/
│   │   │   ├── context_manager_hooks.py # Token tracking + auto-summarization hooks
│   │   │   └── token_counter.py        # Model-aware token counting (tiktoken)
│   │   │
│   │   ├── reranker/
│   │   │   ├── reranker_service.py     # Reranker orchestration
│   │   │   ├── cohere_reranker.py      # Cohere rerank-v3.5
│   │   │   └── keep_topk_reranker.py   # Fallback no-op reranker
│   │   │
│   │   ├── search/
│   │   │   ├── rag_service.py          # Full RAG pipeline (embed → search → rerank)
│   │   │   ├── context_service.py      # Unified context retrieval interface
│   │   │   ├── embedding_service.py    # OpenAI text-embedding-3-small
│   │   │   ├── pinecone_service.py     # Pinecone vector search
│   │   │   └── encryption_service.py   # AES decryption for encrypted channels
│   │   │
│   │   └── streaming/
│   │       ├── streaming_service.py    # Legacy chat streaming (non-agent)
│   │       ├── chat_instructions.py    # System prompts for chat mode
│   │       └── websocket_service.py    # WebSocket ConnectionManager
│   │
│   ├── llm/                             # LLM provider abstraction
│   │   ├── enums.py                     # Provider and model enums
│   │   ├── factory.py                   # Provider factory (creates correct client)
│   │   ├── service.py                   # LLM service layer
│   │   └── providers/
│   │       ├── base.py                  # Base provider interface
│   │       ├── openai_client.py         # OpenAI Responses API client
│   │       ├── claude_client.py         # Anthropic Claude client
│   │       ├── perplexity_client.py     # Perplexity (OpenAI-compatible)
│   │       └── litellm_client.py        # LiteLLM wrapper for Agent SDK
│   │
│   ├── db_models/
│   │   ├── base.py                      # BaseDbModel (UUID PK, timestamps)
│   │   ├── connection.py                # Async SQLAlchemy engine setup
│   │   └── sessions.py                  # AgentSessions + AgentMessages ORM
│   │
│   ├── models/                          # Pydantic DTOs
│   │   ├── agent.py                     # Agent request/response + 20+ event models
│   │   ├── channels.py                  # Channel/source enums + permission mapping
│   │   ├── chat.py                      # Chat request/response + stream events
│   │   ├── consts.py                    # Constants (client types)
│   │   ├── context.py                   # Context search DTOs
│   │   ├── file_path.py                 # File path request DTO
│   │   ├── rerank.py                    # Rerank request/response DTOs
│   │   ├── services.py                  # Service name constants
│   │   └── system.py                    # Health/config response DTOs
│   │
│   └── utils/                           # (currently empty)
│
├── alembic/                             # Database migrations
│   └── versions/                        # 2 migrations (sessions tables, token tracking)
├── config.yml                           # Channel configs + supported model definitions
├── guides/                              # Architecture decision docs
│   ├── AGENT_REFACTORING_PLAN.md
│   ├── AGENT_STREAMING_GUIDE.md
│   ├── CONTEXT_PRUNING_PLAN.md
│   ├── CONTEXT_SYSTEM_GUIDE.md
│   ├── RAG_SYSTEM_GUIDE.md
│   └── RSLOG_MCP_INTEGRATION.md
├── tests/
├── docker-compose.yml                   # PostgreSQL 17
├── Dockerfile                           # Python 3.13-slim, port 8090
├── example.env
├── pyproject.toml                       # Poetry dependencies
└── pytest.ini
```

---

## Layered Architecture

```
Request (from rsgpt-be)
  │
  ▼
Routes (app/api/routes/)               ← HTTP/WebSocket handling, auth verification
  │
  ▼
Orchestration (app/services/agent/)    ← Agent creation, workflow lifecycle, event emission
  │
  ├──► Tools (app/services/agent/tools/)  ← search_knowledge, search_web, device tools
  ├──► Context Manager (app/services/context_manager/) ← Token tracking, auto-summarization
  └──► Session Factory (app/services/agent/session_factory.py) ← Conversation persistence
  │
  ▼
Search/RAG (app/services/search/)      ← Embedding, Pinecone search, reranking
  │
  ▼
LLM Providers (app/llm/)              ← OpenAI, Anthropic, Perplexity, xAI via LiteLLM
  │
  ▼
External APIs (OpenAI, Pinecone, Cohere, etc.)
```

---

## API Endpoints

### Root (`/`)
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/` | None | API info (version, environment) |
| GET | `/health` | None | Health check for load balancers |
| GET | `/config` | None | Non-sensitive config (dev only) |

### Agent (`/api/v1/agent`) — *Core Feature*
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/` | None | Agent service info (active runs, connected devices) |
| POST | `/stream` | BE auth | **Stream agent workflow response (SSE)** |
| GET | `/devices` | None | List connected desktop devices |
| GET | `/runs` | None | List active agent runs |

### Chat (`/api/v1/chat`) — *Legacy*
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/` | None | Chat service info (available providers) |
| POST | `/` | BE auth | Non-streaming chat completion |
| POST | `/stream` | BE auth | Streaming chat completion (SSE) |

### Context (`/api/v1/context`)
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/search` | None | Search across knowledge channels |
| GET | `/stats` | None | Channel and database statistics |
| GET | `/health` | None | Context service health |

### Config (`/api/v1/config`)
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/channels` | None | List all channel configurations |
| GET | `/channels/{channel}` | None | Get specific channel config |
| POST | `/reload` | None | Hot-reload config.yml |
| GET | `/health` | None | Config service health |

### Rerank (`/api/v1/rerank`) — *Used by MCP servers*
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/` | MCP token | Rerank documents by relevance |
| GET | `/health` | None | Reranker service health |

### Search (`/api/v1/search`) — *Used by MCP servers*
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/semantic` | MCP token | Raw semantic search on Pinecone |

### WebSocket (`/api/v1/ws`) — *Desktop device communication*
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| WS | `/device/{device_id}` | JWT + desktop | WebSocket connection for desktop devices |
| GET | `/devices` | None | List connected devices |
| POST | `/send/{device_id}` | None | Send message to device |
| POST | `/send/user/{user_id}` | None | Send message to all user devices |
| POST | `/broadcast` | None | Broadcast to all devices |
| POST | `/list_tools/{device_id}` | None | Request tool list from device |
| POST | `/invoke_tool/{device_id}` | None | Invoke tool on device |
| POST | `/request_file_path/{device_id}` | BE auth | Request file path from device |

### Health (`/api/v1/health`)
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/` | None | Basic health check |
| GET | `/detailed` | None | Detailed health with system metrics |

---

## Authentication

### Backend → AI Core (BE auth)
- **Production:** Auth0 M2M JWT token + `X-Client-Type: backend` header
- **Development/Testing:** Static `X-Service-Token` header (`BE_SERVICE_TOKEN`)

### MCP Servers → AI Core (MCP token)
- Static `X-Service-Token` header (`MCP_SERVICE_TOKEN`)
- Used in both dev and production

### Desktop → AI Core (WebSocket)
- JWT Bearer token in `Authorization` header
- `X-Client-Type: desktop` header required in production
- Token validated against Auth0 JWKS

---

## Core Data Flow: Agent Streaming

This is the most important flow. Here's what happens when `rsgpt-be` sends a prompt:

```
1. BE sends POST /api/v1/agent/stream
   ├── Body: { input, session_id, mode, model, device_id, user_permission, source_channels, ... }
   ├── Auth: M2M JWT or X-Service-Token
   │
2. Orchestration Service starts workflow:
   ├── Emits: agent.workflow.started (with trace_id from OpenAI tracing)
   ├── Creates Agent with:
   │   ├── System instructions (mode-specific: ASK vs AGENT)
   │   ├── Tools (mode-aware + device tools if connected)
   │   ├── LiteLLM model configuration
   │   └── Context management hooks
   │
3. SDK Session initialized:
   ├── Loads conversation history from PostgreSQL
   ├── Checks token count — if > 90% of model limit, triggers summarization
   │
4. Agent SDK runs (streaming):
   │
   │  ┌─── Agent Loop (up to 15 turns ASK / 150 turns AGENT) ────┐
   │  │                                                            │
   │  │  LLM generates response with tool calls                   │
   │  │     │                                                      │
   │  │     ├── search_knowledge → Embed → Pinecone → Cohere      │
   │  │     ├── search_web → Perplexity API                       │
   │  │     ├── device_tool → WebSocket → Desktop App              │
   │  │     │                                                      │
   │  │  Tool results fed back to LLM                             │
   │  │  Agent decides: more tools needed? or final response?      │
   │  │                                                            │
   │  └──────────────────────────────────────────────────────────┘
   │
5. SSE events streamed throughout:
   ├── agent.workflow.status_changed   → "Researching", "Planning", etc.
   ├── agent.tool_execution.started    → Tool name + args
   ├── agent.tool_execution.completed  → Tool results
   ├── agent.thinking                  → Reasoning steps (thinking models)
   ├── agent.message.delta             → Incremental text output
   ├── response.search_results         → Extracted URLs/sources
   ├── context.usage                   → Token counts
   ├── agent.heartbeat                 → Keepalive (every 15s)
   │
6. On completion:
   ├── Emits: agent.workflow.completed (with usage_breakdown, total_tokens, trace_id)
   ├── Persists token count to session DB
   └── Cleans up active run tracking
```

---

## Agent Architecture

### Single-Agent Design
There is **one main agent** that handles all workflows. Its behavior changes based on the **mode**:

| | Ask Mode | Agent Mode |
|--|----------|------------|
| **Purpose** | Knowledge retrieval only | Full capabilities |
| **Max turns** | 15 | 150 |
| **Tools** | search_knowledge (8x), search_web (7x) | Unlimited search + device tools |
| **Providers** | All (including Perplexity) | OpenAI, Anthropic, xAI only |
| **Quota** | Organization quota | Per-user agent quota |

### Tools

**Always available:**
| Tool | Description |
|------|-------------|
| `search_knowledge` | RAG search across Pinecone vector databases. Supports channels: ROC, DIANA, 3GSM, 2SI, ROCKFIELD, AQUANTY. Permission-aware. |
| `search_web` | Real-time web search via Perplexity API. Returns titles, URLs, snippets. |

**Device tools (Agent mode only, dynamically loaded):**
| Tool Pattern | Description |
|--------------|-------------|
| `RS2_*` | RS2 desktop application tools (loaded via WebSocket from connected device) |
| `RSPile_*` | RSPile desktop application tools |

Device tools are discovered at runtime — the agent asks the desktop app "what tools do you have?" over WebSocket, then registers them dynamically. Tools refresh after each execution.

### Context Pruning
When a conversation exceeds 90% of the model's context window:
1. A **Summarizer Agent** (GPT-5 Mini) creates a structured summary
2. Old messages are replaced with the summary
3. The pruned history is persisted to the SDK session
4. Frontend is notified via `context.summarizing` / `context.pruning_completed` events

---

## RAG Pipeline

```
User Query
  │
  ▼
1. Embedding (OpenAI text-embedding-3-small, 1536 dims)
  │
  ▼
2. Permission Mapping (ConductorService)
   ├── BASIC users → documentation channel only
   └── FLEXIBLE users → documentation + tech_support
  │
  ▼
3. Vector Search (Pinecone)
   ├── Multi-channel: searches each channel's index/namespace
   ├── Encrypted channels: AES decryption for tech_support
   └── Returns top_k results per channel (default: 20-30)
  │
  ▼
4. Reranking (Cohere rerank-v3.5)
   ├── Reranks all results by relevance to query
   └── Fallback: KeepTopK if Cohere unavailable
  │
  ▼
5. Results returned to agent as tool output
   ├── Context text, scores, rerank scores
   ├── Metadata: title, URL, file_name, page_number, software
   └── Channel attribution
```

### Knowledge Channels (from `config.yml`)

| Channel | Pinecone Index | Description |
|---------|---------------|-------------|
| documentation | `rocumentation-files` | Rocscience product documentation |
| tech_support | `rsgpt-feb` (encrypted) | Technical support articles |
| diana | `rsgpt-feb` | DIANA software knowledge |
| three_gsm | `3gsm` | 3GSM software knowledge |
| two_si | `twosi-complete` | 2SI software knowledge |
| rockfield | `rsgpt-feb` | Rockfield software knowledge |
| aquanty | `aquanty` | Aquanty software knowledge |

### Source Channel → Internal Channel Mapping
Users select **source channels** (e.g., "ROC"), which are mapped to **internal channels** based on permission:
- `ROC` + BASIC → `[documentation]`
- `ROC` + FLEXIBLE → `[documentation, tech_support]`
- `DIANA` → `[diana]` (any permission)
- etc.

---

## Supported Models (from `config.yml`)

| Model | Provider | Max Input Tokens | Max Output Tokens |
|-------|----------|-----------------|-------------------|
| gpt-5.1-2025-11-13 | OpenAI | 350,000 | 128,000 |
| gpt-5.2-2025-12-11 | OpenAI | 350,000 | 128,000 |
| claude-sonnet-4-5-20250929 | Anthropic | 200,000 | 64,000 |
| claude-haiku-4-5-20251001 | Anthropic | 200,000 | 64,000 |
| claude-opus-4-5-20251101 | Anthropic | 200,000 | 64,000 |
| grok-4-1-fast-reasoning | xAI | 350,000 | 64,000 |
| grok-4-1-fast-non-reasoning | xAI | 350,000 | 64,000 |
| sonar-reasoning | Perplexity | 128,000 | 8,000 |

Models are configured in `config.yml` under `supported_models` with token limits and encoding info used by the context manager.

---

## SSE Event Types

The agent streaming endpoint emits these event types:

### Workflow Lifecycle
| Event | When |
|-------|------|
| `agent.workflow.started` | Workflow begins (includes trace_id) |
| `agent.workflow.status_changed` | Status transition (researching, planning, executing, etc.) |
| `agent.workflow.completed` | Workflow finished (includes usage_breakdown, total_tokens) |
| `agent.workflow.failed` | Workflow errored |

### Agent Communication
| Event | When |
|-------|------|
| `agent.message.delta` | Incremental text from the agent |
| `agent.message.done` | Agent finished generating text |
| `agent.thinking` | Reasoning steps (for thinking-capable models) |
| `agent.planning` | Plan creation |
| `agent.task_progress` | Task execution progress |
| `agent.transition` | Agent mode transition |
| `agent.out_of_scope` | Request deemed out of scope |
| `agent.heartbeat` | Keepalive (every 15s) |

### Tool Execution
| Event | When |
|-------|------|
| `agent.tool_execution.started` | Tool call begins (name + arguments) |
| `agent.tool_execution.completed` | Tool call finished (with results) |
| `agent.tool_execution.failed` | Tool call errored |

### Context Management
| Event | When |
|-------|------|
| `context.usage` | Token usage update |
| `context.summarizing` | Context pruning started |
| `context.pruning_completed` | Context pruning finished |
| `context.pruning_error` | Context pruning failed |

### Search Results
| Event | When |
|-------|------|
| `response.search_results` | URLs/sources extracted from search |

---

## WebSocket Device Communication

Desktop apps (RS2, RSPile) connect to AI Core via WebSocket:

```
Desktop App                          AI Core
    │                                    │
    │──── WS /api/v1/ws/device/{id} ───►│  (JWT auth + X-Client-Type: desktop)
    │◄─── Connection accepted ──────────│
    │                                    │
    │◄─── list_tools_request ───────────│  (Agent needs tool list)
    │──── list_tools_response ─────────►│  (Returns available tools)
    │                                    │
    │◄─── invoke_tool_request ──────────│  (Agent calls a tool)
    │──── invoke_tool_response ────────►│  (Returns tool result)
    │                                    │
    │──── heartbeat ───────────────────►│  (Keepalive)
    │◄─── pong ─────────────────────────│
    │                                    │
    │◄─── file_path_request ────────────│  (Opens native file dialog)
    │──── file_path_response ──────────►│  (Returns selected path)
```

**Connection Manager** tracks all connections in-memory:
- `connected_devices` — device_id → WebSocket
- `user_devices` — user_id → Set[device_id]
- `pending_requests` — message_id → asyncio.Future (for request/response pattern)

**Important limitation:** WebSocket connections are in-memory. With multiple workers, connections are NOT shared. Production requires AWS ALB sticky sessions.

---

## Database

### Tech Stack
- **PostgreSQL 17** (local via Docker on port 5433, managed in production)
- **SQLAlchemy** async ORM with asyncpg driver
- **Alembic** for migrations

### Tables
| Table | Purpose |
|-------|---------|
| `agent_sessions` | SDK session tracking — stores session metadata + token counts |
| `agent_messages` | Serialized conversation messages for multi-turn context |

Token tracking columns on `agent_sessions`:
- `last_input_tokens` — last known token count
- `last_model_name` — model used
- `token_updated_at` — timestamp

These enable fast pre-run threshold checks without re-counting tokens.

---

## Getting Started

### Prerequisites
- Python 3.13+
- [Poetry](https://python-poetry.org/)
- Docker (for local PostgreSQL)
- API keys: OpenAI, Anthropic (optional), Perplexity (optional), Pinecone, Cohere (optional)

### Setup

```bash
# 1. Install dependencies
pip install poetry    # if not installed
poetry install

# 2. Copy environment template
cp example.env .env
# Edit .env — at minimum you need:
#   OPENAI_API_KEY, PINECONE_API_KEY, BE_SERVICE_TOKEN, DATABASE_URL

# 3. Start local PostgreSQL
docker-compose up -d

# 4. Run database migrations
poetry run alembic upgrade head

# 5. Start the dev server
poetry run start
```

The API is available at `http://localhost:8090` with docs at `http://localhost:8090/docs`.

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ENVIRONMENT` | Yes | `development` / `production` / `testing` |
| `HOST` | No | Server host (default: `0.0.0.0`) |
| `PORT` | No | Server port (default: `8090`) |
| `UVICORN_WORKERS` | No | Worker count (default: `1` — required for WebSocket) |
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| **Auth** | | |
| `AUTH0_DOMAIN` | Prod | Auth0 tenant domain |
| `AUTH0_AUDIENCE` | Prod | Auth0 API audience for this service |
| `AUTH0_ALGORITHMS` | No | JWT algorithms (default: `RS256`) |
| `BE_SERVICE_TOKEN` | Yes | Static token for backend auth (dev) |
| `MCP_SERVICE_TOKEN` | Yes | Static token for MCP server auth |
| `SECRET_KEY` | Prod | Application secret key |
| **LLM APIs** | | |
| `OPENAI_API_KEY` | Yes | OpenAI API key (also enables tracing for all models) |
| `ANTHROPIC_API_KEY` | No | Anthropic API key |
| `PERPLEXITY_API_KEY` | No | Perplexity API key |
| `XAI_API_KEY` | No | xAI (Grok) API key |
| **RAG** | | |
| `PINECONE_API_KEY` | Yes | Pinecone vector database key |
| `PINECONE_DEFAULT_TOP_K` | No | Default results per search (default: `20`) |
| `COHERE_API_KEY` | No | Cohere reranker key (fallback: TopK) |
| `AES_ENCRYPTOR_KEY` | No | Fernet key for encrypted channels (tech_support) |
| **MCP** | | |
| `RSLOG_MCP_URL` | No | RSLog MCP server URL |
| `RSLOG_MCP_TIMEOUT` | No | MCP request timeout (default: `30`) |
| **Other** | | |
| `CORS_ORIGINS` | No | Comma-separated allowed origins |
| `LOG_LEVEL` | No | Logging level (default: `INFO`) |
| `DEFAULT_LLM_PROVIDER` | No | Default provider (default: `openai`) |

---

## Configuration File (`config.yml`)

This YAML file (hot-reloadable via `POST /api/v1/config/reload`) defines:

1. **`context_stores`** — Pinecone index/namespace configuration per channel
2. **`supported_models`** — Model definitions with token limits and encoding
3. **`defaults`** — Default top_k, embedding model, similarity threshold

The context manager uses `supported_models` to know each model's token limits for automatic pruning.

---

## Testing

```bash
# Run all tests
poetry run pytest

# Run with coverage
poetry run pytest --cov=app --cov-report=html
```

Test structure mirrors the app structure under `tests/`.

---

## Deployment

### CI/CD
- GitHub Actions workflows in `.github/workflows/`
- `qa.yml` — deploys to QA
- `production.yml` — deploys to production
- `pull_request.yml` — runs tests on PR
- `_deploy.yml` — shared deployment logic

### Docker

```bash
docker build -t rsgpt-ai-core .
docker run -p 8090:8090 --env-file .env rsgpt-ai-core
```

Python 3.13-slim, Poetry 1.8.3, health check on port 8090. Default 1 worker (required for WebSocket — sticky sessions needed for multi-worker).

---

## Developer Quick Reference

### Adding a New Tool

1. Define the tool function in `app/services/agent/tools/base_tools.py` (or new file)
2. Register it in `app/services/agent/tools/tool_initializer.py` — add to appropriate mode (ASK, AGENT, or both)
3. If Ask mode, add to `ASK_MODE_LIMITS` in `limited_tools.py`
4. Update agent instructions in `app/services/agent/instructions.py` if the agent needs guidance

### Adding a New LLM Provider

1. Create provider client in `app/llm/providers/` (extend `BaseLLMProvider`)
2. Add enum value to `app/llm/enums.py`
3. Register in `app/llm/factory.py`
4. Add model definitions to `config.yml` under `supported_models`

### Adding a New Knowledge Channel

1. Add channel config to `config.yml` under `context_stores`
2. Add enum values to `app/models/channels.py` (`SourceChannel`, `Channel`)
3. Update `SOURCE_CHANNEL_MAPPING` in `channels.py` for permission mapping
4. Update `CHANNEL_CONFIG_KEYS` mapping

### Key Files to Understand First

| File | Why |
|------|-----|
| `app/services/agent/orchestration_service.py` | The main workflow — creates agent, runs stream, collects results |
| `app/services/agent/main_agent.py` | How the agent is created (model, tools, instructions) |
| `app/services/agent/tools/base_tools.py` | The two core tools: search_knowledge and search_web |
| `app/services/agent/sse_event_emitter.py` | How SDK events become SSE events |
| `app/services/search/rag_service.py` | The full RAG pipeline |
| `app/services/context_manager/context_manager_hooks.py` | Auto-summarization logic |
| `app/services/streaming/websocket_service.py` | WebSocket ConnectionManager |
| `config.yml` | Channel configs and model definitions |
| `app/models/agent.py` | All agent DTOs and event models |
| `app/config.py` | All environment variables and settings |

---

**Project Status**: Active Development
**Last Updated**: February 2026
**Team**: RSInsight Development Team
