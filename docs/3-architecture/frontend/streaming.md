# Frontend Streaming Architecture

**Navigation**: [Documentation Home](../../INDEX.md) > [Architecture](../INDEX.md) > [Frontend](./INDEX.md) > Streaming

## Overview

Real-time agent conversation updates using WebSocket connections. Agent execution is decoupled from the HTTP request lifecycle: HTTP endpoints start background tasks and return immediately, while clients consume events via WebSocket.

**Key Technologies**: WebSocket, async generators, event-based architecture, background asyncio tasks

## Architecture: Background Tasks + WebSocket

### High-Level Flow

1. **Client sends message/action** → POST to HTTP endpoint → server starts background agent execution → returns `{"conversation_id": N}` immediately
2. **Background execution** → agent runs as asyncio task, pushes `ConversationEvent` objects to an in-memory `asyncio.Queue`
3. **Client consumes events** → WebSocket connection to `/api/conversations/{id}/ws` → server drains queue and sends events as JSON
4. **Completion** → server sends `agent_run_completed` lifecycle event → client terminates stream

### Why WebSocket Instead of NDJSON HTTP Streaming

- **Reconnection resilience**: Client can disconnect and reconnect mid-execution. Unconsumed events are buffered in the in-memory queue.
- **Graceful interruption**: Client sends HTTP `POST /interrupt` → server signals interrupt flag → agent stops gracefully
- **Decoupled lifecycle**: Agent execution continues even if HTTP connection drops. No lost events.

## WebSocket Protocol

**Endpoint**: `GET /api/conversations/{conversation_id}/ws`

**Direction**: Unidirectional — server→client only. The WebSocket carries events from the server to the client. Client-to-server communication (e.g., interrupt) uses separate HTTP endpoints.

### Server→Client Messages

All messages are JSON. Discriminated by `event_type` field:

**Conversation events** (same as stored message history):
- `{ "event_type": "message", "role": "agent", "text_content": "...", "timestamp": "..." }`
- `{ "event_type": "tool_call", "tool_call_id": "...", "tool_name": "...", ... }`
- `{ "event_type": "tool_result", "tool_call_id": "...", "result_content": "...", ... }`
- `{ "event_type": "tool_call_request", ... }` — requires user approval
- `{ "event_type": "system", "type": "task_updated", ... }`

**Execution lifecycle events** (emitted by `AgentExecutionService` as first/last stream events):
- `{ "event_type": "agent_run_started", "conversation_id": <int> }`
- `{ "event_type": "agent_run_completed", "status": "completed|interrupted|failed", "error": null, "usage": null }`

### Connection Lifecycle

```
Client                          Server
  |                               |
  |--- GET /ws ------------------>|  WebSocket handshake
  |                               |
  |<-- agent_run_started ---------|  Agent execution begins
  |<-- ConversationEvent ----------|  Events stream as agent runs
  |<-- ConversationEvent ----------|
  |<-- agent_run_completed --------|  Execution done
  |                               |
  |  (waits for next execution)   |
  |<-- agent_run_started ---------|  Next approval/message
  ...
```

The WebSocket connection stays open across multiple sequential executions (send message → approve tools → etc.).

## Frontend WebSocket Implementation

### WebSocketManager

**Location**: `frontend/src/services/WebSocketManager.ts`

Singleton managing WebSocket connections per conversation. Provides:
- `ensureConnected(conversationId)` — creates or reuses connection
- `registerMessageHandler(conversationId, handler)` — push-based message delivery
- `unregisterMessageHandler(conversationId, handler)` — cleanup
- Auto-reconnect with exponential backoff (max 5 attempts)
- Connection limit (max 10 concurrent connections)

### createWebSocketEventStream

**Location**: `frontend/src/lib/websocketStream.ts`

Bridges push-based WebSocket messages to pull-based async generator, enabling the existing `startStream()` / `processConversationStream()` pipeline to work unchanged.

```typescript
async function* createWebSocketEventStream(conversationId: number): AsyncGenerator<ConversationEvent>
```

**Behavior**:
- Registers a handler with `WebSocketManager` for message routing
- Buffers incoming events in a local array
- Yields events as they arrive via a Promise-based wait mechanism
- Terminates when `agent_run_completed` lifecycle event is received

### API Client Methods

**Location**: `frontend/src/lib/api.ts`

```typescript
// POST /messages → starts background execution → returns WebSocket stream
async *streamConversationMessage(conversationId, request): AsyncGenerator<ConversationEvent>

// POST /approve-tools → resumes execution → returns WebSocket stream
async *streamApproveConversationTools(conversationId, request): AsyncGenerator<ConversationEvent>

// POST /workflow-action → runs procedural steps, optionally starts agent
// Returns { conversation_id } if agent started, { status: "completed" } otherwise
async executeWorkflowAction(taskId, request): Promise<{ conversation_id?: number; status?: string }>

// POST /interrupt → requests graceful stop
async interruptConversation(conversationId): Promise<void>
```

Conversation streaming methods POST to the backend first (starting/resuming execution), then return `createWebSocketEventStream()` for the target conversation. Workflow actions return immediately and the caller creates a WebSocket stream only if `conversation_id` is returned.

## Graceful Interruption

**User action**: Click stop button → calls `stopStream(conversationId)` in store

**Store behavior**: Calls `apiClient.interruptConversation(conversationId)` (fire-and-forget HTTP POST), optimistically marks stream as not streaming.

**Server behavior**: Sets `interrupt_event` asyncio.Event → agent checks flag between tool calls → raises `AgentInterruptedError` → `AgentExecutionService` catches it, yields `agent_run_completed` with status `interrupted`, then re-raises.

**Result**: All messages processed before interruption are persisted. WebSocket stream terminates naturally.

## Event Handler Architecture

**Location**: `frontend/src/hooks/useConversationEventHandlers.ts`

Same as before — React Context-based registry for:
- `useToolResultHandler(handler)` — called when tool execution completes
- `useSystemEventHandler(handler)` — called for system events (task_updated, etc.)
- `useStreamCompleteHandler(handler)` — called when execution completes

### Workflow Action Conversation Switching

Workflow actions that create new conversations (e.g., BeginImplementation) do so synchronously within the HTTP request handler. The response includes the new `conversation_id`, which the frontend uses to create a WebSocket stream on the correct conversation. The frontend always refetches task details after a workflow action completes to pick up status changes, new conversation IDs, and updated available actions.

## Conversation Stream Store

**Location**: `frontend/src/stores/conversationStreamStore.ts`

Manages streaming state per conversation. Key changes from the old streaming architecture:
- No `abortController` in `StreamState` — interruption is via HTTP, not fetch abort
- `stopStream()` calls `apiClient.interruptConversation()` instead of aborting fetch
- `startStream()` takes no `abortController` parameter — streams self-terminate via WebSocket

## Multitasking and State Preservation

The WebSocket architecture improves resilience compared to HTTP streaming:

- **Tab switching**: WebSocket connection maintained. Events continue to buffer in queue even with no consumer.
- **Navigation**: Stream state preserved in Zustand store across component unmounts.
- **Reconnection**: Queue buffers events during disconnection. Consumer receives all events on reconnect.
- **Server restarts**: Active executions are lost (in-memory only), but all persisted messages remain in database.
