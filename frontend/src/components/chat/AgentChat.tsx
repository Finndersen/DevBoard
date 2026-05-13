import { useState, useEffect, useCallback, forwardRef, useRef, useImperativeHandle } from 'react'
import { ChatBubbleLeftIcon, TrashIcon, PlusIcon, MagnifyingGlassCircleIcon } from '@heroicons/react/24/outline'
import ConversationChat, { type ConversationChatHandle } from './ConversationChat'
import RunningIndicator from './RunningIndicator'
import Button from '../ui/Button'
import Card from '../ui/Card'
import ClearChatHistoryModal from '../modals/ClearChatHistoryModal'
import AgentInspectorModal from '../modals/AgentInspectorModal'
import { textColors } from '../../styles/designSystem'
import { apiClient } from '../../lib/api'
import type { ConversationResponse } from '../../lib/api'
import { usePendingMessages } from '../../contexts/PendingMessagesContext'
import { useApprovalActions } from '../../stores/approvalsStore'
import { createConversationPendingKey, createConversationApprovalKey } from '../../utils/approvalKeys'
import { useModal, useAsyncOperation } from '../../hooks'
import { useSystemEventHandler } from '../../hooks/useConversationEventHandlers'
import type { SystemEvent } from '../../lib/api'
import { formatAgentRoleDisplayName } from '../../utils/agentRoles'
import ContextUsageDisplay from './ContextUsageDisplay'

interface AgentChatProps {
  conversationId: number | null
  emptyStateMessage?: string
  className?: string
  padding?: 'none' | 'xs' | 'sm' | 'md' | 'lg'
  isRunningAction?: boolean
  actionMessage?: string
  workingDir?: string
  onConversationReset?: (newConversationId: number) => void
  conversationSelector?: React.ReactNode
  onNewConversation?: () => void
}

/** Handle exposed by AgentChat ref - extends ConversationChatHandle with session state */
export interface AgentChatHandle extends ConversationChatHandle {
  /** Whether the session has expired */
  sessionExpired: boolean
}

