import { memo, useMemo } from 'react'
import type { ConversationEvent, ToolCall, ToolResult } from '../../lib/api'
import ConversationMessageComponent from './ConversationMessage'
import PendingMessageComponent from './PendingMessage'
import ToolCallGroupDisplay from './ToolCallGroupDisplay'
import AgentBlockDisplay from './AgentBlockDisplay'
import type { PendingMessage } from '../../contexts/PendingMessagesContext'

interface ConversationMessageListProps {
  messages: ConversationEvent[]
  pendingMessage: PendingMessage | null
  onRetryMessage: (messageId: string) => void
  emptyStateMessage: string
  showEmptyState: boolean
  codebaseLocalPath?: string
  highlightUuids?: string[]
  sessionId?: string
}

interface SingleRenderItem {
  type: 'single'
  message: ConversationEvent
  index: number
  previousEventTimestamp: string | null
}

interface GroupRenderItem {
  type: 'group'
  items: Array<{ message: ToolCall; index: number; previousEventTimestamp: string | null }>
}

type RenderItem = SingleRenderItem | GroupRenderItem

interface AgentBlockItem {
  type: 'agent_block'
  items: RenderItem[]
}

interface UserMessageItem {
  type: 'user_message'
  message: ConversationEvent
  index: number
  previousEventTimestamp: string | null
}

type OuterRenderItem = UserMessageItem | AgentBlockItem

// Memoized message component to prevent unnecessary re-renders
const MemoizedMessageComponent = memo(ConversationMessageComponent)

// Memoized pending message component
const MemoizedPendingMessage = memo(PendingMessageComponent)

