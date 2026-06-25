# RSGPT Backend Service (`rsgpt-be`)

## What Is This?

`rsgpt-be` is a **FastAPI microservice** that acts as the **API gateway** between the frontend (`rsgpt-fe`) and the AI engine (`rsgpt-ai-core`). It owns all business logic, user management, quota enforcement, data persistence, and external integrations — the frontend never talks to AI Core directly.

**In one sentence:** rsgpt-be receives user requests from the frontend, enforces business rules, proxies them to AI Core for processing, and streams results back — while persisting everything to PostgreSQL.

---

## System Architecture

```
┌──────────────────┐         ┌──────────────────┐         ┌──────────────────┐
│   rsgpt-fe       │         │   rsgpt-be       │         │  rsgpt-ai-core   │
│   (Next.js)      │  HTTP   │   (FastAPI)      │  HTTP   │  (AI Engine)     │
│   Vercel         │────────►│   AWS EC2        │────────►│  AWS EC2         │
│                  │◄────────│                  │◄────────│                  │
│                  │   SSE   │                  │   SSE   │                  │
└──────────────────┘         └────────┬─────────┘         └──────────────────┘
                                      │
                        ┌─────────────┼─────────────┐
                        │             │             │
                 ┌──────▼───┐  ┌─────▼─────┐  ┌───▼────────┐
                 │ Auth0    │  │ RocPortal │  │ AWS S3     │
                 │ OAuth2   │  │ Licensing │  │ Releases   │
                 └──────────┘  └───────────┘  └────────────┘
                        │
                 ┌──────▼──────┐
                 │ PostgreSQL  │
                 │ (Primary DB)│
                 └─────────────┘
```

### How the Three Services Interact

| Flow | Description |
|------|-------------|
| **FE → BE** | Frontend sends HTTP requests to `rsgpt-be` via Next.js API route proxies. Auth0 JWT tokens are attached as `Authorization: Bearer` headers. |
| **BE → AI Core** | Backend calls AI Core's streaming endpoints (`/api/v1/agent/stream`). Auth is M2M JWT (production) or `X-Service-Token` (development). |
| **BE → FE (streaming)** | Backend proxies SSE events from AI Core back to the frontend in real-time. The frontend connects directly to the backend stream URL (bypasses Vercel). |
| **BE → PostgreSQL** | All chat sessions, messages, user data, quotas, and device registrations are persisted here. |
| **BE → RocPortal** | License validation and organization data retrieval for quota management. |
| **BE → AWS S3** | Generates presigned URLs for MCP server downloads and desktop installer releases. |

---

## Key Responsibilities

### 1. User & Organization Management
- Creates/retrieves users from Auth0 on first login
- Maps users to organizations via RocPortal license data
- Manages user settings (model preferences, theme, etc.)
- Calculates quotas from license types (FCL/PCL)

### 2. Chat Session Orchestration
- Creates and manages chat sessions per user
- Validates quotas before allowing messages (org quota for Ask mode, agent quota for Agent mode)
- Validates source channel selections
- Proxies streaming requests to AI Core and streams SSE events back
- Accumulates and persists AI response text, timeline events, search results, and usage data
- Handles retry, cancellation, and partial response saving

### 3. Quota Enforcement
- **Organization quota** — shared across org users, reset daily at 2 AM UTC
- **Agent quota** — per-user, reset monthly on the 1st
- Quota request system (users request increases, admins approve/deny)
- Scheduled cron jobs via APScheduler

### 4. Device Management
- Registers desktop app devices
- Manages device status (active/inactive)
- Proxies file-path selection requests to devices via AI Core

### 5. MCP Registry
- Lists, details, and distributes MCP (Model Context Protocol) servers
- Generates presigned S3 URLs for downloads
- Tracks installation logs
- Accepts registrations from GitHub Actions CI/CD

### 6. RSLog Integration
- Authenticates users with RSLog (username/password + 2FA)
- Encrypts and stores RSLog credentials (Fernet encryption)
- Manages token refresh lifecycle

### 7. External Service Gateway
- Auth0 — JWT validation, M2M tokens for service-to-service auth
- RocPortal — license/org lookups
- AWS S3 — presigned URL generation
- AI Core — streaming chat/agent completions

---

## Project Structure

