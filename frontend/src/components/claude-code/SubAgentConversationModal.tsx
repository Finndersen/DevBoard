import { useState, useEffect, useCallback } from 'react'

import type { ConversationEvent } from '../../lib/api'
import { apiClient } from '../../lib/api'
import { textColors } from '../../styles/designSystem'
import ConversationMessageList from '../chat/ConversationMessageList'
import { Modal } from '../ui'

interface SubAgentConversationModalProps {
  isOpen: boolean
  onClose: () => void
  sessionId: string
  agentId: string
  title: string
  subagentType?: string
}

export default function SubAgentConversationModal({
  isOpen,
  onClose,
  sessionId,
  agentId,
  title,
  subagentType,
}: SubAgentConversationModalProps) {
  const [messages, setMessages] = useState<ConversationEvent[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const loadMessages = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await apiClient.getClaudeCodeSubAgentMessages(sessionId, agentId)
      setMessages(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load sub-agent conversation')
    } finally {
      setLoading(false)
    }
  }, [sessionId, agentId])

  useEffect(() => {
    if (isOpen && agentId) {
      loadMessages()
    }
  }, [isOpen, agentId, loadMessages])

  const modalTitle = (
    <span className="flex items-center gap-2 min-w-0 w-full">
      <span className="truncate">Sub Agent: {title}</span>
      {subagentType && (
        <span className="flex-shrink-0 px-1.5 py-0.5 text-xs rounded-full bg-blue-100 text-blue-800 dark:bg-blue-900/20 dark:text-blue-400">
          {subagentType}
        </span>
      )}
      <span className="ml-auto flex-shrink-0 text-xs text-gray-400 dark:text-gray-500 font-mono">
        {agentId}
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
            />
          </div>
        )}
      </div>
    </Modal>
  )
}
