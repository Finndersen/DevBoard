import { memo, useMemo } from 'react'
import type { ConversationEvent, ToolResult } from '../../lib/api'
import ConversationMessageComponent from './ConversationMessage'
import PendingMessageComponent from './PendingMessage'
import type { PendingMessage } from '../../contexts/PendingMessagesContext'

interface ConversationMessageListProps {
  messages: ConversationEvent[]
  pendingMessage: PendingMessage | null
  onRetryMessage: (messageId: string) => void
  emptyStateMessage: string
  showEmptyState: boolean
  codebaseLocalPath?: string
  highlightUuids?: string[]
}

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
  highlightUuids
}: ConversationMessageListProps) {
  // Compute tool result mappings using useMemo
  // This creates a Map of cache keys to ToolResults, recomputed only when messages change
  // Using useMemo ensures React knows to re-render when this changes
  const toolResultMap = useMemo(() => {
    const map = new Map<string, ToolResult>()

    // Helper function to find matching tool result for a tool call
    const findToolResult = (toolCallId: string, toolCallIndex: number): ToolResult | undefined => {
      // Search only messages that come after the tool call
      for (let i = toolCallIndex + 1; i < messages.length; i++) {
        const msg = messages[i]
        if (msg.event_type === 'tool_result' && msg.tool_call_id === toolCallId) {
          return msg as ToolResult
        }
      }
      return undefined
    }

    messages.forEach((message, index) => {
      if (message.event_type === 'tool_call') {
        const cacheKey = `${message.timestamp}-${message.event_type}-${index}`
        const result = findToolResult(message.tool_call_id, index)
        if (result) {
          map.set(cacheKey, result)
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

  if (showEmptyState) {
    return (
      <div className="text-center text-gray-500 dark:text-gray-400 py-8">
        <p className="text-sm">{emptyStateMessage}</p>
        <p className="text-xs mt-2">I can help with code analysis, documentation, and project insights.</p>
      </div>
    )
  }

  return (
    <>
      {/* Render confirmed messages with memoization to avoid unnecessary re-renders */}
      {messages.map((message, index) => {
        const messageKey = `${message.timestamp}-${message.event_type}-${index}`
        const toolResult = message.event_type === 'tool_call'
          ? toolResultMap.get(messageKey)
          : undefined
        const isLatest = index === lastMessageIndex
        const uuid = (message as { uuid?: string }).uuid
        const isHighlighted = uuid ? highlightSet.has(uuid) : false

        return (
          <div key={messageKey} id={uuid ? `msg-${uuid}` : undefined}>
            <MemoizedMessageComponent
              message={message}
              toolResult={toolResult}
              isLatest={isLatest}
              isHighlighted={isHighlighted}
              codebaseLocalPath={codebaseLocalPath}
            />
          </div>
        )
      })}

      {/* Render pending message if exists (memoized to prevent unnecessary re-renders) */}
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
