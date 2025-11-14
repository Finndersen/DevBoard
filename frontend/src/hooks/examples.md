# Conversation Event Handler Examples

## Overview

The conversation event handler framework allows components to respond to:
- **Tool Results**: When agent tools complete execution
- **System Events**: When entities are updated (tasks, conversations, etc.)

## Setup

### 1. Wrap conversation components with provider

```tsx
import ConversationEventHandlerProvider from '../components/chat/ConversationEventHandlerProvider'

<ConversationEventHandlerProvider>
  <ConversationChat conversationId={123} />
</ConversationEventHandlerProvider>
```

### 2. Pass registry to stream processor

In components that process conversation streams (e.g., `ConversationChat`):

```tsx
import { useEventHandlerRegistryForStream } from '../hooks/useConversationEventHandlers'
import { processConversationStream } from '../lib/streamProcessor'

function ConversationChat() {
  const eventHandlerRegistry = useEventHandlerRegistryForStream()

  const sendMessage = async (message: string) => {
    await processConversationStream({
      stream: apiClient.streamConversationMessage(conversationId, { message }),
      onEvent: (event) => setMessages(prev => [...prev, event]),
      eventHandlerRegistry  // Pass registry to enable handlers
    })
  }

  // ... rest of component
}
```

## Examples

### Reload Task Document on Edit

Automatically refetch document content when document editing tools complete:

```tsx
import { useToolResultHandler } from '../hooks/useConversationEventHandlers'

function TaskDocumentView({ taskId }: { taskId: number }) {
  const { data: specification, refetch: refetchSpec } = useQuery(/* ... */)
  const { data: implementationPlan, refetch: refetchPlan } = useQuery(/* ... */)

  // Handle specification edits
  useToolResultHandler(
    /mcp__devboard_tools__(?:edit|set)_specification/,
    async (result) => {
      console.log('Specification updated, refetching...')
      await refetchSpec()
    }
  )

  // Handle implementation plan edits
  useToolResultHandler(
    /mcp__devboard_tools__(?:edit|set)_implementation_plan/,
    async (result) => {
      console.log('Implementation plan updated, refetching...')
      await refetchPlan()
    }
  )

  // Or handle all document edits together
  useToolResultHandler(
    (toolName) => toolName.startsWith('mcp__devboard_tools__') &&
                  (toolName.includes('edit_') || toolName.includes('set_')),
    async (result) => {
        console.log('Document edited, refetching all...')
        await Promise.all([refetchSpec(), refetchPlan()])
      }
    }
  )

  return (
    <div>
      {/* Document display */}
    </div>
  )
}
```

### Update Conversation Details on System Event

Update displayed conversation details when CONVERSATION_UPDATED event is received:

```tsx
import { useSystemEventHandler } from '../hooks/useConversationEventHandlers'

function ConversationDetailsPanel({ conversationId }: { conversationId: number }) {
  const [sessionId, setSessionId] = useState<string | null>(null)

  // Handle conversation updates
  useSystemEventHandler('conversation_updated', (event) => {
    const { conversation_id, updated_fields } = event.data

    // Only update if this is our conversation
    if (conversation_id !== conversationId) return

    // Check which fields were updated and update local state
    if ('external_session_id' in updated_fields) {
      setSessionId(updated_fields.external_session_id)
      console.log('Session ID updated:', updated_fields.external_session_id)
    }

    // Could also refetch full conversation data
    // refetchConversation()
  })

  return (
    <div>
      <p>Conversation ID: {conversationId}</p>
      {sessionId && <p>Session ID: {sessionId}</p>}
    </div>
  )
}
```

### Update Task Status Display

Update task status badge when task is updated:

```tsx
import { useSystemEventHandler } from '../hooks/useConversationEventHandlers'

function TaskStatusBadge({ taskId }: { taskId: number }) {
  const [status, setStatus] = useState<string>('defining')

  useSystemEventHandler('task_updated', (event) => {
    const { task_id, updated_fields } = event.data

    // Only update if this is our task
    if (task_id !== taskId) return

    // Check if status was updated
    if ('status' in updated_fields) {
      setStatus(updated_fields.status)
    }

    // Check if documents were updated
    if ('specification_id' in updated_fields || 'implementation_plan_id' in updated_fields) {
      console.log('Task documents updated')
      // Could trigger document refresh here
    }
  })

  return <StatusBadge status={status} />
}
```

### Listen to All System Events (Debugging)

```tsx
import { useSystemEventHandler } from '../hooks/useConversationEventHandlers'

function DebugEventMonitor() {
  useSystemEventHandler('*', (event) => {
    console.log('System event received:', {
      type: event.type,
      data: event.data,
      timestamp: event.timestamp
    })
  })

  return null // No UI, just logging
}
```

### Complex Example: Task Page with Multiple Handlers

```tsx
import { useToolResultHandler, useSystemEventHandler } from '../hooks/useConversationEventHandlers'

function TaskPage({ taskId }: { taskId: number }) {
  const { data: task, refetch: refetchTask } = useTaskQuery(taskId)
  const { data: spec, refetch: refetchSpec } = useSpecQuery(taskId)
  const { data: plan, refetch: refetchPlan } = usePlanQuery(taskId)

  // Handle task status changes
  useSystemEventHandler('task_updated', (event) => {
    if (event.data.task_id !== taskId) return

    const { updated_fields } = event.data

    // Refetch based on what changed
    if ('status' in updated_fields) {
      refetchTask()
    }
    if ('specification_id' in updated_fields) {
      refetchSpec()
    }
    if ('implementation_plan_id' in updated_fields) {
      refetchPlan()
    }
  })

  // Handle document content edits
  useToolResultHandler(/mcp__devboard_tools__edit_specification/, async () => {
    await refetchSpec()
  })

  useToolResultHandler(/mcp__devboard_tools__edit_implementation_plan/, async () => {
    await refetchPlan()
  })

  // Handle full content replacements
  useToolResultHandler(/mcp__devboard_tools__set_.*_content/, async (result) => {
    await Promise.all([refetchSpec(), refetchPlan()])
  })

  return (
    <div>
      <TaskHeader task={task} />
      <DocumentViewer spec={spec} plan={plan} />
      <ConversationEventHandlerProvider>
        <ConversationChat conversationId={task.conversation_id} />
      </ConversationEventHandlerProvider>
    </div>
  )
}
```

## Pattern Matching

### String Pattern (Exact Match)
```tsx
useToolResultHandler('mcp__devboard_tools__edit_specification', handler)
```

### Regex Pattern
```tsx
useToolResultHandler(/mcp__devboard_tools__edit_.*/, handler)
```

### Function Pattern
```tsx
useToolResultHandler(
  (name) => name.startsWith('mcp__') && name.includes('edit'),
  handler
)
```

## Best Practices

1. **Error handling**: Tool result handlers automatically skip error results (is_error=true), so you only handle successful operations
2. **Filter by entity ID**: For system events, check the entity ID matches what you're displaying
3. **Granular refetching**: Only refetch data that actually changed
4. **Debounce refetches**: If multiple events might fire rapidly, consider debouncing
5. **Cleanup**: Handlers are automatically cleaned up when components unmount
