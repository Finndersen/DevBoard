import type { ReactNode } from 'react'
import { useState, useEffect, useCallback } from 'react'
import { ClipboardDocumentListIcon, CodeBracketIcon } from '@heroicons/react/24/outline'
import { textColors } from '../../styles/designSystem'
import { apiClient } from '../../lib/api'
import type { ConversationEvent } from '../../lib/api'
import ConversationMessageList from '../chat/ConversationMessageList'

interface SessionConversationViewerProps {
  sessionId: string
  linkedSessionId?: string | null
  highlightUuids?: string[]
  onActiveTabChange?: (tab: TabId) => void
  tabBarRight?: ReactNode
}

export type TabId = 'plan' | 'implementation'

function MessagePane({
  loading,
  error,
  messages,
  onRetry,
  highlightUuids,
  sessionId,
}: {
  loading: boolean
  error: string | null
  messages: ConversationEvent[]
  onRetry: () => void
  highlightUuids?: string[]
  sessionId?: string
}) {
  const [currentMatchIndex, setCurrentMatchIndex] = useState(0)

  useEffect(() => {
    setCurrentMatchIndex(0)
  }, [highlightUuids])

  useEffect(() => {
    if (!highlightUuids?.length) return
    const uuid = highlightUuids[currentMatchIndex]
    if (uuid) {
      document.getElementById(`msg-${uuid}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' })
    }
  }, [highlightUuids, currentMatchIndex])

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
    <div className="relative h-full">
      {highlightUuids && highlightUuids.length > 0 && (
        <div className="absolute top-2 right-2 z-10 flex items-center gap-2 bg-amber-50 dark:bg-amber-900/40 border border-amber-300 dark:border-amber-600 rounded-lg px-3 py-1.5 shadow-md text-xs">
          <span className={textColors.secondary}>{currentMatchIndex + 1} of {highlightUuids.length} matches</span>
          <button
            onClick={() => setCurrentMatchIndex(i => Math.max(0, i - 1))}
            disabled={currentMatchIndex === 0}
            className="p-0.5 disabled:opacity-40 hover:text-amber-700 dark:hover:text-amber-300"
            aria-label="Previous match"
          >‹</button>
          <button
            onClick={() => setCurrentMatchIndex(i => Math.min(highlightUuids.length - 1, i + 1))}
            disabled={currentMatchIndex === highlightUuids.length - 1}
            className="p-0.5 disabled:opacity-40 hover:text-amber-700 dark:hover:text-amber-300"
            aria-label="Next match"
          >›</button>
        </div>
      )}
      <div className="h-full overflow-y-auto space-y-1.5 p-3">
        <ConversationMessageList
          messages={messages}
          pendingMessage={null}
          onRetryMessage={() => {}}
          emptyStateMessage="No messages in this session"
          showEmptyState={messages.length === 0}
          highlightUuids={highlightUuids}
          sessionId={sessionId}
        />
      </div>
    </div>
  )
}

export function SessionConversationViewer({ sessionId, linkedSessionId, highlightUuids, onActiveTabChange, tabBarRight }: SessionConversationViewerProps) {
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
    onActiveTabChange?.('plan')
    if (linkedSessionId) {
      void Promise.all([loadPlanMessages(), loadImplMessages()])
    } else {
      void loadPlanMessages()
    }
  }, [sessionId, linkedSessionId, loadPlanMessages, loadImplMessages]) // eslint-disable-line react-hooks/exhaustive-deps

  if (!linkedSessionId) {
    return (
      <div className="h-full flex flex-col overflow-hidden">
        {tabBarRight && (
          <div className="flex items-center border-b border-gray-200 dark:border-white/[0.08] shrink-0 px-4 py-2">
            <div className="ml-auto flex items-center">
              {tabBarRight}
            </div>
          </div>
        )}
        <div className="flex-1 overflow-hidden">
          <MessagePane
            loading={planLoading}
            error={planError}
            messages={planMessages}
            onRetry={loadPlanMessages}
            highlightUuids={highlightUuids}
            sessionId={sessionId}
          />
        </div>
      </div>
    )
  }

  return (
    <div className="h-full flex flex-col overflow-hidden">
      <div className="flex items-center border-b border-gray-200 dark:border-white/[0.08] shrink-0">
        <button
          onClick={() => { setActiveTab('plan'); onActiveTabChange?.('plan') }}
          className={`px-4 py-2 text-sm font-medium transition-colors ${
            activeTab === 'plan'
              ? `border-b-2 border-blue-500 ${textColors.accent}`
              : `${textColors.secondary} hover:${textColors.primary}`
          }`}
        >
          <ClipboardDocumentListIcon className="w-4 h-4 inline-block mr-1.5 -mt-0.5" />
          Plan
        </button>
        <button
          onClick={() => { setActiveTab('implementation'); onActiveTabChange?.('implementation') }}
          className={`px-4 py-2 text-sm font-medium transition-colors ${
            activeTab === 'implementation'
              ? `border-b-2 border-blue-500 ${textColors.accent}`
              : `${textColors.secondary} hover:${textColors.primary}`
          }`}
        >
          <CodeBracketIcon className="w-4 h-4 inline-block mr-1.5 -mt-0.5" />
          Implementation
        </button>
        {tabBarRight && (
          <div className="ml-auto pr-4 flex items-center">
            {tabBarRight}
          </div>
        )}
      </div>
      <div className="flex-1 overflow-hidden">
        {activeTab === 'plan' ? (
          <MessagePane
            loading={planLoading}
            error={planError}
            messages={planMessages}
            onRetry={loadPlanMessages}
            highlightUuids={highlightUuids}
            sessionId={sessionId}
          />
        ) : (
          <MessagePane
            loading={implLoading}
            error={implError}
            messages={implMessages}
            onRetry={loadImplMessages}
            sessionId={linkedSessionId}
          />
        )}
      </div>
    </div>
  )
}
