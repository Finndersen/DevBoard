import { useRef, useEffect, useCallback, useMemo, forwardRef, useImperativeHandle } from 'react'
import { useSendConversationMessage } from '../../hooks/useSendConversationMessage'
import PendingApprovalsList from '../approvals/common/PendingApprovalsList'
import { usePendingMessages } from '../../contexts/PendingMessagesContext'
import { createConversationPendingKey } from '../../utils/approvalKeys'
import ConversationMessageList from './ConversationMessageList'
import TodoPanel from './TodoPanel'
import { useStreamSubscription } from './hooks/useStreamSubscription'
import { useToolApprovalLogic } from './hooks/useToolApprovalLogic'
import { useConversationHistory } from './hooks/useConversationHistory'
import { useAutoScroll } from './hooks/useAutoScroll'
import Alert from '../ui/Alert'
import { surfaces, statusColors } from '../../styles/designSystem'

export interface ConversationChatHandle {
  /** Send a message directly (bypasses queuing — for programmatic/workflow sends) */
  sendMessage: (message: string) => void
  /** Stop the current stream */
  stopStream: () => void
}

interface ConversationChatProps {
  conversationId: number
  emptyStateMessage?: string
  isRunningAction?: boolean
  actionMessage?: string
  workingDir?: string
  engine?: string
}

const ConversationChat = forwardRef<ConversationChatHandle, ConversationChatProps>(({
  conversationId,
  emptyStateMessage = "Start a conversation!",
  isRunningAction = false,
  actionMessage = '',
  workingDir,
  engine
}, ref) => {
  // Track conversationId changes for debugging
  const prevConversationIdRef = useRef(conversationId)
  useEffect(() => {
    if (prevConversationIdRef.current !== conversationId) {
      console.log('[ConversationChat] conversationId CHANGED:', {
        from: prevConversationIdRef.current,
        to: conversationId
      })
      prevConversationIdRef.current = conversationId
    }
  }, [conversationId])

  const {
    messages,
    historyLoaded,
    isStreaming,
    pendingToolRequests,
    stopStream,
    approveTools,
    clearPendingToolRequests,
    setStoreMessages,
  } = useStreamSubscription(conversationId)

  const {
    approvalKey,
    pendingApprovals,
    setApprovals,
    approvalError,
    handleToolApproval,
  } = useToolApprovalLogic(conversationId, pendingToolRequests, clearPendingToolRequests, approveTools)

  const { fetchHistoryError } = useConversationHistory(
    conversationId, messages, historyLoaded, setStoreMessages, setApprovals, approvalKey
  )

  const { getPendingMessages } = usePendingMessages()
  const pendingKey = useMemo(() => createConversationPendingKey(conversationId), [conversationId])
  const pendingMessages = useMemo(() => getPendingMessages(pendingKey), [getPendingMessages, pendingKey])

  const { sendMessage: sendMessageViaHook } = useSendConversationMessage({
    conversationId
  })

  const pendingMessage = useMemo(() => {
    return pendingMessages[0] || null
  }, [pendingMessages])

  const { messagesContainerRef, handleScroll, scrollToBottom, hasNewMessages } = useAutoScroll(
    messages, pendingMessage, isRunningAction
  )

  // Retry handler - bypasses guards, reuses existing pending message
  const handleRetryMessage = useCallback(async (messageId: string) => {
    const pendingMsg = pendingMessages.find(msg => msg.id === messageId)
    if (!pendingMsg) return

    // Send directly with existing pending message ID
    // Status will be updated to 'sent' inside the hook
    await sendMessageViaHook(pendingMsg.text_content, pendingMsg.id)
  }, [pendingMessages, sendMessageViaHook])

  useImperativeHandle(ref, () => ({
    sendMessage: (message: string) => {
      const messageText = message.trim()
      if (!messageText) return
      sendMessageViaHook(messageText)
    },
    stopStream: () => stopStream(conversationId)
  }), [conversationId, sendMessageViaHook, stopStream])


  // Cleanup: stop stream if component unmounts while streaming
  // Note: This won't actually stop background streams in the store,
  // but it marks this component as no longer interested
  useEffect(() => {
    return () => {
      // Only stop if we're the active viewer and stream is still running
      // Background streams should continue if user just navigated away
      // This is a placeholder - actual cleanup logic may vary based on requirements
    }
  }, [conversationId, stopStream])

  return (
    <div className="flex flex-col h-full">
      {engine && (
        <TodoPanel conversationId={conversationId} engine={engine} />
      )}
      <div className="relative flex-1 min-h-0">
      <div ref={messagesContainerRef} onScroll={handleScroll} className="h-full overflow-y-auto p-3 space-y-1.5">
        <ConversationMessageList
          messages={messages}
          pendingMessage={pendingMessage}
          onRetryMessage={handleRetryMessage}
          emptyStateMessage={emptyStateMessage}
          showEmptyState={messages.length === 0 && !pendingMessage && !fetchHistoryError}
          workingDir={workingDir}
        />

        {fetchHistoryError && (
          <div className="mt-2">
            <Alert variant="error">{fetchHistoryError}</Alert>
          </div>
        )}

        {approvalError && pendingApprovals.length > 0 && (
          <div className="mt-2">
            <Alert variant="error">{approvalError}</Alert>
          </div>
        )}

        {pendingApprovals.length > 0 && (
          <div className="mt-2">
            <PendingApprovalsList
              approvals={pendingApprovals}
              onBatchApproval={handleToolApproval}
              loading={isStreaming}
            />
          </div>
        )}

        {isStreaming && (
          <div className="flex justify-start">
            <div className={`${surfaces.sunken} rounded-lg px-3 py-1.5 text-sm`}>
              <div className="flex items-center space-x-1">
                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></div>
                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.1s' }}></div>
                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
              </div>
            </div>
          </div>
        )}

        {isRunningAction && actionMessage && (
          <div className="flex justify-start">
            <div className={`${statusColors.info.bg} border ${statusColors.info.border} rounded-lg px-3 py-2`}>
              <div className="flex items-center space-x-3">
                <div className="flex items-center space-x-1">
                  <div className="w-2 h-2 bg-blue-500 dark:bg-blue-400 rounded-full animate-bounce"></div>
                  <div className="w-2 h-2 bg-blue-500 dark:bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: '0.1s' }}></div>
                  <div className="w-2 h-2 bg-blue-500 dark:bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
                </div>
                <span className={`text-sm ${statusColors.info.text} font-medium`}>{actionMessage}</span>
              </div>
            </div>
          </div>
        )}
      </div>

        {hasNewMessages && (
          <button
            onClick={scrollToBottom}
            className="absolute bottom-2 left-1/2 -translate-x-1/2 flex items-center gap-1.5 px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white text-xs font-medium rounded-full shadow-lg transition-colors cursor-pointer z-10"
          >
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-3.5 h-3.5">
              <path fillRule="evenodd" d="M10 3a.75.75 0 01.75.75v10.638l3.96-4.158a.75.75 0 111.08 1.04l-5.25 5.5a.75.75 0 01-1.08 0l-5.25-5.5a.75.75 0 111.08-1.04l3.96 4.158V3.75A.75.75 0 0110 3z" clipRule="evenodd" />
            </svg>
            New messages
          </button>
        )}
      </div>
    </div>
  )
})

ConversationChat.displayName = 'ConversationChat'

export default ConversationChat