```
rsgpt-be/
├── app/
│   ├── main.py                     # FastAPI app, CORS, lifespan, root endpoints
│   ├── config.py                   # Pydantic Settings (env vars, typed config)
│   ├── auth.py                     # Auth0 FastAPI plugin setup
│   ├── dependencies.py             # FastAPI Depends() — auth, service injection
│   ├── scheduler.py                # APScheduler cron jobs (quota resets)
│   │
│   ├── api/
│   │   ├── main.py                 # /api/v1 sub-application setup
│   │   └── routes/
│   │       ├── admin.py            # Admin quota management (X-Admin-Token)
│   │       ├── auth.py             # Service token endpoints
│   │       ├── chat.py             # Chat sessions & streaming (core feature)
│   │       ├── desktop.py          # Desktop installer presigned URLs
│   │       ├── device.py           # Device registration & management
│   │       ├── health.py           # Health check endpoints
│   │       ├── mcp_registry.py     # MCP server registry
│   │       ├── quota.py            # Quota scheduler status
│   │       ├── rslog.py            # RSLog integration
│   │       └── user.py             # User settings & quota info
│   │
│   ├── services/                   # Business logic layer
│   │   ├── ai_core_client.py       # HTTP client for rsgpt-ai-core (streaming)
│   │   ├── auth0_m2m_service.py    # Auth0 M2M token service (Client Credentials)
│   │   ├── chat_service.py         # Chat orchestration (the big one)
│   │   ├── desktop_service.py      # Desktop release management
│   │   ├── media_extractor_service.py  # Extract media from search result URLs
│   │   ├── mcp_registry_service.py # MCP registry business logic
│   │   ├── quota_service.py        # Quota reset cron logic
│   │   ├── rslog_service.py        # RSLog auth & token management
│   │   ├── s3_service.py           # AWS S3 presigned URL generation
│   │   ├── secrets_manager_service.py  # Service token validation
│   │   ├── timeline_coalescer.py   # Coalesces streaming events for storage
│   │   └── user_service.py         # User/org CRUD, quota calculation
│   │
│   ├── db_interface/               # Database access layer (queries)
│   │   ├── chats.py
│   │   ├── devices.py
│   │   ├── feedback.py
│   │   ├── mcp_registry.py
│   │   ├── organizations.py
│   │   ├── quota_requests.py
│   │   ├── rslog.py
│   │   └── users.py
│   │
│   ├── db_models/                  # SQLAlchemy ORM models
│   │   ├── base.py                 # BaseDbModel (UUID PK, timestamps, soft delete)
│   │   ├── chats.py                # ChatSessions, UserMessages, AIResponses
│   │   ├── connection.py           # DB engine, pooling, health check
│   │   ├── devices.py
│   │   ├── feedback.py
│   │   ├── mcp_install_logs.py
│   │   ├── mcp_registry.py
│   │   ├── organizations.py
│   │   ├── quota_requests.py
│   │   ├── rslog.py
│   │   ├── system.py
│   │   └── users.py
│   │
│   ├── models/                     # Pydantic DTOs (request/response schemas)
│   │   ├── auth.py
│   │   ├── chats.py
│   │   ├── consts.py               # Quota limits, constants
│   │   ├── devices.py
│   │   ├── enums.py                # Providers, models, statuses
│   │   ├── feedback.py
│   │   ├── mcp_registry.py
│   │   ├── organizations.py
│   │   ├── quota.py
│   │   ├── quota_requests.py
│   │   ├── rslog.py
│   │   ├── system.py
│   │   └── users.py
│   │
│   └── utils/
│       ├── crypto.py               # Fernet encryption (RSLog credentials)
│       └── version.py              # Semantic version parsing
│
├── alembic/                        # Database migrations
│   ├── versions/                   # Migration files (30+)
│   ├── env.py
│   └── script.py.mako
│
├── tests/                          # Test suite
├── alembic.ini
├── docker-compose.yml              # Local PostgreSQL 15
├── Dockerfile                      # Python 3.13-slim, Poetry 1.8.3
├── example.env                     # Environment variable template
├── pyproject.toml                  # Poetry dependencies
└── pytest.ini
```

---

## Layered Architecture

The codebase follows a strict **Routes → Services → DB Interface → DB Models** layering:

```
Request
  │
  ▼
Routes (app/api/routes/)          ← HTTP handling, input validation, auth
  │
  ▼
Services (app/services/)          ← Business logic, orchestration, external calls
  │
  ▼
DB Interface (app/db_interface/)  ← Database queries (SQLAlchemy)
  │
  ▼
DB Models (app/db_models/)        ← ORM model definitions
  │
  ▼
PostgreSQL
```

