# System Design

**Navigation**: [Documentation Home](../INDEX.md) > [Architecture](./INDEX.md) > System Design

**Architecture**: Local client-server monorepo with cloud integration

**Key Decision**: Local-first for data control, cloud for LLMs/integrations, monorepo for file system access

## System Diagram

```
┌─────────────────────────────────────────┐
│  Frontend (React + TS)                   │
│  • Tab System & Views                    │
│  • Conversation UI                       │
│  • Document Editors & Diff Viewers       │
│  WebSocket ↕  HTTP ↕  LocalStorage       │
└─────────────────────────────────────────┘
              ↕
┌─────────────────────────────────────────┐
│  Backend (FastAPI + Python)              │
│  • API Routers                           │
│  • Services Layer                        │
│  • AI Agents (PydanticAI)                │
│  • Repositories (SQLAlchemy)             │
│  • Context Providers                     │
│  • Integrations (GitHub/Jira/Slack)      │
│           ↕                              │
│  SQLite/PostgreSQL                       │
└─────────────────────────────────────────┘
              ↕
┌─────────────────────────────────────────┐
│  External Services                       │
│  • LLMs (OpenAI/Anthropic/Google)        │
│  • GitHub/Jira/Slack APIs                │
│  • Local Repos (Git)                     │
│  • Claude Code CLI / Gemini CLI          │
└─────────────────────────────────────────┘
```

## Tech Stack

**Backend**:
- FastAPI async with Python 3.12+, WebSocket support
- SQLite (PostgreSQL migration path), SQLAlchemy 2.0 with `Mapped[]`
- PydanticAI (multi-provider LLM, streaming, tool approval)
- Pydantic Logfire (observability, tracing)

**Frontend**:
- React 19+ with TypeScript, Vite build
- Zustand + Immer (normalized Map caching, LocalStorage)
- Tailwind CSS (dark/light mode, responsive)
- WebSocket singleton (NDJSON streaming, auto-reconnect)

## Core Principles

**Local-First**: Data on user's machine, SQLite local, fast access, offline core

**Context-Aware**: Multi-source integration (GitHub/Jira/Slack/files), URI-based linking, smart loading (eager/on-demand)

**Agent-Driven**: Role-based agents, tool approval workflows, event-based conversations, streaming

**Extensible**: Pluggable providers, external integrations, LLM provider abstraction

**State-Driven**: Explicit task state transitions, state-appropriate roles, guided workflows

## Deployment

**Development**: Docker Compose (backend + frontend + DB + volumes + env)

**Production**: Docker containers, multi-stage builds, volume mounting for local access, health checks

## Communication Patterns

**HTTP REST**: Resource-based URLs (`/api/{projects|tasks}`), standard methods, Pydantic schemas

**WebSocket**: NDJSON protocol, incremental events, multiple connections, auto-reconnect

**Event-Based**: ConversationEvent discriminated union, multiple types (messages, tool calls/results/requests), chronological

## Security

**Local-First**: Data on machine, API keys in env/encrypted, no cloud sync required

**API Integration**: Secure credentials, token auth, rate limiting, graceful degradation

## Performance

**Response**: 2-5s for simple queries, streaming for immediate feedback, local DB <50ms, parallel context assembly

**Scalability**: Multiple concurrent conversations, normalized caching, WebSocket pooling (max 10), local deployment optimized

**Resources**: Efficient memory, SQLite for single-user (PostgreSQL for multi-user), context caching with TTL

## Data Flow

**User Request**:
1. Frontend → HTTP/WebSocket
2. Backend validates + retrieves context
3. Agent executes with context
4. Events stream incrementally
5. Frontend updates real-time
6. Persist to database

**Context Assembly**:
1. Identify sources (project resources, task links)
2. Categorize by strategy (eager/on-demand)
3. Parallel fetch eager
4. Assemble package
5. Cache with TTL
6. Provide on-demand references

## See Also

[Vision and Goals](../1-overview/vision-and-goals.md) | [Database Schema](./database-schema.md) | [API Design](./api-design.md) | [Backend INDEX](./backend/INDEX.md) | [Frontend INDEX](./frontend/INDEX.md) | [Getting Started](../6-development/getting-started.md)
