import { useState, useEffect, useCallback } from 'react'
import { textColors } from '../../styles/designSystem'
import { apiClient } from '../../lib/api'
import type { ConversationEvent } from '../../lib/api'
import ConversationMessageList from '../chat/ConversationMessageList'

interface SessionConversationViewerProps {
  sessionId: string
}

export function SessionConversationViewer({ sessionId }: SessionConversationViewerProps) {
  const [messages, setMessages] = useState<ConversationEvent[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const loadMessages = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await apiClient.getClaudeCodeSessionMessages(sessionId)
      setMessages(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load session messages')
    } finally {
      setLoading(false)
    }
  }, [sessionId])

  useEffect(() => {
    loadMessages()
  }, [loadMessages])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-full px-4">
        <div className="text-center">
          <p className={`text-sm text-red-600 dark:text-red-400`}>{error}</p>
          <button
            onClick={loadMessages}
            className={`mt-2 text-sm ${textColors.accent} hover:underline`}
          >
            Retry
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="h-full overflow-y-auto">
      <ConversationMessageList
        messages={messages}
        pendingMessage={null}
        onRetryMessage={() => {}}
        emptyStateMessage="No messages in this session"
        showEmptyState={messages.length === 0}
      />
    </div>
  )
}
