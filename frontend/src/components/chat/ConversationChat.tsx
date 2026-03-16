import { useRef, useEffect, useCallback, useMemo, forwardRef, useImperativeHandle } from 'react'
import { useConversationStreamStore } from '../../stores/conversationStreamStore'
import { useSendConversationMessage } from '../../hooks/useSendConversationMessage'
import PendingApprovalsList from '../approvals/common/PendingApprovalsList'
import { usePendingMessages } from '../../contexts/PendingMessagesContext'
import { createConversationPendingKey } from '../../utils/approvalKeys'
import ConversationMessageList from './ConversationMessageList'
import ConversationInput from './ConversationInput'
import TodoPanel from './TodoPanel'
import { useStreamSubscription } from './hooks/useStreamSubscription'
import { useToolApprovalLogic } from './hooks/useToolApprovalLogic'
import { useConversationHistory } from './hooks/useConversationHistory'
import { useAutoScroll } from './hooks/useAutoScroll'
import { useMessageQueueing } from './hooks/useMessageQueueing'
import { useViewContext } from '../../contexts/ViewContext'

/**
 * Handle exposed by ConversationChat ref for external message submission.
 * Allows external components to send messages through the same flow as the input field.
 */
export interface ConversationChatHandle {
  /** Send a message as if it was typed into the input and submitted */
  sendMessage: (message: string) => void
}

interface ConversationChatProps {
  conversationId: number
  placeholder?: string
  emptyStateMessage?: string
  isRunningAction?: boolean
  actionMessage?: string
  initialMessage?: string | null
  onInitialMessageSent?: () => void
  codebaseLocalPath?: string
  isDisabled?: boolean
  engine?: string
}