**Rules:**
- Routes call services, never DB directly
- Services call db_interface for data access
- DTOs (Pydantic models in `models/`) define request/response shapes
- DB models define the database schema

---

## API Endpoints

### Root (`/`)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | API info (name, version, environment) |
| GET | `/health` | Basic health check |
| GET | `/version` | Version info with Git SHA |

### Chat & AI (`/api/v1/chat`) — *Core Feature*
| Method | Path | Description |
|--------|------|-------------|
| POST | `/sessions` | Create a new chat session |
| GET | `/sessions` | List user's chat sessions (paginated) |
| GET | `/sessions/{session_id}` | Get session details |
| DELETE | `/sessions/{session_id}` | Delete a session |
| POST | `/sessions/stream/{session_id}` | Stream a chat message (SSE) |
| GET | `/sessions/conversation/{session_id}` | Get conversation history (paginated) |
| POST | `/sessions/retry/{user_message_id}` | Retry a failed prompt |
| POST | `/sessions/feedback/{ai_response_id}` | Submit feedback on AI response |

### User (`/api/v1/user`)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Get authenticated user info |
| GET | `/rocportal-status` | Get RocPortal license status (cached) |
| PUT | `/rocportal-status` | Force-refresh RocPortal status |
| GET | `/quota-info` | Get org & agent quota info |
| GET | `/settings` | Get user settings |
| PUT | `/settings` | Update user settings |
| POST | `/quota-request` | Request additional agent quota |

### Device (`/api/v1/device`)
| Method | Path | Description |
|--------|------|-------------|
| POST | `/register` | Register/update a desktop device |
| PUT | `/{device_id}/status` | Update device status |
| GET | `/` | List user's devices |
| GET | `/{device_id}` | Get device details |
| DELETE | `/{device_id}` | Deactivate a device |
| POST | `/{device_id}/file-path` | Request file path from device |

### MCP Registry (`/api/v1/mcp/registry`)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/list` | List MCPs (paginated, filtered) |
| GET | `/details/{mcp_id}` | Get MCP details |
| GET | `/download/{mcp_id}` | Get download presigned URL (latest) |
| GET | `/download/{mcp_id}/{version}` | Get download presigned URL (specific version) |
| POST | `/install-log` | Log an MCP installation |
| POST | `/register` | Register new MCP (GitHub Actions only) |

### RSLog (`/api/v1/rslog`)
| Method | Path | Description |
|--------|------|-------------|
| POST | `/connect/token` | Authenticate with RSLog |
| POST | `/connect/verify` | Verify 2FA code |
| POST | `/connect/refresh` | Refresh RSLog token |
| GET | `/status` | Get RSLog connection status |
| POST | `/connect/enable` | Enable RSLog connection |
| DELETE | `/disconnect` | Disconnect RSLog |

### Auth (`/api/v1/auth`)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/service-tokens` | Get MCP service tokens |

### Admin (`/api/v1/admin`) — *X-Admin-Token required*
| Method | Path | Description |
|--------|------|-------------|
| GET | `/quota-requests` | List all quota requests |
| POST | `/quota-requests/{id}/approve` | Approve a quota request |
| POST | `/quota-requests/{id}/deny` | Deny a quota request |

### Health (`/api/v1/health`)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Basic health check |
| GET | `/database` | Database connectivity check |
| GET | `/detailed` | Detailed system health |

---

## Authentication & Authorization

### User Auth (Frontend → Backend)
- **Method:** Auth0 JWT tokens via `Authorization: Bearer <token>` header
- **Validation:** Auth0 FastAPI plugin validates JWTs on every protected route
- **User Resolution:** Database-first lookup → Auth0 fallback (creates user if missing)

### Service-to-Service Auth (Backend → AI Core)
- **Production:** Auth0 M2M JWT tokens (Client Credentials Grant), cached with auto-refresh
- **Development:** Static `X-Service-Token` header

### Service Token Auth (External Services → Backend)
- **Desktop app:** `X-Service-Token` header (HMAC constant-time comparison)
- **GitHub Actions:** `X-Service-Token` header
- **Admin panel:** `X-Admin-Token` header

### Authorization Model
- All user resources are scoped to the authenticated user
- Organization-based quota enforcement
- Permission levels: `BASIC`, `FLEXIBLE` (determined by license type)

---

## Core Data Flow: Chat Streaming

This is the most important flow in the system. Here's what happens when a user sends a message:

