import { useState, useRef, useEffect, useCallback, useMemo } from 'react'
import { flushSync } from 'react-dom'
import { apiClient } from '../../lib/api'
import type { ConversationEvent, ToolApprovalRequest, ToolCallRequest } from '../../lib/api'
import { useConversationStreamStore } from '../../stores/conversationStreamStore'
import { useEventHandlerRegistryForStream } from '../../hooks/useConversationEventHandlers'
import PendingApprovalsList from '../approvals/common/PendingApprovalsList'
import { useApprovals, useApprovalActions, type PendingApprovalWithContext } from '../../stores/approvalsStore'
import { usePendingMessages } from '../../contexts/PendingMessagesContext'
import { createConversationApprovalKey, createConversationPendingKey } from '../../utils/approvalKeys'
import ConversationMessageList from './ConversationMessageList'
import ConversationInput from './ConversationInput'
import { useUIStore } from '../../stores/uiStore'

interface ConversationChatProps {
  conversationId: number
  placeholder?: string
  emptyStateMessage?: string
  isRunningAction?: boolean
  actionMessage?: string
  onStreamingStarted?: () => void
  initialMessage?: string | null
  onInitialMessageSent?: () => void
}

const ConversationChat = ({
  conversationId,
  placeholder = "Ask a question...",
  emptyStateMessage = "Start a conversation!",
  isRunningAction = false,
  actionMessage = '',
  onStreamingStarted,
  initialMessage,
  onInitialMessageSent
}: ConversationChatProps) => {
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

  // Subscribe to streaming store state
  // IMPORTANT: Use stable references to avoid infinite loops
  const streamMessages = useConversationStreamStore(
    state => state.activeStreams.get(conversationId)?.messages
  )
  const isStreaming = useConversationStreamStore(
    state => state.activeStreams.get(conversationId)?.isStreaming ?? false
  )
  const pendingToolRequests = useConversationStreamStore(
    state => state.activeStreams.get(conversationId)?.pendingToolRequests
  )

  // Use streamState only when needed (not for subscriptions)
  const streamState = useConversationStreamStore(state => state.activeStreams.get(conversationId))

  // Store actions
  const startStream = useConversationStreamStore(state => state.startStream)
  const stopStream = useConversationStreamStore(state => state.stopStream)
  const approveTools = useConversationStreamStore(state => state.approveTools)
  const clearPendingToolRequests = useConversationStreamStore(state => state.clearPendingToolRequests)
  const updateEventHandlerRegistry = useConversationStreamStore(state => state.updateEventHandlerRegistry)

  // Get event handler registry for stream processing
  const eventHandlerRegistry = useEventHandlerRegistryForStream()

  // Update the event handler registry for active streams when component mounts
  // This ensures event handlers work after navigation
  useEffect(() => {
    if (streamState) {
      updateEventHandlerRegistry(conversationId, eventHandlerRegistry)
    }
  }, [conversationId, streamState, eventHandlerRegistry, updateEventHandlerRegistry])

  // Debug: Log subscription state changes
  useEffect(() => {
    console.log('[ConversationChat] Subscription state changed:', {
      conversationId,
      hasStreamState: !!streamState,
      isStreaming,
      messageCount: streamMessages?.length ?? 0,
      pendingToolRequestCount: pendingToolRequests?.length ?? 0,
      allActiveStreams: Array.from(useConversationStreamStore.getState().activeStreams.keys())
    })
  }, [conversationId, streamState, isStreaming, streamMessages, pendingToolRequests])

  // Local state for non-streaming concerns
  const [messages, setMessages] = useState<ConversationEvent[]>([])
  const [approvalError, setApprovalError] = useState<string | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const messagesContainerRef = useRef<HTMLDivElement>(null)
  const removedPendingIdsRef = useRef<Set<string>>(new Set())
  const [renderCount, setRenderCount] = useState(0)
  const lastFetchedConversationIdRef = useRef<number | null>(null)
  const initialMessageSentRef = useRef(false)

  const approvalKey = useMemo(() => createConversationApprovalKey(conversationId), [conversationId])
  const pendingApprovals = useApprovals(approvalKey)
  const { setApprovals, clearApprovals, executeRefreshHandlers } = useApprovalActions()

  const { setTabActivityStatus, getActiveTab } = useUIStore()

  const {
    addPendingMessage,
    updateMessageStatus,
    removeMessage,
    getPendingMessages,
    retryMessage
  } = usePendingMessages()
  const pendingKey = useMemo(() => createConversationPendingKey(conversationId), [conversationId])
  const pendingMessages = useMemo(() => getPendingMessages(pendingKey), [getPendingMessages, pendingKey])

  const pendingMessage = useMemo(() => {
    const msg = pendingMessages[0] || null
    const isRemoved = msg ? removedPendingIdsRef.current.has(msg.id) : false
    return msg && !isRemoved ? msg : null
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pendingMessages, renderCount])

  // Update messages from stream store
  useEffect(() => {
    console.log('[ConversationChat] streamMessages effect:', {
      conversationId,
      hasStreamMessages: !!streamMessages,
      messageCount: streamMessages?.length ?? 0
    })
    if (streamMessages) {
      setMessages(streamMessages)
    }
  }, [streamMessages, conversationId])

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
    }
  }, [])

  useEffect(() => {
    requestAnimationFrame(() => {
      scrollToBottom()
    })
  }, [messages, pendingMessage, isRunningAction, scrollToBottom])

  // Fetch history when conversation changes (but not if there's an active stream)
  useEffect(() => {
    // If there's an active stream with messages, don't fetch - use store messages
    if (streamMessages && streamMessages.length > 0) {
      lastFetchedConversationIdRef.current = conversationId
      return
    }

    // Only fetch if we haven't already fetched for this conversation
    if (lastFetchedConversationIdRef.current === conversationId) {
      return
    }

    const fetchHistory = async () => {
      try {
        const data = await apiClient.getConversationMessages(conversationId)

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

        // Set messages (without tool requests)
        setMessages(messages)

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

        lastFetchedConversationIdRef.current = conversationId
      } catch (error) {
        console.error('Failed to fetch chat history:', error)
      }
    }

    fetchHistory()
  }, [conversationId, streamMessages, setApprovals, approvalKey])

  useEffect(() => {
    const currentIds = new Set(pendingMessages.map(m => m.id))
    const removed = removedPendingIdsRef.current

    if (removed.size === 0) return

    let changed = false
    removed.forEach(id => {
      if (!currentIds.has(id)) {
        removed.delete(id)
        changed = true
      }
    })

    if (changed) {
      setRenderCount(prev => prev + 1)
    }
  }, [pendingMessages])

  const handleSendMessage = useCallback(async (messageText: string) => {
    if (isStreaming || pendingApprovals.length > 0 || pendingMessage !== null || isRunningAction) return

    // Add message to pending state
    const pendingMessageId = addPendingMessage(pendingKey, {
      conversationId,
      text_content: messageText
    })

    try {
      updateMessageStatus(pendingKey, pendingMessageId, 'sent')

      // Notify streaming started
      onStreamingStarted?.()

      // Remove pending message
      removedPendingIdsRef.current.add(pendingMessageId)
      removeMessage(pendingKey, pendingMessageId)

      flushSync(() => {
        setRenderCount(prev => prev + 1)
      })

      // Create user message
      const userMessage: ConversationEvent = {
        event_type: 'message',
        role: 'user',
        text_content: messageText,
        timestamp: new Date().toISOString()
      }

      // Create stream from API
      const stream = apiClient.streamConversationMessage(
        conversationId,
        { message: messageText }
      )

      // Start streaming via store - include user message in initial state
      await startStream(conversationId, stream, eventHandlerRegistry, [...messages, userMessage])
    } catch (error) {
      console.error('Failed to send message:', error)
      const errorMessage = error instanceof Error ? error.message : 'Failed to send message'
      updateMessageStatus(pendingKey, pendingMessageId, 'failed', errorMessage)
    }
  }, [
    isStreaming,
    pendingApprovals.length,
    pendingMessage,
    isRunningAction,
    pendingKey,
    conversationId,
    addPendingMessage,
    updateMessageStatus,
    removeMessage,
    onStreamingStarted,
    startStream,
    eventHandlerRegistry,
    messages
  ])

  const handleRetryMessage = useCallback(async (messageId: string) => {
    const pendingMsg = pendingMessages.find(msg => msg.id === messageId)
    if (!pendingMsg) return

    retryMessage(pendingKey, messageId)
    await handleSendMessage(pendingMsg.text_content)
  }, [pendingMessages, pendingKey, retryMessage, handleSendMessage])

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
        handleSendMessage(initialMessage)
        onInitialMessageSent?.()
      }, 0)
    }
  }, [initialMessage, isStreaming, pendingApprovals.length, isRunningAction, conversationId, handleSendMessage, onInitialMessageSent])

  // Reset initial message sent ref when conversation changes
  useEffect(() => {
    initialMessageSentRef.current = false
  }, [conversationId])

  const isInputDisabled = useMemo(
    () => isStreaming || pendingApprovals.length > 0 || pendingMessage !== null || isRunningAction,
    [isStreaming, pendingApprovals.length, pendingMessage, isRunningAction]
  )

  const handleToolApproval = async (approvalRequest: ToolApprovalRequest) => {
    if (pendingApprovals.length === 0) return

    setApprovalError(null)

    // Extract approved tool names for refresh handlers
    const approvedToolNames: string[] = []
    Object.keys(approvalRequest.approvals).forEach(toolCallId => {
      const decision = approvalRequest.approvals[toolCallId]
      if (decision.approved) {
        const approval = pendingApprovals.find(a => a.tool_call_id === toolCallId)
        if (approval) {
          approvedToolNames.push(approval.tool_name)
        }
      }
    })

    try {
      // Clear approvals from context first (before starting new stream)
      clearApprovals(approvalKey)

      // Clear pending tool requests from store
      clearPendingToolRequests(conversationId)

      // Use store to approve tools and continue streaming
      // Pass existing messages so they're preserved if we need to create a new stream
      await approveTools(conversationId, approvalRequest.approvals, eventHandlerRegistry, messages)

      // Execute refresh handlers for approved tools
      if (approvedToolNames.length > 0) {
        console.log('ConversationChat: Executing refresh handlers for approved tools:', approvedToolNames)
        await executeRefreshHandlers(conversationId, approvedToolNames)
      }
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
      <div ref={messagesContainerRef} className="flex-1 overflow-y-auto p-3 space-y-1.5 min-h-0">
        <ConversationMessageList
          messages={messages}
          pendingMessage={pendingMessage}
          onRetryMessage={handleRetryMessage}
          emptyStateMessage={emptyStateMessage}
          showEmptyState={messages.length === 0 && !pendingMessage}
        />

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

        <div ref={messagesEndRef} />
      </div>

      <div className="border-t border-gray-200 dark:border-gray-600 p-3 flex-shrink-0">
        <ConversationInput
          onSendMessage={handleSendMessage}
          disabled={isInputDisabled}
          placeholder={placeholder}
        />

        {pendingApprovals.length > 0 && (
          <p className="text-xs text-orange-600 dark:text-orange-400 mt-2">
            Please review and approve/deny the pending tool requests above before sending another message.
          </p>
        )}
        {pendingMessage && pendingMessage.status !== 'failed' && (
          <p className="text-xs text-blue-600 dark:text-blue-400 mt-2">
            Waiting for agent response...
          </p>
        )}
      </div>
    </div>
  )
}

export default ConversationChat
