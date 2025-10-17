import { useState, useEffect } from 'react'
import { ChatBubbleLeftIcon, TrashIcon } from '@heroicons/react/24/outline'
import ConversationChat from './ConversationChat'
import ConversationModelSelector from './ConversationModelSelector'
import Button from '../ui/Button'
import Card from '../ui/Card'
import Modal from '../ui/Modal'
import { textColors } from '../../styles/designSystem'
import { apiClient } from '../../lib/api'
import type { ConversationResponse } from '../../lib/api'
import { usePendingMessages } from '../../contexts/PendingMessagesContext'
import { createConversationPendingKey } from '../../utils/approvalKeys'
import { useModal, useAsyncOperation } from '../../hooks'
import { formatAgentRoleDisplayName } from '../../utils/agentRoles'

interface AgentChatProps {
  conversationId: number | null
  placeholder?: string
  emptyStateMessage?: string
  className?: string
  padding?: 'none' | 'xs' | 'sm' | 'md' | 'lg'
  isTransitioning?: boolean
  transitionMessage?: string
}

export default function AgentChat({
  conversationId,
  placeholder = "Ask a question...",
  emptyStateMessage = "Start a conversation!",
  className = "flex flex-col overflow-hidden",
  padding = "xs",
  isTransitioning = false,
  transitionMessage = ''
}: AgentChatProps) {
  const [conversation, setConversation] = useState<ConversationResponse | null>(null)
  const [loadingConversation, setLoadingConversation] = useState(false)

  // Use new custom hooks to eliminate boilerplate
  const clearChatModal = useModal()
  const { clearConversationMessages } = usePendingMessages()

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
              isTransitioning={isTransitioning}
              transitionMessage={transitionMessage}
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
      <Modal 
        isOpen={clearChatModal.isOpen}
        onClose={clearChatModal.close}
        title="Clear Chat History"
        maxWidth="sm"
      >
        <div className="space-y-4">
          <p className="text-gray-600 dark:text-gray-300">
            Are you sure you want to clear all conversation history? This action cannot be undone.
          </p>
          
          <div className="flex justify-end space-x-3">
            <Button 
              variant="secondary" 
              onClick={clearChatModal.close}
              disabled={clearChatOperation.loading}
            >
              Cancel
            </Button>
            <Button 
              variant="primary" 
              onClick={clearChatOperation.execute}
              loading={clearChatOperation.loading}
            >
              Clear History
            </Button>
          </div>
        </div>
      </Modal>
    </>
  )
}