```
1. Frontend POST /api/v1/chat/sessions/stream/{session_id}
   ├── Body: { input, provider, model, mode, sources, device_id, reasoning_effort }
   │
2. Backend validates:
   ├── Provider + model combination is valid
   ├── Agent mode provider support (Perplexity not supported)
   ├── Organization quota (Ask mode) or Agent quota (Agent mode)
   └── Source channel selections
   │
3. Backend creates DB records:
   ├── UserMessage (status: SUBMITTED)
   └── AIResponse (status: SUBMITTED)
   │
4. Backend calls AI Core:
   └── POST /api/v1/agent/stream (SSE)
       ├── Headers: Authorization or X-Service-Token, X-Client-Type: backend
       └── Body: { input, session_id, mode, model, user_permission, source_channels, ... }
   │
5. Backend processes SSE events from AI Core:
   ├── agent.workflow.started      → Captures trace_id
   ├── agent.message.delta         → Accumulates text, proxies to FE
   ├── agent.tool_execution.*      → Proxies tool status to FE
   ├── response.search_results     → Stores search results
   ├── context.usage               → Updates session token count
   ├── agent.workflow.completed    → Captures usage_breakdown
   └── ... (20+ event types handled)
   │
6. On completion:
   ├── Saves full response text to AIResponse
   ├── Updates status → COMPLETED (or CANCELLED/ERRORED)
   ├── Stores timeline, search results, trace_id, usage_breakdown
   └── Extracts media from search result URLs (async)
```

---

## Supported LLM Providers & Models

| Provider | Models | Agent Mode |
|----------|--------|------------|
| OpenAI | GPT-5, GPT-5.1, GPT-5.2 | Yes |
| Anthropic | Claude Sonnet 4.5, Claude Haiku 4.5, Claude Opus 4.5 | Yes |
| Perplexity | Sonar, Sonar Reasoning | No (Ask only) |
| xAI | Grok 4.1 Fast, Grok 4.1 Fast Reasoning | Yes |

Modes:
- **Ask** — Knowledge-only responses, uses org quota
- **Agent** — Full tool access (search, code execution, device interaction), uses agent quota

---

## Getting Started

