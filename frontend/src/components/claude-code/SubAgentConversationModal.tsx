import { useState, useEffect, useCallback } from 'react'

import type { ConversationEvent, ConversationResponse, ContextUsage } from '../../lib/api'
import { apiClient } from '../../lib/api'
import { textColors } from '../../styles/designSystem'
import ConversationMessageList from '../chat/ConversationMessageList'
import { ContextUsageBadge } from '../chat/ContextUsageDisplay'
import { Modal } from '../ui'

interface FetchMessagesResult {
  messages: ConversationEvent[]
  context_usage?: ContextUsage | null
}

interface SubAgentConversationModalProps {
  isOpen: boolean
  onClose: () => void
  fetchMessages: () => Promise<FetchMessagesResult>
  title: string
  subagentType?: string
  subtitle?: string
  workingDir?: string
  conversationId?: number
}

export default function SubAgentConversationModal({
  isOpen,
  onClose,
  fetchMessages,
  title,
  subagentType,
  subtitle,
  workingDir,
  conversationId,
}: SubAgentConversationModalProps) {
  const [messages, setMessages] = useState<ConversationEvent[]>([])
  const [contextUsage, setContextUsage] = useState<ContextUsage | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [conversationMeta, setConversationMeta] = useState<ConversationResponse | null>(null)
  const [isLive, setIsLive] = useState(false)

  const refreshMessages = useCallback(async () => {
    const data = await fetchMessages()
    setMessages(data.messages)
    setContextUsage(data.context_usage ?? null)
  }, [fetchMessages])

  const loadMessages = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      await refreshMessages()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load sub-agent conversation')
    } finally {
      setLoading(false)
    }
  }, [refreshMessages])

  useEffect(() => {
    if (isOpen) {
      loadMessages()
      if (conversationId !== undefined) {
        apiClient.getConversation(conversationId).then(setConversationMeta).catch(() => {})
        apiClient.hasActiveExecution(conversationId).then(setIsLive).catch(() => {})
      } else {
        setConversationMeta(null)
        setIsLive(false)
      }
    } else {
      setIsLive(false)
    }
  }, [isOpen, loadMessages, conversationId])

  useEffect(() => {
    if (!isLive || !isOpen || conversationId === undefined) return

    const interval = setInterval(async () => {
      await refreshMessages()
      const stillActive = await apiClient.hasActiveExecution(conversationId)
      if (!stillActive) {
        setIsLive(false)
      }
    }, 3000)

    return () => clearInterval(interval)
  }, [isLive, isOpen, conversationId, refreshMessages])

  const modalTitle = (
    <span className="flex items-center gap-2 min-w-0 w-full">
      <span className="truncate">Sub Agent: {title}</span>
      {subagentType && (
        <span className="flex-shrink-0 px-1.5 py-0.5 text-xs rounded-full bg-blue-100 text-blue-800 dark:bg-blue-900/20 dark:text-blue-400">
          {subagentType}
        </span>
      )}
      {isLive && (
        <span className="flex-shrink-0 flex items-center gap-1 px-1.5 py-0.5 text-xs rounded-full bg-green-100 text-green-800 dark:bg-green-900/20 dark:text-green-400">
          <span className="animate-pulse h-1.5 w-1.5 rounded-full bg-green-500 dark:bg-green-400" />
          Live
        </span>
      )}
      <span className="ml-auto flex-shrink-0 flex items-center gap-3">
        {subtitle && (
          <span className={`text-xs font-mono ${textColors.muted}`}>{subtitle}</span>
        )}
        {conversationMeta && (
          <>
            <span className={`text-xs font-mono ${textColors.muted}`}>Conversation: {conversationMeta.id}</span>
            {conversationMeta.external_session_id && (
              <span className={`text-xs font-mono ${textColors.muted}`}>Session: {conversationMeta.external_session_id}</span>
            )}
            {conversationMeta.model_id && (
              <span className={`text-xs font-mono ${textColors.muted}`}>Model: {conversationMeta.model_id}</span>
            )}
          </>
        )}
        {contextUsage && <ContextUsageBadge contextUsage={contextUsage} />}
      </span>
    </span>
  )

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={modalTitle} maxWidth="screen">
      <div className="min-h-[50vh]">
        {loading ? (
          <div className="flex items-center justify-center h-full">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
          </div>
        ) : error ? (
          <div className="flex items-center justify-center h-full px-4">
            <div className="text-center">
              <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
              <button onClick={loadMessages} className={`mt-2 text-sm ${textColors.accent} hover:underline`}>
                Retry
              </button>
            </div>
          </div>
        ) : (
          <div className="space-y-1.5 p-3">
            <ConversationMessageList
              messages={messages}
              pendingMessage={null}
              onRetryMessage={() => {}}
              emptyStateMessage="No messages in this sub-agent session"
              showEmptyState={messages.length === 0}
              workingDir={workingDir}
            />
          </div>
        )}
      </div>
    </Modal>
  )
}
