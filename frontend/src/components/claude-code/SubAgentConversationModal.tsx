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
}

export default function SubAgentConversationModal({
  isOpen,
  onClose,
  sessionId,
  agentId,
  title,
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

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={title} maxWidth="screen" scrollable={false}>
      <div className="flex-1 min-h-0 h-[70vh]">
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
          <div className="h-full overflow-y-auto space-y-1.5 p-3">
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