### Prerequisites
- Python 3.13+
- [Poetry](https://python-poetry.org/) (dependency management)
- Docker (for local PostgreSQL)

### Setup

```bash
# 1. Install dependencies
pip install poetry    # if not installed
poetry install

# 2. Copy environment template
cp example.env .env
# Edit .env with your configuration (see Environment Variables below)

# 3. Start local PostgreSQL
docker-compose up -d

# 4. Run database migrations
poetry run alembic upgrade head

# 5. Start the dev server
poetry run start
```

The API is available at `http://localhost:8080` with docs at `http://localhost:8080/docs`.

### Generate RSLog Encryption Key

```bash
poetry run python -c "from cryptography.fernet import Fernet; print('RSLOG_ENCRYPTION_KEY=' + Fernet.generate_key().decode())"
```

---

## Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `ENVIRONMENT` | Environment mode | `development` / `production` / `testing` |
| `HOST` | Server host | `0.0.0.0` |
| `PORT` | Server port | `8080` |
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://user:pass@localhost:5432/rsgpt_db` |
| `AUTH0_CLIENT_ID` | Auth0 application client ID | — |
| `AUTH0_CLIENT_SECRET` | Auth0 application client secret | — |
| `AUTH0_DOMAIN` | Auth0 tenant domain | `your-tenant.auth0.com` |
| `AUTH0_AUDIENCE` | Auth0 API audience (this service) | `rsgpt-be-identifier` |
| `AUTH0_AI_CORE_AUDIENCE` | Auth0 audience for AI Core M2M | `rsgpt-ai-core-identifier` |
| `AI_CORE_URL` | AI Core service base URL | `http://localhost:8090` |
| `AI_CORE_SERVICE_TOKEN` | Static token for dev AI Core auth | — |
| `DESKTOP_SERVICE_TOKEN` | Desktop app service auth token | — |
| `GITHUB_ACTIONS_SERVICE_TOKEN` | GitHub Actions auth token | — |
| `ADMIN_API_TOKEN` | Admin endpoint auth token | — |
| `MCP_SERVICE_TOKEN` | MCP service token | — |
| `AWS_REGION` | AWS region | `us-east-2` |
| `MCP_RELEASES_S3_BUCKET` | S3 bucket for MCP releases | `rsinsight-mcp-releases-staging` |
| `DESKTOP_RELEASES_S3_BUCKET` | S3 bucket for desktop releases | `rsinsight-desktop-releases-staging` |
| `USER_LICENSE_API_URL` | RocPortal license API URL | — |
| `USER_ORG_LICENSE_API_TOKEN` | RocPortal API token | — |
| `RSLOG_ENCRYPTION_KEY` | Fernet key for RSLog credential encryption | — |
| `CORS_ORIGINS` | Comma-separated allowed origins | `http://localhost:3000` |
| `LOG_LEVEL` | Logging level | `INFO` |

---

## Database

### Tech Stack
- **PostgreSQL 15** (local via Docker, managed in production)
- **SQLAlchemy** ORM with connection pooling (pool_size=10, max_overflow=20)
- **Alembic** for migrations (30+ migration files)

### Base Model Pattern
All models inherit from `BaseDbModel`:
- **UUID primary keys** — no integer IDs
- **Timestamps** — `created_at`, `updated_at` (auto-managed)
- **Soft deletes** — `deleted_at` field, records are never hard-deleted

### Core Tables
| Table | Purpose |
|-------|---------|
| `users` | User accounts (linked to Auth0 sub) |
| `user_settings` | User preferences (model, theme, etc.) |
| `organizations` | Organizations with quota allocations |
| `user_organizations` | User ↔ Organization mapping |
| `chat_sessions` | Chat sessions per user |
| `user_messages` | User-sent messages |
| `ai_responses` | AI responses with metadata, timeline, usage |
| `message_feedback` | Thumbs up/down feedback |
| `devices` | Desktop app device registrations |
| `mcp_registry` | MCP server registry |
| `mcp_versions` | MCP version history |
| `mcp_install_logs` | MCP installation tracking |
| `quota_requests` | Quota increase requests |
| `rslog_user_settings` | RSLog credentials (encrypted) |
| `system_logs` | System error logging |

### Migration Commands

```bash
# Apply all pending migrations
poetry run alembic upgrade head

# Auto-generate migration from model changes
poetry run alembic revision --autogenerate -m "Add new_column to users"

# Check current migration status
poetry run alembic current

# Rollback last migration
poetry run alembic downgrade -1
```

---

## Scheduled Jobs

The backend runs cron jobs via **APScheduler**:

| Job | Schedule | Description |
|-----|----------|-------------|
| Organization quota reset | Daily at 2:00 AM UTC | Resets shared org quotas |
| Agent quota reset | 1st of each month | Resets per-user agent quotas |

Configured in `app/scheduler.py`, started/stopped during app lifespan.

---

## Testing

```bash
# Run all tests
poetry run pytest

# Run with coverage
poetry run pytest --cov=app --cov-report=html
```

---

## Deployment

### CI/CD
- GitHub Actions workflows in `.github/workflows/`
- `qa.yml` — deploys to QA on push
- `prod.yml` — deploys to production
- `_deploy.yml` — shared deployment logic

### Docker

```bash
# Build
docker build -t rsgpt-be .

# Run (port 8080)
docker run -p 8080:8080 --env-file .env rsgpt-be
```

The Dockerfile uses Python 3.13-slim with Poetry 1.8.3. Health check is on port 8080.

---

## Developer Quick Reference

### Adding a New Endpoint

1. **Create/update DTO** in `app/models/` (request + response schemas)
2. **Add service method** in `app/services/` (business logic)
3. **Add DB query** in `app/db_interface/` if needed
4. **Add DB model** in `app/db_models/` if new table needed
5. **Create route** in `app/api/routes/` (wire up service + auth)
6. **Register route** in `app/api/main.py` if new router
7. **Create migration** if schema changed: `poetry run alembic revision --autogenerate -m "description"`

### Adding a New External Integration

1. **Add config vars** in `app/config.py`
2. **Create client/service** in `app/services/`
3. **Add to `example.env`** for documentation

### Key Files to Understand First

| File | Why |
|------|-----|
| `app/main.py` | App initialization, middleware, lifespan |
| `app/config.py` | All environment variables and defaults |
| `app/dependencies.py` | How auth and services are injected into routes |
| `app/services/chat_service.py` | The core feature — chat streaming orchestration |
| `app/services/ai_core_client.py` | How we talk to AI Core |
| `app/services/user_service.py` | User/org management and quota calculation |
| `app/models/enums.py` | All enums (providers, models, statuses) |

---

**Project Status**: Active Development
**Last Updated**: February 2026
**Team**: RSInsight Development Team
