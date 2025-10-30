# Frontend Streaming Architecture

**Navigation**: [Documentation Home](../../INDEX.md) > [Architecture](../INDEX.md) > [Frontend](./INDEX.md) > Streaming

## Overview

Real-time agent conversation updates using NDJSON streaming. Immediate feedback as agents process requests.

**Key Technologies**: NDJSON (newline-delimited JSON), async generators, event-based architecture

## NDJSON Streaming Protocol

**Format**: Each line contains complete JSON object followed by newline.

**Example Stream**:
```
{"event_type":"text_message","role":"assistant","text_content":"Analyzing...","timestamp":"2024-01-01T10:00:00Z"}
{"event_type":"tool_call","tool_call_id":"tc_1","tool_name":"search_codebase","tool_args":{"query":"auth"},"timestamp":"2024-01-01T10:00:01Z"}
{"event_type":"tool_result","tool_call_id":"tc_1","result_content":"Found 5 files","is_error":false,"timestamp":"2024-01-01T10:00:03Z"}
```

**Benefits**: Incremental parsing, no buffering entire response, clear message boundaries

### NDJSON Parser

**Location**: `frontend/src/lib/api.ts` (within streaming methods)

Line buffering for incomplete chunks, UTF-8 decoding, async generator for clean consumption, type-safe with generics.

**Pattern**:
```typescript
async function* parseNDJSONStream<T>(stream: ReadableStream<Uint8Array>): AsyncGenerator<T>
```

Splits incoming bytes by newlines, maintains buffer for incomplete lines, yields parsed JSON objects.

## Event-Based Chat Architecture

**Location**: `frontend/src/components/chat/ConversationChat.tsx`

### Streaming Event Consumption

Core chat component consumes streaming events via async generators:

**Pattern**:
```typescript
const eventStream = apiClient.sendMessageStreaming(conversationId, message)
for await (const event of eventStream) {
  setEvents(prev => [...prev, event])
}
```

**Benefits**: Events appear progressively, immediate feedback, improved perceived performance

### Event Type Discrimination

Type-safe event rendering with discriminated unions:

```typescript
switch (event.event_type) {
  case 'text_message': return <ConversationMessage message={event} />
  case 'tool_call': return <ToolCallDisplay toolCall={event} />
  case 'tool_result': return <ToolResult result={event} />
  case 'tool_call_request': return <ToolApprovalRequest request={event} />
}
```

TypeScript exhaustiveness check ensures all event types handled at compile time.

## API Client Streaming Methods

**Location**: `frontend/src/lib/api.ts`

### Async Generator Pattern

API client provides async generator methods for streaming endpoints:

**Send Message with Streaming**:
```typescript
async *sendMessageStreaming(conversationId: number, message: string): AsyncGenerator<ConversationEvent>
```

**Approve Tools with Streaming**:
```typescript
async *approveToolsStreaming(conversationId: number, approvals: ToolApprovalRequest): AsyncGenerator<ConversationEvent>
```

**Implementation**: Fetch streaming endpoint, parse NDJSON with `parseNDJSONStream()`, yield events.

## Real-Time UI Updates

### Progressive Event Display

**User Experience Timeline**:
1. User sends message → Message appears immediately
2. Agent starts processing → Loading indicator
3. Tool call event → Tool call card appears (collapsed)
4. Tool result event → Result added to tool call card
5. Agent text response → Response message appears
6. Streaming complete → Loading indicator removed

**Pattern**: Events added to timeline as they arrive. UI updates incrementally without waiting for completion.

### Streaming State Management

Track streaming state for UI feedback:

```typescript
const [streamingState, setStreamingState] = useState<{
  isStreaming: boolean
  currentToolCall?: string
}>({ isStreaming: false })
```

Update state during streaming to show current tool execution, display loading indicators, enable/disable input.

## Error Handling

### Stream Error Recovery

**Error Scenarios**: Network interruption mid-stream, invalid JSON, server error during processing

**Pattern**:
```typescript
try {
  for await (const event of eventStream) {
    addEvent(event)
  }
} catch (error) {
  // Show error message, preserve already received events
}
```

### Partial Stream Recovery

Events received before error remain in UI. Allows retry from last received event.

## Performance Characteristics

**Immediate Feedback**: Users see agent activity as it happens, tool executions visible real-time, progress based on actual events

**Perceived Performance**: UI feels responsive, no "black box" waiting, incremental content reduces perceived latency

**Resource Efficiency**: No buffering entire response, memory proportional to event rate

### Optimizations

**Virtual Scrolling**: Handle large conversation histories efficiently in ConversationChat component

**Event Deduplication**: Prevent duplicates when reconnecting mid-stream

## DevBoard-Specific Patterns

### Tool Call/Result Streaming

Tool calls and results stream as separate events. `findToolResult()` helper in ConversationChat matches ToolResult to ToolCall by `tool_call_id` for integrated display.

**Pattern**: ToolCall event arrives → card appears with spinner. ToolResult event arrives → result added to card, spinner replaced with checkmark/error icon.

### Tool Approval Request Streaming

When agent encounters tool requiring approval:
1. Agent streams `ToolCallRequest` event
2. Frontend pauses event consumption, displays approval UI
3. User approves/denies
4. Frontend calls `/approve-tools/stream`
5. Agent resumes, streams completion events

**Pattern**: Two-phase streaming: initial request stream pauses at approval, approval response stream continues to completion.

## See Also

- [Components](./components.md) - Chat component implementation
- [Patterns](./patterns.md) - Frontend development patterns
- [Backend API Reference](../backend/api-reference.md) - Streaming endpoints
