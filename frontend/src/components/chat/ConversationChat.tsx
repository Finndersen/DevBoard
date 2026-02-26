import { useState, useRef, useEffect, useCallback, useMemo, forwardRef, useImperativeHandle } from 'react'
import { apiClient } from '../../lib/api'
import type { ConversationEvent, ToolApprovalRequest, ToolCallRequest } from '../../lib/api'
import { useConversationStreamStore } from '../../stores/conversationStreamStore'
import { useEventHandlerRegistryForStream, useStreamCompleteHandler } from '../../hooks/useConversationEventHandlers'
import { useSendConversationMessage } from '../../hooks/useSendConversationMessage'
import PendingApprovalsList from '../approvals/common/PendingApprovalsList'
import { useApprovals, useApprovalActions, type PendingApprovalWithContext } from '../../stores/approvalsStore'
import { usePendingMessages } from '../../contexts/PendingMessagesContext'
import { createConversationApprovalKey, createConversationPendingKey } from '../../utils/approvalKeys'
import ConversationMessageList from './ConversationMessageList'
import ConversationInput from './ConversationInput'
import TodoPanel from './TodoPanel'
import { useUIStore } from '../../stores/uiStore'

const EMPTY_MESSAGES: ConversationEvent[] = []

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

  // Subscribe to store state
  // Messages are stored separately from streaming state
  const messages = useConversationStreamStore(
    state => state.conversationMessages.get(conversationId)?.messages ?? EMPTY_MESSAGES
  )
  const isStreaming = useConversationStreamStore(
    state => state.activeStreams.get(conversationId)?.isStreaming ?? false
  )
  const pendingToolRequests = useConversationStreamStore(
    state => state.activeStreams.get(conversationId)?.pendingToolRequests
  )
  const isQueued = useConversationStreamStore(
    state => state.activeStreams.get(conversationId)?.isQueued ?? false
  )

  // Use streamState only when needed (not for subscriptions)
  const streamState = useConversationStreamStore(state => state.activeStreams.get(conversationId))

  // Store actions
  const stopStream = useConversationStreamStore(state => state.stopStream)
  const approveTools = useConversationStreamStore(state => state.approveTools)
  const clearPendingToolRequests = useConversationStreamStore(state => state.clearPendingToolRequests)
  const updateEventHandlerRegistry = useConversationStreamStore(state => state.updateEventHandlerRegistry)
  const setQueued = useConversationStreamStore(state => state.setQueued)
  const setStoreMessages = useConversationStreamStore(state => state.setMessages)

  // Get event handler registry for stream processing
  const eventHandlerRegistry = useEventHandlerRegistryForStream()

  // Update the event handler registry for active streams when component mounts
  // This ensures event handlers work after navigation
  useEffect(() => {
    updateEventHandlerRegistry(conversationId, eventHandlerRegistry)
  }, [conversationId, eventHandlerRegistry, updateEventHandlerRegistry])

  // Debug: Log subscription state changes
  useEffect(() => {
    console.log('[ConversationChat] Subscription state changed:', {
      conversationId,
      hasStreamState: !!streamState,
      isStreaming,
      messageCount: messages.length,
      pendingToolRequestCount: pendingToolRequests?.length ?? 0,
      allActiveStreams: Array.from(useConversationStreamStore.getState().activeStreams.keys())
    })
  }, [conversationId, streamState, isStreaming, messages, pendingToolRequests])

  // Input state (lifted from ConversationInput for queue functionality)
  const [inputMessage, setInputMessage] = useState('')

  // Local state for non-streaming concerns
  const [approvalError, setApprovalError] = useState<string | null>(null)
  const [fetchHistoryError, setFetchHistoryError] = useState<string | null>(null)
  const messagesContainerRef = useRef<HTMLDivElement>(null)
  const isNearBottomRef = useRef(true)
  const [hasNewMessages, setHasNewMessages] = useState(false)
  const lastFetchedConversationIdRef = useRef<number | null>(null)
  const initialMessageSentRef = useRef(false)

  const approvalKey = useMemo(() => createConversationApprovalKey(conversationId), [conversationId])
  const pendingApprovals = useApprovals(approvalKey)
  const { setApprovals, clearApprovals } = useApprovalActions()

  const { setTabActivityStatus, getActiveTab } = useUIStore()

  const { getPendingMessages } = usePendingMessages()
  const pendingKey = useMemo(() => createConversationPendingKey(conversationId), [conversationId])
  const pendingMessages = useMemo(() => getPendingMessages(pendingKey), [getPendingMessages, pendingKey])

  // Use shared hook for sending messages
  // ConversationChat manages its own queueing (keeping message in input field for editing)
  // Event handler registry is registered via updateEventHandlerRegistry effect below
  const { sendMessage: sendMessageViaHook } = useSendConversationMessage({
    conversationId
  })

  const pendingMessage = useMemo(() => {
    return pendingMessages[0] || null
  }, [pendingMessages])

  // Convert tool requests from store to approval objects
  // Track if we've set approvals to avoid clearing them incorrectly
  const hasSetApprovalsRef = useRef(false)

  useEffect(() => {
    if (pendingToolRequests && pendingToolRequests.length > 0) {
      // Convert tool requests to approval objects
      const approvals: PendingApprovalWithContext[] = pendingToolRequests.map((request) => {
        // Parse tool_args if it's a string
        let toolArgs: Record<string, unknown> | null = null
        if (typeof request.tool_args === 'object' && request.tool_args !== null) {
          toolArgs = request.tool_args as Record<string, unknown>
        } else if (typeof request.tool_args === 'string') {
          try {
            toolArgs = JSON.parse(request.tool_args)
          } catch (e) {
            console.warn('ConversationChat: Failed to parse tool_args as JSON:', e)
          }
        }

        return {
          tool_call_id: request.tool_call_id,
          tool_name: request.tool_name,
          tool_args: toolArgs,
          conversationId: conversationId
        }
      })

      setApprovals(approvalKey, approvals)
      hasSetApprovalsRef.current = true
    }
    // DO NOT clear approvals when stream state disappears - approvals persist until handled
  }, [pendingToolRequests, conversationId, setApprovals, approvalKey])

  const updateCurrentTabStatus = useCallback((status: { type: 'idle' } | { type: 'new_messages'; count: number } | { type: 'agent_working' } | { type: 'action_required' }) => {
    const activeTab = getActiveTab()
    if (activeTab) {
      setTabActivityStatus(activeTab.id, status)
    }
  }, [getActiveTab, setTabActivityStatus])

  useEffect(() => {
    if (isStreaming || isRunningAction) {
      updateCurrentTabStatus({ type: 'agent_working' })
    } else if (pendingApprovals.length > 0) {
      updateCurrentTabStatus({ type: 'action_required' })
    } else {
      updateCurrentTabStatus({ type: 'idle' })
    }
  }, [isStreaming, isRunningAction, pendingApprovals.length, updateCurrentTabStatus])

  const scrollToBottom = useCallback(() => {
    if (messagesContainerRef.current) {
      messagesContainerRef.current.scrollTop = messagesContainerRef.current.scrollHeight
      isNearBottomRef.current = true
      setHasNewMessages(false)
    }
  }, [])

  const handleScroll = useCallback(() => {
    const el = messagesContainerRef.current
    if (!el) return
    const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 100
    isNearBottomRef.current = nearBottom
    if (nearBottom) {
      setHasNewMessages(false)
    }
  }, [])

  // Auto-scroll on new messages only when user is near bottom
  useEffect(() => {
    requestAnimationFrame(() => {
      if (isNearBottomRef.current) {
        scrollToBottom()
      } else {
        setHasNewMessages(true)
      }
    })
  }, [messages, scrollToBottom])

  // Always scroll to bottom for user-initiated actions
  useEffect(() => {
    requestAnimationFrame(() => {
      scrollToBottom()
    })
  }, [pendingMessage, isRunningAction, scrollToBottom])

  // Fetch history when conversation changes (but not if store already has messages)
  useEffect(() => {
    // If store already has messages, don't fetch
    if (messages.length > 0) {
      lastFetchedConversationIdRef.current = conversationId
      return
    }

    // Only fetch if we haven't already fetched for this conversation
    if (lastFetchedConversationIdRef.current === conversationId) {
      return
    }

    // Mark as fetched BEFORE starting async operation to prevent duplicate fetches
    // (React StrictMode in dev mode renders twice, causing race conditions)
    lastFetchedConversationIdRef.current = conversationId

    const fetchHistory = async () => {
      setFetchHistoryError(null)
      try {
        const data = await apiClient.getConversationMessages(conversationId)

        // Debug: Log system events (especially session_expired)
        const systemEvents = data.filter(e => e.event_type === 'system')
        if (systemEvents.length > 0) {
          console.log('[ConversationChat] System events received from history:', systemEvents)
        }

        // Separate tool requests from regular messages (like stream processor does)
        const messages: ConversationEvent[] = []
        const toolRequests: ToolCallRequest[] = []

        data.forEach(event => {
          if (event.event_type === 'tool_call_request') {
            toolRequests.push(event as ToolCallRequest)
          } else {
            messages.push(event)
          }
        })

        // Set messages in store (without tool requests)
        console.log('[ConversationChat] Setting messages from history, count:', messages.length, 'types:', messages.map(m => m.event_type))
        setStoreMessages(conversationId, messages)

        // If there are tool requests from history, convert to approvals
        if (toolRequests.length > 0) {
          const approvals: PendingApprovalWithContext[] = toolRequests.map((request) => {
            let toolArgs: Record<string, unknown> | null = null
            if (typeof request.tool_args === 'object' && request.tool_args !== null) {
              toolArgs = request.tool_args as Record<string, unknown>
            } else if (typeof request.tool_args === 'string') {
              try {
                toolArgs = JSON.parse(request.tool_args)
              } catch (e) {
                console.warn('Failed to parse tool_args from history:', e)
              }
            }

            return {
              tool_call_id: request.tool_call_id,
              tool_name: request.tool_name,
              tool_args: toolArgs,
              conversationId: conversationId
            }
          })

          setApprovals(approvalKey, approvals)
        }
      } catch (error) {
        console.error('Failed to fetch chat history:', error)
        let errorMessage = 'Failed to load conversation history'
        if (error instanceof TypeError && error.message === 'Failed to fetch') {
          errorMessage = 'Unable to connect to server. Please check if the backend is running.'
        } else if (error instanceof Error) {
          errorMessage = `Failed to load conversation history: ${error.message}`
        }
        setFetchHistoryError(errorMessage)
      }
    }

    fetchHistory()
  }, [conversationId, messages.length, setApprovals, approvalKey, setStoreMessages])

  // Public handler for new messages from input
  // If agent is busy (streaming, approvals pending, action running), queue the message
  // Otherwise, send immediately
  const handleSendMessage = useCallback(async () => {
    const messageText = inputMessage.trim()
    if (!messageText) return

    // If agent is busy, queue the message instead of sending immediately
    if (isStreaming || pendingApprovals.length > 0 || isRunningAction) {
      setQueued(conversationId, true)
      return
    }

    // Not busy - send immediately and clear input
    setInputMessage('')
    await sendMessageViaHook(messageText)
  }, [inputMessage, isStreaming, pendingApprovals.length, isRunningAction, conversationId, setQueued, sendMessageViaHook])

  // Cancel queue handler - removes queue state but keeps message in input
  const handleCancelQueue = useCallback(() => {
    setQueued(conversationId, false)
  }, [conversationId, setQueued])

  // Clear queue state when input is cleared while queued
  useEffect(() => {
    if (isQueued && !inputMessage.trim()) {
      setQueued(conversationId, false)
    }
  }, [inputMessage, isQueued, conversationId, setQueued])

  // Auto-send queued message when stream completes successfully
  useStreamCompleteHandler(useCallback(() => {
    const currentStreamState = useConversationStreamStore.getState().activeStreams.get(conversationId)

    // Only send queued message when the agent's entire turn is complete
    // (no pending tool requests that need approval first)
    if (
      currentStreamState?.isQueued &&
      inputMessage.trim() &&
      (!currentStreamState.pendingToolRequests || currentStreamState.pendingToolRequests.length === 0)
    ) {
      const messageToSend = inputMessage.trim()
      setInputMessage('')
      setQueued(conversationId, false)
      sendMessageViaHook(messageToSend)
    }
  }, [conversationId, inputMessage, setQueued, sendMessageViaHook]))

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
  }), [conversationId, pendingApprovals.length, isRunningAction, setQueued, sendMessageViaHook])

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
  }, [initialMessage, isStreaming, pendingApprovals.length, isRunningAction, conversationId, sendMessageViaHook, onInitialMessageSent])

  // Reset initial message sent ref when conversation changes
  useEffect(() => {
    initialMessageSentRef.current = false
  }, [conversationId])

  const handleToolApproval = async (approvalRequest: ToolApprovalRequest) => {
    if (pendingApprovals.length === 0) return

    setApprovalError(null)

    try {
      // Clear approvals from context first (before starting new stream)
      clearApprovals(approvalKey)

      // Clear pending tool requests from store
      clearPendingToolRequests(conversationId)

      // Use store to approve tools and continue streaming
      // Messages are preserved automatically in the store
      // Note: Tool result handlers (useToolResultHandler) in detail views handle refreshes
      // during stream processing, so no post-stream refresh is needed here
      // Event handler registry is already registered via updateEventHandlerRegistry effect
      await approveTools(conversationId, approvalRequest.approvals)
    } catch (error) {
      console.error('Failed to process tool approval:', error)
      const errorMsg = error instanceof Error ? error.message : 'An unknown error occurred'
      setApprovalError(`Failed to process approval: ${errorMsg}. Please try again.`)
    }
  }

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
              onCancelQueue={handleCancelQueue}
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