function ConversationMessageList({
  messages,
  pendingMessage,
  onRetryMessage,
  emptyStateMessage,
  showEmptyState,
  codebaseLocalPath,
  highlightUuids,
  sessionId,
}: ConversationMessageListProps) {
  // Compute tool result mappings using useMemo
  // This creates a Map of cache keys to ToolResults, recomputed only when messages change
  const toolResultMap = useMemo(() => {
    const map = new Map<string, ToolResult>()

    const findToolResult = (toolCallId: string, toolCallIndex: number): ToolResult | undefined => {
      for (let i = toolCallIndex + 1; i < messages.length; i++) {
        const msg = messages[i]
        if (msg.event_type === 'tool_result' && msg.tool_call_id === toolCallId) {
          return msg as ToolResult
        }
      }
      return undefined
    }

    // Check if there's a subsequent message event (user or agent text) after a given index,
    // indicating the conversation moved past that point
    const hasSubsequentMessage = (afterIndex: number): boolean => {
      for (let i = afterIndex + 1; i < messages.length; i++) {
        if (messages[i].event_type === 'message') {
          return true
        }
      }
      return false
    }

    messages.forEach((message, index) => {
      if (message.event_type === 'tool_call') {
        const cacheKey = `${message.timestamp}-${message.event_type}-${index}`
        const result = findToolResult(message.tool_call_id, index)
        if (result) {
          map.set(cacheKey, result)
        } else if (hasSubsequentMessage(index)) {
          // Tool call is orphaned: the conversation moved on without a result.
          // This happens when a stream was interrupted (e.g. client disconnect).
          map.set(cacheKey, {
            event_type: 'tool_result',
            tool_call_id: message.tool_call_id,
            result_content: 'Tool execution was interrupted.',
            is_error: true,
            timestamp: message.timestamp,
          })
        }
      }
    })

    return map
  }, [messages])

  const highlightSet = useMemo(() => new Set(highlightUuids ?? []), [highlightUuids])

  // Find the index of the last 'message' type event
  const lastMessageIndex = useMemo(() => {
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i].event_type === 'message') {
        return i
      }
    }
    return -1
  }, [messages])

  // Group consecutive tool_call events into GroupRenderItems.
  // tool_result events are skipped (they are hidden and paired via toolResultMap).
  // Any other event type breaks the current group.
  // Trailing tool calls (at end of list, not followed by a non-tool event) stay as individual items.
  const renderItems = useMemo((): RenderItem[] => {
    const result: RenderItem[] = []
    let toolCallBuffer: Array<{ message: ToolCall; index: number; previousEventTimestamp: string | null }> = []
    let lastTimestamp: string | null = null

    const flushBuffer = (asGroup: boolean) => {
      if (toolCallBuffer.length === 0) return

      if (asGroup && toolCallBuffer.length >= 2) {
        result.push({ type: 'group', items: toolCallBuffer })
      } else {
        for (const item of toolCallBuffer) {
          result.push({ type: 'single', message: item.message, index: item.index, previousEventTimestamp: item.previousEventTimestamp })
        }
      }
      toolCallBuffer = []
    }

    for (let i = 0; i < messages.length; i++) {
      const message = messages[i]

      if (message.event_type === 'tool_result') {
        // Skip tool_result events — they are rendered inside their paired tool_call
        continue
      }

      if (message.event_type === 'tool_call') {
        // Previous for this tool call: the event before the buffer started (if first), or the previous tool call
        const prevTs = toolCallBuffer.length === 0 ? lastTimestamp : toolCallBuffer[toolCallBuffer.length - 1].message.timestamp
        toolCallBuffer.push({ message: message as ToolCall, index: i, previousEventTimestamp: prevTs })
      } else {
        // Non-tool event: flush buffer as a group, then add this event
        flushBuffer(true)
        result.push({ type: 'single', message, index: i, previousEventTimestamp: lastTimestamp })
      }

      lastTimestamp = message.timestamp
    }

    // Trailing tool calls are NOT grouped — keep them as individual items
    flushBuffer(false)

    return result
  }, [messages])

  // Group consecutive non-user items into agent blocks, separated by user messages.
  const outerRenderItems = useMemo((): OuterRenderItem[] => {
    const result: OuterRenderItem[] = []
    let agentBuffer: RenderItem[] = []

    const flushAgentBuffer = () => {
      if (agentBuffer.length > 0) {
        result.push({ type: 'agent_block', items: agentBuffer })
        agentBuffer = []
      }
    }

    for (const item of renderItems) {
      if (item.type === 'single' && item.message.event_type === 'message' && item.message.role === 'user') {
        flushAgentBuffer()
        result.push({ type: 'user_message', message: item.message, index: item.index, previousEventTimestamp: item.previousEventTimestamp })
      } else {
        agentBuffer.push(item)
      }
    }

    flushAgentBuffer()
    return result
  }, [renderItems])

  const lastAgentBlockIndex = useMemo(() => {
    for (let i = outerRenderItems.length - 1; i >= 0; i--) {
      if (outerRenderItems[i].type === 'agent_block') return i
    }
    return -1
  }, [outerRenderItems])

  if (showEmptyState) {
    return (
      <div className="text-center text-gray-500 dark:text-gray-400 py-8">
        <p className="text-sm">{emptyStateMessage}</p>
        <p className="text-xs mt-2">I can help with code analysis, documentation, and project insights.</p>
      </div>
    )
  }

  const renderInnerItem = (item: RenderItem) => {
    if (item.type === 'group') {
      const groupKey = item.items.map(({ message, index }) => `${message.timestamp}-tool_call-${index}`).join('|')
      return (
        <ToolCallGroupDisplay
          key={groupKey}
          items={item.items}
          toolResultMap={toolResultMap}
          highlightSet={highlightSet}
          codebaseLocalPath={codebaseLocalPath}
          sessionId={sessionId}
        />
      )
    }

    const messageKey = `${item.message.timestamp}-${item.message.event_type}-${item.index}`
    const toolResult = item.message.event_type === 'tool_call'
      ? toolResultMap.get(messageKey)
      : undefined
    const isLatest = item.index === lastMessageIndex
    const uuid = (item.message as { uuid?: string }).uuid
    const isHighlighted = uuid ? highlightSet.has(uuid) : false

    return (
      <div key={messageKey} id={uuid ? `msg-${uuid}` : undefined}>
        <MemoizedMessageComponent
          message={item.message}
          toolResult={toolResult}
          isLatest={isLatest}
          isHighlighted={isHighlighted}
          codebaseLocalPath={codebaseLocalPath}
          sessionId={sessionId}
          previousEventTimestamp={item.previousEventTimestamp}
        />
      </div>
    )
  }

  return (
    <>
      {outerRenderItems.map((outerItem, outerIndex) => {
        if (outerItem.type === 'user_message') {
          const messageKey = `${outerItem.message.timestamp}-${outerItem.message.event_type}-${outerItem.index}`
          const uuid = (outerItem.message as { uuid?: string }).uuid
          const isHighlighted = uuid ? highlightSet.has(uuid) : false
          return (
            <div key={messageKey} id={uuid ? `msg-${uuid}` : undefined}>
              <MemoizedMessageComponent
                message={outerItem.message}
                toolResult={undefined}
                isLatest={outerItem.index === lastMessageIndex}
                isHighlighted={isHighlighted}
                codebaseLocalPath={codebaseLocalPath}
                sessionId={sessionId}
                previousEventTimestamp={outerItem.previousEventTimestamp}
              />
            </div>
          )
        }

        const blockKey = outerItem.items.length > 0
          ? (() => {
              const first = outerItem.items[0]
              return first.type === 'group'
                ? `agent-block-${first.items[0].message.timestamp}-tool_call-${first.items[0].index}`
                : `agent-block-${first.message.timestamp}-${first.message.event_type}-${first.index}`
            })()
          : `agent-block-${outerIndex}`

        return (
          <AgentBlockDisplay key={blockKey} isLatest={outerIndex === lastAgentBlockIndex}>
            {outerItem.items.map(renderInnerItem)}
          </AgentBlockDisplay>
        )
      })}

      {/* Render pending message if exists */}
      {pendingMessage && (
        <MemoizedPendingMessage
          key={pendingMessage.id}
          message={pendingMessage}
          onRetry={onRetryMessage}
        />
      )}
    </>
  )
}

// Wrap in memo to prevent re-renders when parent re-renders but messages haven't changed
export default memo(ConversationMessageList)