const AgentChat = forwardRef<AgentChatHandle, AgentChatProps>(({
  conversationId,
  emptyStateMessage = "Start a conversation!",
  className = "flex flex-col overflow-hidden",
  padding = "xs",
  isRunningAction = false,
  actionMessage = '',
  workingDir,
  onConversationReset,
  conversationSelector,
  onNewConversation,
}, ref) => {
  const [conversation, setConversation] = useState<ConversationResponse | null>(null)
  const [sessionExpired, setSessionExpired] = useState(false)
  const conversationChatRef = useRef<ConversationChatHandle>(null)

  // Forward the ref to ConversationChat and expose sessionExpired state
  useImperativeHandle(ref, () => ({
    sendMessage: (message: string) => {
      conversationChatRef.current?.sendMessage(message)
    },
    get inputMessage() {
      return conversationChatRef.current?.inputMessage ?? ''
    },
    setInputMessage: (text: string) => {
      conversationChatRef.current?.setInputMessage(text)
    },
    handleSendMessage: () => {
      conversationChatRef.current?.handleSendMessage()
    },
    get isQueued() {
      return conversationChatRef.current?.isQueued ?? false
    },
    stopStream: () => {
      conversationChatRef.current?.stopStream()
    },
    get sessionExpired() {
      return sessionExpired
    }
  }), [sessionExpired])
  const [loadingConversation, setLoadingConversation] = useState(false)

  // Use new custom hooks to eliminate boilerplate
  const clearChatModal = useModal()
  const inspectorModal = useModal()
  const { clearConversationMessages } = usePendingMessages()
  const { clearApprovals } = useApprovalActions()

  // Handle session ID updates from system events
  const sessionEventHandler = useCallback((event: SystemEvent) => {
    // Handle session_expired - clear session ID
    if (event.sub_type === 'session_expired') {
      setConversation(prev => prev ? { ...prev, external_session_id: null } : null)
      setSessionExpired(true)
      return
    }

    // Handle conversation_updated with external_session_id change
    if (event.sub_type === 'conversation_updated' &&
        event.data?.conversation_id === conversationId &&
        'external_session_id' in (event.data?.updated_fields ?? {})) {
      const newSessionId = event.data?.updated_fields?.external_session_id
      setConversation(prev => prev ? { ...prev, external_session_id: newSessionId } : null)
    }
  }, [conversationId])

  useSystemEventHandler(sessionEventHandler)

  // Fetch conversation details to get agent role
  useEffect(() => {
    if (!conversationId) return

    setSessionExpired(false)

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

      const result = await apiClient.resetConversation(conversationId)
      // Clear pending messages for old conversation
      const pendingKey = createConversationPendingKey(conversationId)
      clearConversationMessages(pendingKey)
      // Clear pending tool approvals for old conversation
      const approvalKey = createConversationApprovalKey(conversationId)
      clearApprovals(approvalKey)
      clearChatModal.close()
      // Notify parent of the new conversation ID
      onConversationReset?.(result.new_conversation_id)
    }
  )

  return (
    <>
      <Card padding={padding} className={className}>
        <div className="relative flex items-center justify-between mb-2 flex-shrink-0">
          <div className="flex items-center gap-3">
            <ChatBubbleLeftIcon className="w-5 h-5 text-blue-600 shrink-0" />
            <h3 className={`text-lg font-medium ${textColors.primary}`}>
              {loadingConversation ? (
                <span className="text-gray-400 dark:text-gray-500">Loading...</span>
              ) : (
                title
              )}
            </h3>
            {conversationId && (
              <button
                onClick={inspectorModal.open}
                className="p-1.5 hover:bg-gray-100 dark:hover:bg-gray-700 rounded transition-colors"
                title="Agent Inspector"
              >
                <MagnifyingGlassCircleIcon className="w-5 h-5 text-gray-500 dark:text-gray-400" />
              </button>
            )}
            {conversationId && <RunningIndicator conversationId={conversationId} />}
          </div>
          {(conversationSelector || onNewConversation) && (
            <div className="absolute inset-x-0 flex justify-center items-center pointer-events-none">
              <div className="flex items-center space-x-2 pointer-events-auto">
                {conversationSelector}
                {onNewConversation && (
                  <button
                    onClick={onNewConversation}
                    className="p-1.5 hover:bg-gray-100 dark:hover:bg-gray-700 rounded transition-colors"
                    title="New Conversation"
                  >
                    <PlusIcon className="w-5 h-5 text-gray-500 dark:text-gray-400" />
                  </button>
                )}
              </div>
            </div>
          )}
          <div className="flex items-center space-x-3">
            {conversationId && !loadingConversation && (
              <ContextUsageDisplay conversationId={conversationId} />
            )}
            {conversationId && !conversationSelector && (
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
              ref={conversationChatRef}
              conversationId={conversationId}
              emptyStateMessage={emptyStateMessage}
              isRunningAction={isRunningAction}
              actionMessage={actionMessage}
              workingDir={workingDir}
              engine={conversation?.engine}
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
      {!conversationSelector && (
        <ClearChatHistoryModal
          isOpen={clearChatModal.isOpen}
          onClose={clearChatModal.close}
          onConfirm={clearChatOperation.execute}
          loading={clearChatOperation.loading}
        />
      )}

      {/* Agent Inspector Modal */}
      {conversationId && (
        <AgentInspectorModal
          isOpen={inspectorModal.isOpen}
          onClose={inspectorModal.close}
          conversationId={conversationId}
          engine={conversation?.engine}
          modelId={conversation?.model_id}
          externalSessionId={conversation?.external_session_id}
        />
      )}
    </>
  )
})

AgentChat.displayName = 'AgentChat'

export default AgentChat