const ConversationChat = forwardRef<ConversationChatHandle, ConversationChatProps>(({
  conversationId,
  placeholder = "Ask a question...",
  emptyStateMessage = "Start a conversation!",
  isRunningAction = false,
  actionMessage = '',
  initialMessage,
  onInitialMessageSent,
  codebaseLocalPath,
  isDisabled = false,
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
    isStreaming,
    pendingToolRequests,
    isQueued,
    stopStream,
    approveTools,
    clearPendingToolRequests,
    setQueued,
    setStoreMessages,
  } = useStreamSubscription(conversationId)

  const {
    approvalKey,
    pendingApprovals,
    setApprovals,
    approvalError,
    handleToolApproval,
  } = useToolApprovalLogic(conversationId, pendingToolRequests, clearPendingToolRequests, approveTools)

  const { fetchHistoryError, lastFetchedConversationIdRef } = useConversationHistory(
    conversationId, messages, setStoreMessages, setApprovals, approvalKey
  )

  const initialMessageSentRef = useRef(false)

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

  const { viewType, entityId } = useViewContext()

  const { inputMessage, setInputMessage, handleSendMessage } = useMessageQueueing(
    conversationId, isStreaming, pendingApprovals, isRunningAction, isQueued, setQueued, sendMessageViaHook, viewType, entityId
  )

  // Retry handler - bypasses guards, reuses existing pending message
  const handleRetryMessage = useCallback(async (messageId: string) => {
    const pendingMsg = pendingMessages.find(msg => msg.id === messageId)
    if (!pendingMsg) return

    // Send directly with existing pending message ID
    // Status will be updated to 'sent' inside the hook
    await sendMessageViaHook(pendingMsg.text_content, pendingMsg.id)
  }, [pendingMessages, sendMessageViaHook])

  // Expose sendMessage method via ref for external callers (e.g., review comments)
  // This goes through the same flow as typing in the input - queueing if busy
  useImperativeHandle(ref, () => ({
    sendMessage: (message: string) => {
      const messageText = message.trim()
      if (!messageText) return

      // Check current busy state from store (not stale closure)
      const currentStreamState = useConversationStreamStore.getState().activeStreams.get(conversationId)
      const currentIsStreaming = currentStreamState?.isStreaming ?? false
      const currentIsQueued = currentStreamState?.isQueued ?? false

      // If agent is busy or already has a queued message, queue this one
      if (currentIsStreaming || pendingApprovals.length > 0 || isRunningAction || currentIsQueued) {
        // Set the message in input field and mark as queued
        setInputMessage(messageText)
        setQueued(conversationId, true)
        return
      }

      // Not busy - send immediately
      sendMessageViaHook(messageText)
    }
  }), [conversationId, pendingApprovals.length, isRunningAction, setQueued, sendMessageViaHook, setInputMessage])

  // Auto-send initial message when provided (e.g., from task creation with description)
  useEffect(() => {
    // Only send if:
    // 1. We have an initial message
    // 2. Haven't sent it yet
    // 3. Not currently streaming
    // 4. No pending approvals
    // 5. Conversation history has been fetched (lastFetchedConversationIdRef is set)
    if (
      initialMessage &&
      !initialMessageSentRef.current &&
      !isStreaming &&
      pendingApprovals.length === 0 &&
      !isRunningAction &&
      lastFetchedConversationIdRef.current === conversationId
    ) {
      initialMessageSentRef.current = true
      // Use setTimeout to ensure this runs after render cycle
      setTimeout(() => {
        sendMessageViaHook(initialMessage)
        onInitialMessageSent?.()
      }, 0)
    }
  }, [initialMessage, isStreaming, pendingApprovals.length, isRunningAction, conversationId, sendMessageViaHook, onInitialMessageSent, lastFetchedConversationIdRef])

  // Reset initial message sent ref when conversation changes
  useEffect(() => {
    initialMessageSentRef.current = false
  }, [conversationId])

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
          codebaseLocalPath={codebaseLocalPath}
        />

        {fetchHistoryError && (
          <div className="mt-2 p-2.5 bg-red-100 dark:bg-red-900/30 border border-red-200 dark:border-red-800 rounded-lg">
            <p className="text-sm text-red-800 dark:text-red-200">{fetchHistoryError}</p>
          </div>
        )}

        {approvalError && pendingApprovals.length > 0 && (
          <div className="mt-2 p-2.5 bg-red-100 dark:bg-red-900/30 border border-red-200 dark:border-red-800 rounded-lg">
            <p className="text-sm text-red-800 dark:text-red-200">{approvalError}</p>
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
            <div className="bg-gray-100 dark:bg-gray-700 rounded-lg px-3 py-1.5 text-sm">
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
            <div className="bg-blue-50 dark:bg-blue-900/30 border border-blue-200 dark:border-blue-700 rounded-lg px-3 py-2">
              <div className="flex items-center space-x-3">
                <div className="flex items-center space-x-1">
                  <div className="w-2 h-2 bg-blue-500 dark:bg-blue-400 rounded-full animate-bounce"></div>
                  <div className="w-2 h-2 bg-blue-500 dark:bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: '0.1s' }}></div>
                  <div className="w-2 h-2 bg-blue-500 dark:bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
                </div>
                <span className="text-sm text-blue-700 dark:text-blue-300 font-medium">{actionMessage}</span>
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

      <div className="border-t border-gray-200 dark:border-gray-600 p-3 flex-shrink-0">
        {isDisabled ? (
          <div className="text-center text-gray-500 dark:text-gray-400 py-3 text-sm">
            Chat disabled — task is complete
          </div>
        ) : (
          <>
            <ConversationInput
              value={inputMessage}
              onChange={setInputMessage}
              onSendMessage={handleSendMessage}
              placeholder={placeholder}
              isStreaming={isStreaming}
              onStopStream={() => stopStream(conversationId)}
              isQueued={isQueued}
            />

            {pendingMessage && pendingMessage.status !== 'failed' && (
              <p className="text-xs text-blue-600 dark:text-blue-400 mt-2">
                Waiting for agent response...
              </p>
            )}
          </>
        )}
      </div>
    </div>
  )
})

ConversationChat.displayName = 'ConversationChat'

export default ConversationChat
