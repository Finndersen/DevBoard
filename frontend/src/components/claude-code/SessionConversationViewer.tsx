import { useState, useEffect, useCallback } from 'react'
import { textColors } from '../../styles/designSystem'
import { apiClient } from '../../lib/api'
import type { ConversationEvent } from '../../lib/api'
import ConversationMessageList from '../chat/ConversationMessageList'

interface SessionConversationViewerProps {
  sessionId: string
  linkedSessionId?: string | null
}

type TabId = 'plan' | 'implementation'

function MessagePane({
  loading,
  error,
  messages,
  onRetry,
}: {
  loading: boolean
  error: string | null
  messages: ConversationEvent[]
  onRetry: () => void
}) {
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
          <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
          <button onClick={onRetry} className={`mt-2 text-sm ${textColors.accent} hover:underline`}>
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

export function SessionConversationViewer({ sessionId, linkedSessionId }: SessionConversationViewerProps) {
  const [planMessages, setPlanMessages] = useState<ConversationEvent[]>([])
  const [implMessages, setImplMessages] = useState<ConversationEvent[]>([])
  const [planLoading, setPlanLoading] = useState(false)
  const [implLoading, setImplLoading] = useState(false)
  const [planError, setPlanError] = useState<string | null>(null)
  const [implError, setImplError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<TabId>('plan')

  const loadPlanMessages = useCallback(async () => {
    setPlanLoading(true)
    setPlanError(null)
    try {
      const data = await apiClient.getClaudeCodeSessionMessages(sessionId)
      setPlanMessages(data)
    } catch (err) {
      setPlanError(err instanceof Error ? err.message : 'Failed to load session messages')
    } finally {
      setPlanLoading(false)
    }
  }, [sessionId])

  const loadImplMessages = useCallback(async () => {
    if (!linkedSessionId) return
    setImplLoading(true)
    setImplError(null)
    try {
      const data = await apiClient.getClaudeCodeSessionMessages(linkedSessionId)
      setImplMessages(data)
    } catch (err) {
      setImplError(err instanceof Error ? err.message : 'Failed to load implementation messages')
    } finally {
      setImplLoading(false)
    }
  }, [linkedSessionId])

  useEffect(() => {
    setActiveTab('plan')
    if (linkedSessionId) {
      void Promise.all([loadPlanMessages(), loadImplMessages()])
    } else {
      void loadPlanMessages()
    }
  }, [sessionId, linkedSessionId, loadPlanMessages, loadImplMessages])

  if (!linkedSessionId) {
    return (
      <MessagePane
        loading={planLoading}
        error={planError}
        messages={planMessages}
        onRetry={loadPlanMessages}
      />
    )
  }

  return (
    <div className="h-full flex flex-col overflow-hidden">
      <div className="flex border-b border-gray-200 dark:border-gray-700 shrink-0">
        <button
          onClick={() => setActiveTab('plan')}
          className={`px-4 py-2 text-sm font-medium transition-colors ${
            activeTab === 'plan'
              ? `border-b-2 border-blue-500 ${textColors.accent}`
              : `${textColors.secondary} hover:${textColors.primary}`
          }`}
        >
          Plan
        </button>
        <button
          onClick={() => setActiveTab('implementation')}
          className={`px-4 py-2 text-sm font-medium transition-colors ${
            activeTab === 'implementation'
              ? `border-b-2 border-blue-500 ${textColors.accent}`
              : `${textColors.secondary} hover:${textColors.primary}`
          }`}
        >
          Implementation
        </button>
      </div>
      <div className="flex-1 overflow-hidden">
        {activeTab === 'plan' ? (
          <MessagePane
            loading={planLoading}
            error={planError}
            messages={planMessages}
            onRetry={loadPlanMessages}
          />
        ) : (
          <MessagePane
            loading={implLoading}
            error={implError}
            messages={implMessages}
            onRetry={loadImplMessages}
          />
        )}
      </div>
    </div>
  )
}
