import { useState, useEffect } from 'react'
import { ChatBubbleLeftIcon, TrashIcon, InformationCircleIcon } from '@heroicons/react/24/outline'
import ConversationChat from './ConversationChat'
import ConversationModelSelector from './ConversationModelSelector'
import Button from '../ui/Button'
import Card from '../ui/Card'
import ClearChatHistoryModal from '../modals/ClearChatHistoryModal'
import SessionIdModal from '../modals/SessionIdModal'
import { textColors } from '../../styles/designSystem'
import { apiClient } from '../../lib/api'
import type { ConversationResponse } from '../../lib/api'
import { usePendingMessages } from '../../contexts/PendingMessagesContext'
import { useApprovals } from '../../contexts/ApprovalsContext'
import { createConversationPendingKey, createConversationApprovalKey } from '../../utils/approvalKeys'
import { useModal, useAsyncOperation } from '../../hooks'
import { formatAgentRoleDisplayName } from '../../utils/agentRoles'

interface AgentChatProps {
  conversationId: number | null
  placeholder?: string
  emptyStateMessage?: string
  className?: string
  padding?: 'none' | 'xs' | 'sm' | 'md' | 'lg'
  isRunningAction?: boolean
  actionMessage?: string
  onStreamingStarted?: () => void
  initialMessage?: string | null
  onInitialMessageSent?: () => void
}

const AgentChat = ({
  conversationId,
  placeholder = "Ask a question...",
  emptyStateMessage = "Start a conversation!",
  className = "flex flex-col overflow-hidden",
  padding = "xs",
  isRunningAction = false,
  actionMessage = '',
  onStreamingStarted,
  initialMessage,
  onInitialMessageSent
}: AgentChatProps) => {
  const [conversation, setConversation] = useState<ConversationResponse | null>(null)
  const [loadingConversation, setLoadingConversation] = useState(false)

  // Use new custom hooks to eliminate boilerplate
  const clearChatModal = useModal()
  const sessionIdModal = useModal()
  const { clearConversationMessages } = usePendingMessages()
  const { clearApprovals } = useApprovals()

  // Fetch conversation details to get agent role
  useEffect(() => {
    if (!conversationId) return

    const fetchConversation = async () => {
      try {
        setLoadingConversation(true)
        const data = await apiClient.getConversation(conversationId)
        setConversation(data)
      } catch (error) {
        console.error('Failed to fetch conversation:', error)
      } finally {
        setLoadingConversation(false)
      }
    }

    fetchConversation()
  }, [conversationId])

  // Format the title based on agent role
  const title = conversation
    ? formatAgentRoleDisplayName(conversation.agent_role)
    : 'Agent'

  const clearChatOperation = useAsyncOperation(
    async () => {
      if (!conversationId) return

      await apiClient.clearConversationMessages(conversationId)
      // Also clear pending messages
      const pendingKey = createConversationPendingKey(conversationId)
      clearConversationMessages(pendingKey)
      // Clear pending tool approvals
      const approvalKey = createConversationApprovalKey(conversationId)
      clearApprovals(approvalKey)
      clearChatModal.close()
      // Force refresh the conversation chat component
      window.location.reload() // Simple approach - could be optimized to just refresh the chat
    }
  )

  return (
    <>
      <Card padding={padding} className={className}>
        <div className="flex items-center justify-between mb-2 flex-shrink-0">
          <div className="flex items-center">
            <ChatBubbleLeftIcon className="w-5 h-5 mr-2 text-blue-600" />
            <h3 className={`text-lg font-medium ${textColors.primary}`}>
              {loadingConversation ? (
                <span className="text-gray-400 dark:text-gray-500">Loading...</span>
              ) : (
                title
              )}
            </h3>
          </div>
          <div className="flex items-center space-x-3">
            {conversation?.external_session_id && (
              <button
                onClick={sessionIdModal.open}
                className="p-1.5 hover:bg-gray-100 dark:hover:bg-gray-700 rounded transition-colors"
                title="View session ID"
              >
                <InformationCircleIcon className="w-5 h-5 text-gray-500 dark:text-gray-400" />
              </button>
            )}
            {conversationId && !loadingConversation && (
              <ConversationModelSelector
                conversationId={conversationId}
                onModelChange={(engine, modelId, modelName) => {
                  console.log(`Model changed: ${engine} / ${modelName} (${modelId})`)
                }}
              />
            )}
            {conversationId && (
              <Button
                variant="ghost"
                size="sm"
                onClick={clearChatModal.open}
                disabled={clearChatOperation.loading}
                className="p-2"
                title="Clear Chat History"
              >
                <TrashIcon className="w-5 h-5 text-gray-600 dark:text-gray-400" />
              </Button>
            )}
          </div>
        </div>
        <div className="flex-1 overflow-hidden">
          {conversationId ? (
            <ConversationChat
              conversationId={conversationId}
              placeholder={placeholder}
              emptyStateMessage={emptyStateMessage}
              isRunningAction={isRunningAction}
              actionMessage={actionMessage}
              onStreamingStarted={onStreamingStarted}
              initialMessage={initialMessage}
              onInitialMessageSent={onInitialMessageSent}
            />
          ) : (
            <div className="text-center text-gray-500 dark:text-gray-400 py-8">
              <p className="text-sm">No conversation started yet.</p>
              <p className="text-xs mt-2">Send your first message to begin.</p>
            </div>
          )}
        </div>
      </Card>

      {/* Clear Chat History Confirmation Modal */}
      <ClearChatHistoryModal
        isOpen={clearChatModal.isOpen}
        onClose={clearChatModal.close}
        onConfirm={clearChatOperation.execute}
        loading={clearChatOperation.loading}
      />

      {/* Session ID Modal */}
      {conversation?.external_session_id && (
        <SessionIdModal
          isOpen={sessionIdModal.isOpen}
          onClose={sessionIdModal.close}
          sessionId={conversation.external_session_id}
        />
      )}
    </>
  )
}

export default AgentChat