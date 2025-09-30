import { ChatBubbleLeftIcon, TrashIcon } from '@heroicons/react/24/outline'
import ConversationChat from './ConversationChat'
import Button from './ui/Button'
import Card from './ui/Card'
import Modal from './ui/Modal'
import { textColors } from '../styles/designSystem'
import { apiClient } from '../lib/api'
import { usePendingMessages } from '../contexts/PendingMessagesContext'
import { createConversationPendingKey } from '../utils/approvalKeys'
import { useModal, useAsyncOperation } from '../hooks'

interface AgentChatProps {
  title: string
  conversationId: number | null
  placeholder?: string
  emptyStateMessage?: string
  rightHeaderContent?: React.ReactNode
  className?: string
  padding?: 'none' | 'xs' | 'sm' | 'md' | 'lg'
}

export default function AgentChat({
  title,
  conversationId,
  placeholder = "Ask a question...",
  emptyStateMessage = "Start a conversation!",
  rightHeaderContent,
  className = "flex flex-col overflow-hidden",
  padding = "xs"
}: AgentChatProps) {
  // Use new custom hooks to eliminate boilerplate
  const clearChatModal = useModal()
  const { clearConversationMessages } = usePendingMessages()

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
            <h3 className={`text-lg font-medium ${textColors.primary}`}>{title}</h3>
          </div>
          <div className="flex items-center space-x-3">
            {rightHeaderContent}
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