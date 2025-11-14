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
  case 'message': return <ConversationMessage message={event} />
  case 'tool_call': return <ToolCallDisplay toolCall={event} />
  case 'tool_result': return <ToolResult result={event} />
  case 'tool_call_request': return <ToolApprovalRequest request={event} />
  case 'system': // Handled by registered SystemEventHandlers, not rendered
}
```

TypeScript exhaustiveness check ensures all event types handled at compile time.

## Event Handler Architecture

**Location**: `frontend/src/hooks/useConversationEventHandlers.ts`, `frontend/src/components/chat/ConversationEventHandlerProvider.tsx`

The frontend implements a sophisticated event handler system for processing conversation events with side effects.

### ConversationEventHandlerProvider

A React Context provider that maintains registries for tool result handlers and system event handlers. Must wrap conversation components that need to react to events.

**Pattern**:
```typescript
<ConversationEventHandlerProvider>
  <TaskDetail id={123} />
</ConversationEventHandlerProvider>
```

**Registry Structure**:
- `toolResultHandlers`: Map of matchers to handler sets for tool execution results
- `systemEventHandlers`: Map of matchers to handler sets for system events

**Architecture**: Each parent view (TaskDetail, ProjectDetail) is wrapped in a provider at the TabContentContainer level. This ensures a single registry per conversation context, allowing components to register handlers that execute when matching events stream through ConversationChat.

### Tool Result Handlers

Components can register handlers that execute when specific tools complete successfully (error results are automatically skipped).

**Hook**: `useToolResultHandler(matcher, handler)`

**Example - Handle document edits**:
```typescript
useToolResultHandler(
  (toolName) => toolName.includes('edit_specification'),
  async (result) => await refetchSpecification()
)
```

**Example - Handle multiple tools**:
```typescript
useToolResultHandler(
  (toolName) => ['edit_specification', 'set_specification_content'].some(t => toolName.includes(t)),
  async () => await refetchDocuments()
)
```

**Pattern**: Matcher receives tool name and event, returns boolean. Handler receives ToolResult event. Multiple handlers can match a single tool result.

### System Event Handlers

Components can register handlers for system-level events like task updates and conversation changes.

**Hook**: `useSystemEventHandler(matcher, handler)`

**Example - Handle task updates**:
```typescript
useSystemEventHandler(
  (event) => event.type === 'task_updated' && event.data?.task_id === taskId,
  async (event) => {
    const { updated_fields } = event.data
    if ('status' in updated_fields) {
      // Task status changed during workflow action
      await refetch()
    }
    if ('implementation_plan_id' in updated_fields) {
      // Implementation plan was created
      await refetch()
    }
  }
)
```

**Pattern**: Matcher receives SystemEvent, returns boolean. Handler receives SystemEvent. Enables reactive updates to task state changes, workflow transitions, and entity modifications.

### Event Processing Flow

**ConversationChat Integration**:
1. ConversationChat retrieves registry via `useEventHandlerRegistryForStream()`
2. Passes registry to `processConversationStream()` helper
3. Stream processor invokes `invokeEventHandlers()` for each event
4. For ToolResult events: maps tool_call_id to tool name, skips errors, finds matching handlers
5. For SystemEvent events: finds matching handlers based on event type and data
6. All matching handlers execute concurrently via `Promise.all()`

**Benefits**:
- Decoupled event handling from rendering logic
- Type-safe event matching and handling
- Automatic cleanup on component unmount
- Supports multiple handlers per event type
- Error results automatically filtered out for tool handlers
- System events filtered from UI display (handled in background)

**Implementation**: The `processConversationStream` helper in `streamProcessor.ts` builds a tool call map from ToolCall events, then uses it to resolve tool names for ToolResult events. System events skip the UI rendering pipeline entirely and only trigger registered handlers.

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

## Multitasking and Streaming State Preservation

**Challenge**: In a multitasking environment with multiple tabs, switching between tabs must not interrupt or lose streaming state.

### Implementation Strategy

**Location**: `frontend/src/components/chat/ConversationChat.tsx`, `frontend/src/views/TaskDetail.tsx`, `frontend/src/views/ProjectDetail.tsx`, `frontend/src/components/layout/TabContentContainer.tsx`

#### Component Memoization

All view components (TaskDetail, ProjectDetail) are wrapped with `React.memo()` and custom comparison functions:

```typescript
export default memo(TaskDetail, (prevProps, nextProps) => {
  return prevProps.id === nextProps.id
})
```

**Effect**: Only re-renders when entity ID changes, not when other tabs switch. Preserves all component state including active streaming sessions.

#### Conversation History Fetch Optimization

ConversationChat tracks which conversations have been fetched to prevent unnecessary refetches:

```typescript
const lastFetchedConversationIdRef = useRef<number | null>(null)

const fetchChatHistory = useCallback(async () => {
  // Only fetch if we haven't already fetched for this conversation
  if (lastFetchedConversationIdRef.current === conversationId) {
    return
  }

  const data = await apiClient.getConversationMessages(conversationId)
  setMessages(data)
  lastFetchedConversationIdRef.current = conversationId
}, [conversationId])
```

**Effect**: Prevents overwriting client-side streaming messages with incomplete backend history when tabs switch.

#### Tab Container Optimization

TabContentContainer uses `useMemo` to prevent unnecessary re-render cascades:

```typescript
const renderedTabs = useMemo(() => {
  return tabs.map(tab => {
    const isActive = tab.id === activeTabId
    return <div style={{ visibility: isActive ? 'visible' : 'hidden' }}>
      {/* tab content */}
    </div>
  })
}, [tabs, activeTabId])
```

**Effect**: Minimizes re-renders when switching tabs. Combined with component memoization, ensures inactive tabs don't re-render unnecessarily.

### State Preservation Guarantees

With these optimizations:
- ✓ Streaming messages remain in client state when switching tabs
- ✓ No refetch of conversation history on tab switch
- ✓ Active streaming connections maintained (subject to browser throttling)
- ✓ Minimal re-renders across all mounted components
- ✓ Seamless multitasking experience

### Browser Considerations

Modern browsers may throttle or suspend fetch requests for hidden tabs. While components stay mounted and state preserved, the underlying network connection may be affected by browser optimizations. The application maintains message state regardless of connection status.
