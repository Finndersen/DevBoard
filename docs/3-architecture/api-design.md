# API Design

**Navigation**: [Documentation Home](../INDEX.md) > [Architecture](./INDEX.md) > API Design

## Overview

RESTful API with FastAPI. Focus on architectural decisions.

## Core Architectural Decisions

### Event-Based Conversation Architecture

**Decision**: All conversation endpoints return `list[ConversationEvent]` instead of single text responses.

**Rationale**: Unified handling of messages, tool calls, tool results, and approval requests. Frontend renders event timeline chronologically.

**Implementation**: Backend converts PydanticAI messages to ConversationEvents, stores in database, returns/streams to frontend.

### Background Task + WebSocket Architecture

**Decision**: Agent execution is decoupled from HTTP request lifecycle. HTTP endpoints start background asyncio tasks and return `{"conversation_id": N}` immediately. Clients consume events via WebSocket.

**Rationale**: Enables reconnection resilience (clients can disconnect/reconnect without losing events) and graceful interruption (HTTP POST `/interrupt` → agent stops cleanly).

**Key endpoints**:
- `POST /conversations/{id}/messages` — starts background execution, returns immediately
- `POST /conversations/{id}/approve-tools` — resumes execution with tool approval
- `GET /conversations/{id}/ws` — WebSocket for consuming events (server→client only)
- `POST /conversations/{id}/interrupt` — request graceful interruption
- `POST /tasks/{id}/workflow-action` — runs procedural steps, optionally starts agent execution. Returns `{"conversation_id": N}` if agent started, `{"status": "completed"}` otherwise. Returns 400 if action validation fails.

**409 Conflict**: Returns 409 if an execution is already active for a conversation. At most one active execution per conversation at any time.

**In-memory queue**: Each execution has an `asyncio.Queue`. Events are consumed by the WebSocket connection. Queue is cleaned up ~60s after execution completes to allow reconnection.

### Polymorphic Conversation System

**Decision**: Single unified `/api/conversations/{id}/...` endpoints for all entity types (projects, tasks, codebases).

**Rationale**: Avoid duplication of conversation endpoints per entity. Single conversation model with `entity_type`/`entity_id` polymorphism.

**Benefits**: Consistent frontend handling, shared event history, simplified routing.

### Tool Approval Workflow

**Decision**: Two-phase execution with explicit approval endpoint.

**Rationale**: Agent pauses when tool requires approval, returns `ToolCallRequest` events. Frontend displays approval UI, calls `/approve-tools` to resume.

**Pattern**: Agent checks `tool.requires_approval`, yields approval request if true, waits for approval response before continuing.

### Document Conflict Detection

**Decision**: Content hashing for optimistic locking on document updates.

**Rationale**: Multiple users/agents editing same document need conflict detection. Hash prevents overwriting unseen changes.

**Implementation**: GET returns `content_hash`, PUT requires `original_hash`, returns 409 if mismatch.

**Endpoints**: `/codebases/{id}/architecture_document`, `/projects/{id}/specification`, `/tasks/{id}/specification`, `/tasks/{id}/implementation_plan`

### Three-Layer Configuration System

**Decision**: Environment variables override database values, which override code defaults.

**Rationale**: Deploy-time configuration (env vars), runtime configuration (database), sensible defaults (code).

**Pattern**: ConfigService checks sources in precedence order. `/configurations/{key}/detail` shows source per field.

### URI-Based Resource System

**Decision**: Resources identified by URI scheme (e.g., `github://owner/repo/pulls/123`, `jira://project/TICKET-456`).

**Rationale**: Flexible external resource linking. Context providers route by URI scheme, transform to normalized text.

**Pattern**: `ContextProviderRegistry` routes URIs to providers. Providers use integrations for API calls.

### State-Driven Task Agents

**Decision**: Different agent configurations per task state (DEFINING → specification agent, PLANNING → planning agent).

**Rationale**: Different tools/prompts needed at each lifecycle stage. Task state determines active agent.

**Implementation**: Frontend selects agent based on task state. Backend loads state-appropriate agent configuration.

## Endpoint Organization

See [Backend API Reference](./backend/api-reference.md) for complete endpoint list.

**Key Patterns**:
- Resource-based URLs: `/api/{resource}`, `/api/{resource}/{id}`, `/api/{resource}/{id}/{sub}`
- Standard HTTP methods: GET, POST, PATCH, DELETE
- Nested resources for relationships: `/api/projects/{id}/tasks`

## Request/Response Patterns

### Standard CRUD

**Pattern**: POST creates, GET reads, PATCH updates, DELETE removes. Pydantic schemas for validation.

### Event-Based Responses

**Pattern**: GET conversation history returns `list[ConversationEvent]` with chronological events.

**Real-time streaming**: POST endpoints start background execution and return immediately. Events stream via WebSocket (`GET /conversations/{id}/ws`). See [Frontend Streaming Architecture](../frontend/streaming.md) for details.

### Error Responses

**Status Codes**: 400 (bad request), 404 (not found), 409 (conflict), 500 (server error)

**Structured Format**: Consistent error response with `detail`, `error_type`, additional context

## Schema Patterns

### Discriminated Unions

**ConversationEvent**: Base with `event_type` discriminator. Subtypes: `ConversationMessage`, `ToolCall`, `ToolResult`, `ToolCallRequest`

**Pattern**: Type-safe deserialization with automatic type resolution based on discriminator field.

### Task PR Feedback

**Endpoint**: `GET /api/tasks/{task_id}/pr-feedback`

Returns structured PR review feedback (reviews with inline comment threads and standalone comment threads) from GitHub. Only available when the task is in `PR_OPEN` state with a configured PR number. Used by the frontend to display GitHub review comments inline in the File Changes diff view.

## Future Considerations

**Versioning**: Currently v1 implied. Use `/api/v2/` prefix for breaking changes.

**Authentication**: Currently none (single-user local). Future: token-based for multi-user.

**Rate Limiting**: Currently none (local). Respects external API limits (GitHub, Jira, etc.).
