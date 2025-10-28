import { memo, useCallback } from 'react'
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
  showEmptyState
}: ConversationMessageListProps) {
  // Find matching tool result for a tool call
  // Searches for the NEXT ToolResult with matching tool_call_id that comes AFTER the tool call
  const findToolResult = useCallback((toolCallId: string, toolCallIndex: number): ToolResult | undefined => {
    // Search only messages that come after the tool call
    for (let i = toolCallIndex + 1; i < messages.length; i++) {
      const msg = messages[i]
      if (msg.event_type === 'tool_result' && msg.tool_call_id === toolCallId) {
        return msg as ToolResult
      }
    }
    return undefined
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
        // For tool calls, find the matching result
        const toolResult = message.event_type === 'tool_call'
          ? findToolResult(message.tool_call_id, index)
          : undefined

        // Create a truly unique key combining timestamp and event type + index
        // This ensures uniqueness even for messages generated in the same millisecond
        const messageKey = `${message.timestamp}-${message.event_type}-${index}`

        return (
          <MemoizedMessageComponent
            key={messageKey}
            message={message}
            toolResult={toolResult}
          />
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
