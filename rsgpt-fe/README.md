# RSGPT Frontend (`rsgpt-fe`)

## What Is This?

`rsgpt-fe` is a **Next.js 15 application** that serves as the **user interface** for RSInsight — a chat-based AI assistant for Rocscience products. It handles authentication, renders the chat interface, streams AI responses in real-time, manages user settings, and communicates with the backend (`rsgpt-be`) through a proxy layer.

**In one sentence:** rsgpt-fe is the web app users interact with — it authenticates them via Auth0, provides the chat UI, streams AI responses via SSE, and proxies all API calls through Next.js API routes to the backend.

The frontend **never** talks to `rsgpt-ai-core` directly. All requests go through `rsgpt-be`.

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         rsgpt-fe (Vercel)                       │
│                                                                 │
│  ┌──────────────┐   ┌──────────────────┐   ┌────────────────┐  │
│  │ React UI     │   │ Next.js API      │   │ Middleware      │  │
│  │ (Client)     │──►│ Routes (Proxy)   │──►│ (Auth + Access) │  │
│  │              │   │ Adds Auth token  │   │                 │  │
│  └──────┬───────┘   └────────┬─────────┘   └────────────────┘  │
│         │                    │                                   │
│         │  SSE (direct)      │  HTTP (proxied)                  │
└─────────┼────────────────────┼──────────────────────────────────┘
          │                    │
          │                    ▼
          │            ┌───────────────┐
          └───────────►│   rsgpt-be    │
                       │   (Backend)   │
                       └───────────────┘
```

### How FE Talks to BE

| Pattern | Description |
|---------|-------------|
| **Proxied requests** | React calls `/api/v1/*` → Next.js API route adds Auth0 token → proxies to `rsgpt-be` |
| **Direct streaming** | For chat, FE first gets a stream URL + token from the proxy, then connects directly to BE for SSE (bypasses Vercel's streaming limits) |
| **Auth flow** | Auth0 handles login/logout. Middleware checks session + RocPortal access on every navigation. |

---

## Key Responsibilities

### 1. Chat Interface (Core Feature)
- Real-time AI response streaming via SSE
- Markdown rendering with math (KaTeX), tables, and code blocks
- Agent mode with tool execution indicators, workflow status, thinking display
- Source selection (knowledge channels + web search)
- Model selection (OpenAI, Anthropic, xAI, Perplexity)
- Message feedback (thumbs up/down)
- Conversation history with infinite scroll
- Context usage tracking display

### 2. Authentication & Access Control
- Auth0 login/logout with session management
- RocPortal license validation (middleware checks on every navigation)
- Automatic token refresh
- Session expiry detection and cleanup

### 3. Session Management
- Create, list, and delete chat sessions
- Sidebar navigation between sessions
- Infinite scroll session list

### 4. User Settings
- Model preference, theme (light/dark/system), data consent
- Device management (view connected desktop devices)
- Quota information and quota increase requests

### 5. Device Integration
- View connected desktop devices
- File path selection from device (native OS file dialog)
- Device connection status alerts

### 6. RSLog Integration
- RSLog connection modal (username/password + 2FA)
- Connection status management
- Token refresh

### 7. Error Handling & Resilience
- Circuit breaker pattern on API calls (opens after 5 failures, 30s cooldown)
- Retry with exponential backoff (GET requests)
- Offline detection with action queueing
- Service health monitoring
- Global alert system

---

## Project Structure

```
rsgpt-fe/
├── src/
│   ├── app/                              # Next.js App Router
│   │   ├── layout.tsx                    # Root layout (providers, global alerts)
│   │   ├── page.tsx                      # Landing page (Dashboard)
│   │   ├── providers.tsx                 # All React context providers
│   │   ├── globals.css                   # Global styles + theme variables
│   │   ├── hero.ts                       # HeroUI custom theme config
│   │   │
│   │   ├── chat/
│   │   │   ├── layout.tsx                # Chat layout (sidebar + content)
│   │   │   ├── page.tsx                  # New chat page (creates session)
│   │   │   └── [sessionId]/
│   │   │       └── page.tsx              # Active chat session page
│   │   │
│   │   ├── maintenance/
│   │   │   └── page.tsx                  # Maintenance mode page
│   │   │
│   │   └── api/v1/                       # Next.js API routes (proxy layer)
│   │       ├── avatar/route.ts           # Avatar image proxy
│   │       ├── health/route.ts           # Health check proxy
│   │       ├── chat/sessions/
│   │       │   ├── route.ts              # List/create sessions
│   │       │   ├── [sessionId]/route.ts  # Delete session
│   │       │   ├── conversation/[sessionId]/route.ts  # Conversation history
│   │       │   ├── stream/[sessionId]/route.ts        # Stream setup (returns URL+token)
│   │       │   └── feedback/[messageId]/route.ts      # Message feedback
│   │       ├── user/
│   │       │   ├── settings/route.ts     # User settings GET/PUT
│   │       │   ├── quota-info/route.ts   # Quota info
│   │       │   ├── quota-request/route.ts # Quota request
│   │       │   └── rocportal-status/route.ts # RocPortal status
│   │       ├── devices/route.ts          # Device list
│   │       ├── device/[deviceId]/file-path/route.ts  # Device file path
│   │       ├── desktop/presigned-url/route.ts # Desktop installer URL
│   │       └── rslog/                    # RSLog endpoints
│   │           ├── status/route.ts
│   │           ├── connect/token/route.ts
│   │           ├── connect/verify/route.ts
│   │           ├── connect/enable/route.ts
│   │           ├── connect/refresh/route.ts
│   │           └── disconnect/route.ts
│   │
│   ├── components/
│   │   ├── alerts/                       # Alert/notification components
│   │   │   ├── alerts.tsx                # Session/streaming/network error alerts
│   │   │   ├── device-connection-alert.tsx
│   │   │   ├── device-timeout-alert.tsx
│   │   │   ├── global-alert-container.tsx
│   │   │   ├── offline-alert.tsx
│   │   │   └── service-status-banner.tsx
│   │   │
│   │   ├── auth/                         # Authentication components
│   │   │   ├── auth-buttons.tsx          # Login/logout buttons
│   │   │   ├── auth-checker.tsx          # Auth state checker
│   │   │   └── logout-handler.tsx        # Cleanup on logout (clears stores)
│   │   │
│   │   ├── chat/                         # Chat interface (main feature)
│   │   │   ├── display/                  # Visual components
│   │   │   │   ├── animated-streaming-text.tsx   # Streaming text animation
│   │   │   │   ├── markdown-hero-table.tsx       # Markdown table renderer
│   │   │   │   ├── plan-display.tsx              # Agent plan display
│   │   │   │   ├── response-info.tsx             # Response metadata
│   │   │   │   ├── thinking-indicator.tsx        # Agent thinking indicator
│   │   │   │   ├── tool-execution-indicator.tsx  # Tool execution status
│   │   │   │   └── workflow-status-bar.tsx       # Workflow progress bar
│   │   │   ├── feedback/
│   │   │   │   └── user-feedback-buttons.tsx     # Thumbs up/down
│   │   │   ├── input/
│   │   │   │   ├── message-input.tsx             # Main message input
│   │   │   │   ├── agent-quota-exceeded-banner.tsx
│   │   │   │   └── message-input-components/
│   │   │   │       ├── chip-textarea.tsx         # Input textarea
│   │   │   │       ├── context-usage-display.tsx # Token usage display
│   │   │   │       ├── file-path-selector.tsx    # Device file selector
│   │   │   │       ├── message-input-controls.tsx
│   │   │   │       ├── message-input-options.tsx # Agent mode, web search toggles
│   │   │   │       ├── model-selector.tsx        # Model dropdown
│   │   │   │       ├── source-logos.tsx
│   │   │   │       └── source-selector.tsx       # Knowledge source picker
│   │   │   ├── messages/
│   │   │   │   ├── ai-message.tsx                # AI response rendering
│   │   │   │   ├── message-list.tsx              # Conversation list (infinite scroll)
│   │   │   │   └── user-message.tsx              # User message rendering
│   │   │   ├── navigation/
│   │   │   │   └── navigation-overlay.tsx
│   │   │   └── sources/
│   │   │       ├── responsive-source-list.tsx
│   │   │       ├── source-carousel.tsx
│   │   │       └── source-list.tsx
│   │   │
│   │   ├── dashboard/                    # Landing page components
│   │   │   ├── dashboard.tsx
│   │   │   ├── header.tsx
│   │   │   ├── prompt-animation.tsx
│   │   │   └── rsinsight-logo.tsx
│   │   │
│   │   ├── side-bar/                     # Sidebar navigation
│   │   │   ├── side-bar-client.tsx       # Main sidebar component
│   │   │   ├── sidebar-header.tsx
│   │   │   ├── sidebar-mobile.tsx
│   │   │   ├── responsive-sidebar-wrapper.tsx
│   │   │   ├── session-list.tsx          # Session list (infinite scroll)
│   │   │   ├── session-list-item.tsx
│   │   │   ├── new-chat-button.tsx
│   │   │   ├── delete-session-modal.tsx
│   │   │   ├── rsinsight-desktop-button.tsx
│   │   │   ├── user-profile.tsx
│   │   │   └── settings/                 # Settings modal
│   │   │       ├── settings-modal.tsx
│   │   │       ├── global-settings-modal.tsx
│   │   │       ├── account-settings.tsx
│   │   │       ├── device-info.tsx
│   │   │       ├── theme-switcher.tsx
│   │   │       ├── data-consent.tsx
│   │   │       └── quota-request-modal.tsx
│   │   │
│   │   ├── rslog/
│   │   │   └── rslog-connection-modal.tsx
│   │   ├── sentry/
│   │   │   ├── sentry-feedback-widget.tsx
│   │   │   └── sentry-user-setter.tsx
│   │   ├── banners/
│   │   │   └── agent-mode-banner.tsx
│   │   ├── icons/
│   │   │   └── rslog-icon.tsx
│   │   └── ui/
│   │       ├── loading.tsx
│   │       └── theme-initializer.tsx
│   │
│   ├── hooks/                            # Custom React hooks
│   │   ├── useStreamPrompt.ts            # SSE streaming (the big one)
│   │   ├── useChatMessages.ts            # Chat state (Zustand store)
│   │   ├── useSessions.ts               # Session list (React Query)
│   │   ├── useCreateSession.ts           # Create session (mutation)
│   │   ├── useDeleteSession.ts           # Delete session (mutation)
│   │   ├── useGetChatSessionHistory.ts   # Conversation history (infinite query)
│   │   ├── useMessageFeedback.ts         # Feedback submission
│   │   ├── useModelSelection.ts          # Model state (Zustand)
│   │   ├── useSourceList.ts              # Source state (Zustand)
│   │   ├── useAgentMode.ts              # Agent mode state (Zustand)
│   │   ├── useDeviceSelection.ts         # Device state (Zustand)
│   │   ├── useContextUsage.ts            # Token usage state (Zustand)
│   │   ├── useGetUserSettings.ts         # User settings (React Query)
│   │   ├── useUpdateUserSettings.ts      # Update settings (mutation)
│   │   ├── useGetQuotaInfo.ts            # Quota info (React Query)
│   │   ├── useRequestQuota.ts            # Quota request (mutation)
│   │   ├── useGetDeviceInfo.ts           # Device list (React Query)
│   │   ├── useRSLogConnection.ts         # RSLog hooks (6 hooks)
│   │   ├── useUpdateRocPortalStatus.ts   # RocPortal status (mutation)
│   │   ├── useMessageInputState.ts       # Input state (Zustand)
│   │   ├── useMessageInputStatus.ts      # Input status logic
│   │   ├── useMessageInputUI.ts          # Input UI logic
│   │   ├── useMessageInputAutoSend.ts    # Auto-send on navigation
│   │   ├── usePendingFirstMessage.ts     # Pending message state (Zustand)
│   │   ├── useNetworkStatus.ts           # Network state (Zustand)
│   │   ├── useGlobalAlerts.ts            # Alert state (Zustand)
│   │   ├── useNavigationState.ts         # Navigation state (Zustand)
│   │   └── useTimelineProcessor.ts       # Timeline rendering logic
│   │
│   ├── contexts/                         # React context providers
│   │   ├── CitationHighlightContext.tsx   # Citation URL highlighting
│   │   └── SettingsModalContext.tsx       # Settings modal open/close
│   │
│   ├── lib/                              # Utility libraries
│   │   ├── api.ts                        # API client (circuit breaker, retry, offline)
│   │   ├── auth0.ts                      # Auth0 client configuration
│   │   ├── avatar.ts                     # Avatar URL proxy helper
│   │   ├── consts.ts                     # Constants (API_PREFIX, sample prompts)
│   │   ├── fonts.ts                      # Font configuration (Inter)
│   │   ├── store-utils.ts               # Zustand store cleanup on logout
│   │   └── types.ts                      # All TypeScript types
│   │
│   ├── middleware.ts                     # Auth + RocPortal access checks
│   └── instrumentation.ts               # Sentry initialization
│
├── tests/                                # Test suite (Jest + React Testing Library)
│   ├── components/                       # Component tests (19 files)
│   ├── hooks/                            # Hook tests (7 files)
│   ├── lib/                              # Utility tests (3 files)
│   └── pages/                            # Integration tests (3 files)
│
├── public/                               # Static assets (logos, icons)
├── next.config.ts                        # Next.js + Sentry config
├── tailwind.config.ts                    # Tailwind CSS + HeroUI theme
├── tsconfig.json                         # TypeScript config
├── jest.config.js                        # Jest config
├── eslint.config.mjs                     # ESLint config
├── example.env                           # Environment variable template
└── package.json                          # Dependencies and scripts
```

---

## State Management

The app uses three layers of state:

### 1. Zustand Stores (Client State)

| Store | File | Purpose |
|-------|------|---------|
| `useChatMessages` | `hooks/useChatMessages.ts` | Conversation turns, streaming text, tool executions, workflow state, timeline events — per session |
| `useMessageInputState` | `hooks/useMessageInputState.ts` | Input position, disabled state, submit handler |
| `useModelSelection` | `hooks/useModelSelection.ts` | Selected model + reasoning level |
| `useSourceList` | `hooks/useSourceList.ts` | Selected knowledge sources, search results |
| `useAgentMode` | `hooks/useAgentMode.ts` | Agent mode toggle, web search toggle |
| `useDeviceSelection` | `hooks/useDeviceSelection.ts` | Selected device ID |
| `useContextUsage` | `hooks/useContextUsage.ts` | Token usage per session |
| `usePendingFirstMessage` | `hooks/usePendingFirstMessage.ts` | Message queued before session creation |
| `useNetworkStatus` | `hooks/useNetworkStatus.ts` | Online/offline, action retry queue |
| `useGlobalAlerts` | `hooks/useGlobalAlerts.ts` | Error/warning alerts with auto-dismiss |
| `useNavigationState` | `hooks/useNavigationState.ts` | Navigation transition tracking |

All stores are cleared on logout via `clearAllStores()` in `lib/store-utils.ts`.

### 2. React Query (Server State)

| Hook | Type | Endpoint | Description |
|------|------|----------|-------------|
| `useSessions` | Infinite Query | `GET /chat/sessions` | Paginated session list |
| `useGetChatSessionHistory` | Infinite Query | `GET /chat/sessions/conversation/{id}` | Paginated conversation |
| `useGetUserSettings` | Query | `GET /user/settings` | User preferences |
| `useGetQuotaInfo` | Query | `GET /user/quota-info` | Quota information |
| `useGetDeviceInfo` | Query | `GET /devices` | Connected devices |
| `useCreateSession` | Mutation | `POST /chat/sessions` | Create session |
| `useDeleteSession` | Mutation | `DELETE /chat/sessions/{id}` | Delete session |
| `useUpdateUserSettings` | Mutation | `PUT /user/settings` | Update settings |
| `useMessageFeedback` | Mutation | `POST /chat/sessions/feedback/{id}` | Submit feedback |
| `useRequestQuota` | Mutation | `POST /user/quota-request` | Request quota |
| `useUpdateRocPortalStatus` | Mutation | `PUT /user/rocportal-status` | Refresh access |

Default config: 5-minute stale time, 1 retry, Sentry error integration.

### 3. React Context (Component State)

| Context | Purpose |
|---------|---------|
| `SettingsModalContext` | Open/close settings modal, target tab |
| `CitationHighlightContext` | Highlighted citation URL for visual feedback |

---

## Core Data Flow: Chat Streaming

This is the most important flow in the frontend:

```
1. User types message and hits send
   │
2. useStreamPrompt.sendMessage() called
   ├── Creates optimistic user message in useChatMessages store
   ├── Creates streaming AI turn (empty, status: streaming)
   │
3. POST /api/v1/chat/sessions/stream/{sessionId}
   ├── Next.js API route adds Auth0 token
   ├── Proxies to rsgpt-be
   ├── Returns: { streamUrl, token }     ← direct backend URL
   │
4. Direct fetch to streamUrl (bypasses Vercel)
   ├── Headers: Authorization: Bearer {token}
   ├── Body: { input, provider, model, mode, sources, device_id, ... }
   ├── Response: SSE event stream
   │
5. SSE events parsed in real-time:
   │
   ├── agent.workflow.started        → Set workflow state
   ├── agent.workflow.status_changed → Update status bar
   ├── agent.thinking                → Show thinking indicator
   ├── agent.tool_execution.started  → Show tool indicator
   ├── agent.tool_execution.completed → Update tool result
   ├── agent.message.delta           → Append text to streaming turn
   ├── response.search_results       → Add sources to source list
   ├── context.usage                 → Update token usage display
   ├── agent.heartbeat               → Keep connection alive
   ├── agent.workflow.completed      → Mark complete
   │
6. On completion:
   ├── Streaming turn finalized
   ├── useChatMessages updated with final state
   ├── Session list refreshed (React Query invalidation)
   └── Source list populated with search results
```

### Why Direct Streaming?

Vercel has streaming response limits. To avoid them, the frontend:
1. Makes a regular POST to the Next.js API route to get a `streamUrl` and `token`
2. Connects directly to the AWS-hosted backend for the SSE stream
3. This bypasses Vercel entirely for the streaming portion

---

## SSE Event Types Handled

The `useStreamPrompt` hook processes these events from the backend:

### Chat Events
| Event | Action |
|-------|--------|
| `response.created` | Initialize response state |
| `response.output_text.delta` | Append text to streaming message |
| `response.completed` | Mark response complete |
| `response.failed` | Show error state |
| `response.search_results` | Populate source list |

### Agent Workflow Events
| Event | Action |
|-------|--------|
| `agent.workflow.started` | Set workflow active |
| `agent.workflow.status_changed` | Update workflow status bar |
| `agent.workflow.completed` | Mark workflow complete |
| `agent.workflow.failed` | Show workflow error |
| `agent.thinking` | Show thinking indicator with content |
| `agent.message.delta` | Append agent text output |
| `agent.planning` | Show plan display |
| `agent.task_progress` | Update task progress |
| `agent.out_of_scope` | Show out-of-scope message |

### Tool Execution Events
| Event | Action |
|-------|--------|
| `agent.tool_execution.started` | Show tool execution indicator |
| `agent.tool_execution.completed` | Update tool with results |
| `agent.tool_execution.failed` | Show tool error |

### Context Events
| Event | Action |
|-------|--------|
| `context.usage` | Update context usage display |
| `context.summarizing` | Show summarization indicator |
| `context.pruning_completed` | Hide summarization indicator |
| `context.pruning_error` | Show summarization error |

### Stream Events
| Event | Action |
|-------|--------|
| `stream.error` | Handle stream error |
| `agent.heartbeat` | No-op (keepalive) |

---

## Authentication Flow

```
1. User visits any page
   │
2. Middleware (src/middleware.ts) intercepts
   ├── Maintenance check → /maintenance if enabled
   ├── Auth0 middleware processes request
   │
3. Protected routes (anything except / and /auth)
   ├── No session? → Redirect to /
   ├── Expired session? → Redirect to /auth/logout
   ├── Has session → Check RocPortal access
   │   ├── No access → Redirect to /
   │   └── Has access → Allow through
   │
4. API calls
   ├── React calls apiFetch("/api/v1/...") → uses cookies (credentials: include)
   ├── Next.js API route calls getAccessToken() → auto-refreshes if expired
   ├── Adds Authorization: Bearer {token} header
   ├── Proxies to rsgpt-be
   │
5. Session expiry handling
   ├── 401 from any API call → dispatches "session-expired" event
   ├── LogoutHandler listens → calls /auth/logout
   └── clearAllStores() cleans up all Zustand state
```

### Session Configuration
- **Absolute duration:** 21 days
- **Inactivity timeout:** 14 days
- **Rolling sessions:** Enabled (extends on activity)
- **Scopes:** `openid profile email offline_access`

---

## API Proxy Layer

Every Next.js API route follows the same pattern:

```typescript
// src/app/api/v1/[resource]/route.ts
export async function GET() {
  const token = await getAccessToken();
  const res = await fetch(`${API_BASE_URL}/api/v1/[resource]`, {
    headers: { Authorization: `Bearer ${token}` }
  });
  return Response.json(await res.json(), { status: res.status });
}
```

### Proxy Routes Summary

| Frontend Route | Backend Route | Methods |
|----------------|---------------|---------|
| `/api/v1/chat/sessions` | `/api/v1/chat/sessions` | GET, POST |
| `/api/v1/chat/sessions/[id]` | `/api/v1/chat/sessions/{id}` | DELETE |
| `/api/v1/chat/sessions/conversation/[id]` | `/api/v1/chat/sessions/conversation/{id}` | GET |
| `/api/v1/chat/sessions/stream/[id]` | Returns `{streamUrl, token}` | POST |
| `/api/v1/chat/sessions/feedback/[id]` | `/api/v1/chat/sessions/feedback/{id}` | POST |
| `/api/v1/user/settings` | `/api/v1/user/settings` | GET, PUT |
| `/api/v1/user/quota-info` | `/api/v1/user/quota-info` | GET |
| `/api/v1/user/quota-request` | `/api/v1/user/quota-request` | POST |
| `/api/v1/user/rocportal-status` | `/api/v1/user/rocportal-status` | PUT |
| `/api/v1/devices` | `/api/v1/device/?include_inactive=true` | GET |
| `/api/v1/device/[id]/file-path` | `/api/v1/device/{id}/file-path` | POST |
| `/api/v1/desktop/presigned-url` | `/api/v1/desktop/get-presigned-url` | GET |
| `/api/v1/rslog/status` | `/api/v1/rslog/status` | GET |
| `/api/v1/rslog/connect/token` | `/api/v1/rslog/connect/token` | POST |
| `/api/v1/rslog/connect/verify` | `/api/v1/rslog/connect/verify` | POST |
| `/api/v1/rslog/connect/enable` | `/api/v1/rslog/connect/enable` | POST |
| `/api/v1/rslog/connect/refresh` | `/api/v1/rslog/connect/refresh` | POST |
| `/api/v1/rslog/disconnect` | `/api/v1/rslog/disconnect` | DELETE |
| `/api/v1/health` | `/health` | GET |

---

## UI Stack

| Library | Purpose |
|---------|---------|
| **HeroUI** (`@heroui/react`) | Primary component library (buttons, modals, dropdowns, etc.) |
| **Tailwind CSS** v4 | Utility-first styling |
| **next-themes** | Dark/light/system theme switching |
| **Framer Motion** | Animations |
| **React Markdown** | Markdown rendering in chat messages |
| **KaTeX** | Math equation rendering (via `remark-math` + `rehype-katex`) |
| **remark-gfm** | GitHub Flavored Markdown (tables, strikethrough, etc.) |
| **Heroicons** | Icon set |

### Theme
- Primary color: `#E35205` (Rocscience orange)
- Dark mode via `class` strategy
- Custom HeroUI theme with light/dark color scales
- Custom CSS variables for chat layout positioning

---

## Providers Stack

The root layout wraps the app in these providers (see `src/app/providers.tsx`):

```
Auth0Provider
  └── HeroUIProvider
        └── ThemeProvider (next-themes)
              └── QueryClientProvider (React Query)
                    └── Analytics (Vercel)
                          └── ThemeInitializer
                          └── LogoutHandler
                          └── SentryUserSetter
                          └── SentryFeedbackWidget
                          └── GlobalAlertContainer
                          └── {children}
```

---

## Getting Started

### Prerequisites
- Node.js 18+
- npm

### Setup

```bash
# 1. Install dependencies
npm install

# 2. Copy environment template
cp example.env .env
# Edit .env with Auth0 credentials and backend URL

# 3. Start dev server (Turbopack)
npm run dev
```

The app is available at `http://localhost:3000`.

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `AUTH0_DOMAIN` | Yes | Auth0 tenant domain |
| `AUTH0_CLIENT_ID` | Yes | Auth0 client ID |
| `AUTH0_CLIENT_SECRET` | Yes | Auth0 client secret |
| `AUTH0_SECRET` | Yes | Auth0 session encryption secret |
| `AUTH0_BASE_URL` | Yes | Auth0 base URL (e.g., `http://localhost:3000`) |
| `AUTH0_AUDIENCE` | Yes | Auth0 API audience |
| `API_BASE_URL` | Yes | Backend API URL (e.g., `http://localhost:8080`) |
| `APP_BASE_URL` | No | Frontend URL (auto-uses `VERCEL_URL` for previews) |
| `SENTRY_AUTH_TOKEN` | No | Sentry source map upload token |
| `NEXT_PUBLIC_MAINTENANCE` | No | Set to `"1"` to enable maintenance mode |

---

## Testing

```bash
# Run all tests
npm run test

# Watch mode
npm run test:watch

# Coverage report
npm run test:coverage

# Unit tests only (components, hooks, lib)
npm run test:unit

# Integration tests only (pages)
npm run test:integration
```

**Stack:** Jest + React Testing Library + jsdom

Test structure mirrors `src/`:
- `tests/components/` — 19 component test files
- `tests/hooks/` — 7 hook test files
- `tests/lib/` — 3 utility test files
- `tests/pages/` — 3 page integration tests

---

## CI/CD

### GitHub Actions (`.github/workflows/pull_request.yml`)
- Runs on PR to `main`
- Steps: checkout → Node.js 24 setup → `npm install` → `npm run test` → `npm run build`

### Husky Pre-commit Hook
- Runs `npm run lint` before every commit

### Deployment
- Deployed to **Vercel** (no Dockerfile)
- Sentry source maps uploaded on build
- Vercel Analytics enabled

---

## Developer Quick Reference

### Adding a New Page

1. Create `src/app/[route]/page.tsx`
2. Add any needed layout in `src/app/[route]/layout.tsx`
3. Page is automatically protected by middleware (requires auth + RocPortal access)

### Adding a New API Call

1. **Add backend proxy route** in `src/app/api/v1/[path]/route.ts` — follow existing pattern
2. **Add TypeScript types** in `src/lib/types.ts` (request + response)
3. **Create React hook** in `src/hooks/` — use React Query (`useQuery` / `useMutation`)
4. **Call the hook** from your component

### Adding a New Zustand Store

1. Create hook in `src/hooks/use[Name].ts`
2. Register cleanup in `src/lib/store-utils.ts` → `clearAllStores()`

### Key Files to Understand First

| File | Why |
|------|-----|
| `src/hooks/useStreamPrompt.ts` | The core feature — how SSE streaming works |
| `src/hooks/useChatMessages.ts` | Chat state management (Zustand) |
| `src/lib/api.ts` | API client with circuit breaker and retry |
| `src/lib/auth0.ts` | Auth0 configuration and token management |
| `src/lib/types.ts` | All TypeScript types for API contracts |
| `src/middleware.ts` | Auth + RocPortal access enforcement |
| `src/app/providers.tsx` | Provider stack (Auth0, HeroUI, theme, React Query) |
| `src/app/chat/[sessionId]/page.tsx` | Main chat session page |
| `src/components/chat/input/message-input.tsx` | Message input component |
| `src/components/chat/messages/ai-message.tsx` | AI response rendering |

---

## Monitoring

- **Sentry** — Error tracking (client, server, edge), replay (10% sessions, 100% on error), feedback widget
- **Vercel Analytics** — Performance and usage analytics

---

**Project Status**: Active Development
**Last Updated**: February 2026
**Team**: RSInsight Development Team
