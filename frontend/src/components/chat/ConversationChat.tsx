import { useState, useRef, useEffect, useCallback, useMemo, forwardRef, useImperativeHandle } from 'react'
import { flushSync } from 'react-dom'
import { apiClient } from '../../lib/api'
import type { ConversationEvent, ToolCallRequest, ToolApprovalRequest } from '../../lib/api'
import { processConversationStream } from '../../lib/streamProcessor'
import PendingApprovalsList from '../approvals/common/PendingApprovalsList'
import { useApprovals, type PendingApprovalWithContext } from '../../contexts/ApprovalsContext'
import { usePendingMessages } from '../../contexts/PendingMessagesContext'
import { createConversationApprovalKey, createConversationPendingKey } from '../../utils/approvalKeys'
import ConversationMessageList from './ConversationMessageList'
import ConversationInput from './ConversationInput'
import { useUIStore } from '../../stores/uiStore'

export interface ConversationChatHandle {
  executePromptAction: (actionKey: string) => Promise<void>
}

interface ConversationChatProps {
  conversationId: number
  placeholder?: string
  emptyStateMessage?: string
  isTransitioning?: boolean
  transitionMessage?: string
}

const ConversationChat = forwardRef<ConversationChatHandle, ConversationChatProps>(({
  conversationId,
  placeholder = "Ask a question...",
  emptyStateMessage = "Start a conversation!",
  isTransitioning = false,
  transitionMessage = ''
}, ref) => {
  const [messages, setMessages] = useState<ConversationEvent[]>([])
  const [loading, setLoading] = useState(false)
  const [approvalError, setApprovalError] = useState<string | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const messagesContainerRef = useRef<HTMLDivElement>(null)
  // Track removed pending message IDs locally to immediately hide them in UI
  // Use ref for synchronous updates without waiting for re-render
  const removedPendingIdsRef = useRef<Set<string>>(new Set())
  const [renderCount, setRenderCount] = useState(0)
  // Track the last fetched conversation ID to prevent unnecessary refetches
  const lastFetchedConversationIdRef = useRef<number | null>(null)

  const { getApprovals, setApprovals, clearApprovals, executeRefreshHandlers } = useApprovals()
  const approvalKey = useMemo(() => createConversationApprovalKey(conversationId), [conversationId])
  const pendingApprovals = useMemo(() => getApprovals(approvalKey), [getApprovals, approvalKey])

  // Get UIStore methods for updating tab activity status
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

  // Get single pending message (only support one at a time), filtering out removed ones
  const pendingMessage = useMemo(() => {
    const msg = pendingMessages[0] || null
    // Filter out messages that have been marked as removed locally (check ref synchronously)
    const isRemoved = msg ? removedPendingIdsRef.current.has(msg.id) : false
    return msg && !isRemoved ? msg : null
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pendingMessages, renderCount]) // renderCount is intentionally used to force re-evaluation when we manually trigger renders

  // Helper to update current tab's activity status
  const updateCurrentTabStatus = useCallback((status: { type: 'idle' } | { type: 'new_messages'; count: number } | { type: 'agent_working' } | { type: 'action_required' }) => {
    const activeTab = getActiveTab()
    if (activeTab) {
      setTabActivityStatus(activeTab.id, status)
    }
  }, [getActiveTab, setTabActivityStatus])

  // Update tab status when loading state changes
  useEffect(() => {
    if (loading || isTransitioning) {
      updateCurrentTabStatus({ type: 'agent_working' })
    } else if (pendingApprovals.length > 0) {
      updateCurrentTabStatus({ type: 'action_required' })
    } else {
      updateCurrentTabStatus({ type: 'idle' })
    }
  }, [loading, isTransitioning, pendingApprovals.length, updateCurrentTabStatus])

  const scrollToBottom = useCallback(() => {
    if (messagesContainerRef.current) {
      messagesContainerRef.current.scrollTop = messagesContainerRef.current.scrollHeight
    }
  }, [])

  useEffect(() => {
    // Defer scroll operation until after browser finishes layout recalculation
    // This is particularly important when switching tabs, as the browser must
    // recalculate layout from display:none to display:block
    requestAnimationFrame(() => {
      scrollToBottom()
    })
  }, [messages, pendingMessage, isTransitioning, scrollToBottom])

  const fetchChatHistory = useCallback(async () => {
    // Only fetch if we haven't already fetched for this conversation
    if (lastFetchedConversationIdRef.current === conversationId) {
      return
    }

    try {
      const data = await apiClient.getConversationMessages(conversationId)
      setMessages(data)
      lastFetchedConversationIdRef.current = conversationId
    } catch (error) {
      console.error('Failed to fetch chat history:', error)
    }
  }, [conversationId])

  // Reset tracking and fetch when conversationId changes
  useEffect(() => {
    // Reset the ref when conversation changes to allow refetch
    lastFetchedConversationIdRef.current = null
    fetchChatHistory()
  }, [conversationId, fetchChatHistory])

  // Clean up removedPendingIds when pending messages are actually removed from context
  // Only remove from the local "removed" set when the message is no longer in pendingMessages
  useEffect(() => {
    const currentIds = new Set(pendingMessages.map(m => m.id))
    const removed = removedPendingIdsRef.current

    if (removed.size === 0) return

    // Remove IDs that are no longer in pending messages (context caught up)
    let changed = false
    removed.forEach(id => {
      if (!currentIds.has(id)) {
        removed.delete(id)
        changed = true
      }
    })

    // Force re-render if we cleaned up any IDs
    if (changed) {
      setRenderCount(prev => prev + 1)
    }
  }, [pendingMessages])

  // Shared callback for handling streamed events
  const handleStreamEvent = useCallback((event: ConversationEvent) => {
    setMessages(prev => [...prev, event])
  }, [])

  /**
   * Convert tool requests to approval objects with conversation context
   */
  const convertToolRequestsToApprovals = useCallback(async (toolRequests: ToolCallRequest[]): Promise<PendingApprovalWithContext[]> => {
    return toolRequests.map((request) => {
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

      const approvalObject: PendingApprovalWithContext = {
        tool_call_id: request.tool_call_id,
        tool_name: request.tool_name,
        tool_args: toolArgs,
        conversationId: conversationId // Add conversation context
      }

      return approvalObject
    })
  }, [conversationId])

  /**
   * Higher-level wrapper for stream processing that handles:
   * - Event streaming with message updates
   * - Tool request conversion to approvals
   * - Setting approvals state
   *
   * This standardizes the common pattern across all stream operations.
   *
   * @returns true if tool approvals were set, false otherwise
   */
  const processStreamWithApprovals = useCallback(async (
    stream: AsyncGenerator<ConversationEvent>,
    options?: {
      onFirstEvent?: () => void | Promise<void>
    }
  ): Promise<boolean> => {
    const { toolRequests } = await processConversationStream({
      stream,
      onFirstEvent: options?.onFirstEvent,
      onEvent: handleStreamEvent
    })

    // Handle tool approval requests if any
    if (toolRequests.length > 0) {
      const approvals = await convertToolRequestsToApprovals(toolRequests)
      setApprovals(approvalKey, approvals)
      return true
    }

    return false
  }, [handleStreamEvent, approvalKey, setApprovals, convertToolRequestsToApprovals])

  /**
   * Core logic for processing streamed conversation events.
   * Handles both regular messages and tool approval requests.
   */
  const processStreamedMessage = useCallback(async (
    messageText: string,
    messageTimestamp: string,
    pendingMessageId: string
  ) => {
    setLoading(true)

    try {
      updateMessageStatus(pendingKey, pendingMessageId, 'sent')

      // Process stream with standardized approval handling
      const hasApprovals = await processStreamWithApprovals(
        apiClient.streamConversationMessage(conversationId, {
          message: messageText
        }),
        {
          onFirstEvent: () => {
            // Remove pending message and add user message on first event
            removedPendingIdsRef.current.add(pendingMessageId)
            removeMessage(pendingKey, pendingMessageId)

            // Force immediate UI update to hide pending message
            flushSync(() => {
              setRenderCount(prev => prev + 1)
            })

            const userMessage: ConversationEvent = {
              event_type: 'message',
              role: 'user',
              text_content: messageText,
              timestamp: messageTimestamp
            }
            setMessages(prev => [...prev, userMessage])
          }
        }
      )

      // Update status to awaiting_approval if there are pending approvals
      if (hasApprovals) {
        updateMessageStatus(pendingKey, pendingMessageId, 'awaiting_approval')
      }
    } catch (error) {
      console.error('Failed to send message:', error)
      const errorMessage = error instanceof Error ? error.message : 'Failed to send message'
      updateMessageStatus(pendingKey, pendingMessageId, 'failed', errorMessage)
    } finally {
      setLoading(false)
    }
  }, [updateMessageStatus, pendingKey, processStreamWithApprovals, conversationId, removeMessage])

  const handleSendMessage = useCallback(async (messageText: string) => {
    if (loading || pendingApprovals.length > 0 || pendingMessage !== null || isTransitioning) return

    // Add message to pending state
    const pendingMessageId = addPendingMessage(pendingKey, {
      conversationId,
      text_content: messageText
    })

    await processStreamedMessage(messageText, new Date().toISOString(), pendingMessageId)
  }, [loading, pendingApprovals.length, pendingMessage, isTransitioning, pendingKey, conversationId, addPendingMessage, processStreamedMessage])

  const handleRetryMessage = useCallback((messageId: string) => {
    const pendingMsg = pendingMessages.find(msg => msg.id === messageId)
    if (!pendingMsg) return

    retryMessage(pendingKey, messageId)
    processStreamedMessage(pendingMsg.text_content, pendingMsg.timestamp, pendingMsg.id)
  }, [pendingMessages, pendingKey, retryMessage, processStreamedMessage])

  // Memoize disabled state for input
  const isInputDisabled = useMemo(
    () => loading || pendingApprovals.length > 0 || pendingMessage !== null || isTransitioning,
    [loading, pendingApprovals.length, pendingMessage, isTransitioning]
  )

  const handleToolApproval = async (approvalRequest: ToolApprovalRequest) => {
    if (pendingApprovals.length === 0) return

    setLoading(true)
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
      // Process stream with standardized approval handling
      await processStreamWithApprovals(
        apiClient.streamApproveConversationTools(conversationId, approvalRequest)
      )

      // Clear pending approvals after successful response
      clearApprovals(approvalKey)

      // Execute refresh handlers for approved tools
      if (approvedToolNames.length > 0) {
        console.log('ConversationChat: Executing refresh handlers for approved tools:', approvedToolNames)
        await executeRefreshHandlers(conversationId, approvedToolNames)
      }
    } catch (error) {
      console.error('Failed to process tool approval:', error)
      const errorMsg = error instanceof Error ? error.message : 'An unknown error occurred'
      setApprovalError(`Failed to process approval: ${errorMsg}. Please try again.`)
    } finally {
      setLoading(false)
    }
  }

  const executePromptAction = useCallback(async (actionKey: string) => {
    setLoading(true)
    try {
      // Process stream with standardized approval handling
      await processStreamWithApprovals(
        apiClient.streamPromptAction(conversationId, {
          action_key: actionKey
        })
      )
    } catch (error) {
      console.error('Failed to execute prompt action:', error)
    } finally {
      setLoading(false)
    }
  }, [conversationId, processStreamWithApprovals])

  // Expose executePromptAction via ref
  useImperativeHandle(ref, () => ({
    executePromptAction
  }), [executePromptAction])

  return (
    <div className="flex flex-col h-full">
      {/* Messages */}
      <div ref={messagesContainerRef} className="flex-1 overflow-y-auto p-4 space-y-4 min-h-0">{/* Removed floating Clear History Button - now handled externally */}

        <ConversationMessageList
          messages={messages}
          pendingMessage={pendingMessage}
          onRetryMessage={handleRetryMessage}
          emptyStateMessage={emptyStateMessage}
          showEmptyState={messages.length === 0 && !pendingMessage}
        />
        
        {/* Approval Error Message */}
        {approvalError && pendingApprovals.length > 0 && (
          <div className="mt-4 p-3 bg-red-100 dark:bg-red-900/30 border border-red-200 dark:border-red-800 rounded-lg">
            <p className="text-sm text-red-800 dark:text-red-200">{approvalError}</p>
          </div>
        )}

        {/* Pending Tool Approvals */}
        {pendingApprovals.length > 0 && (
          <div className="mt-4">
            <PendingApprovalsList
              approvals={pendingApprovals}
              onBatchApproval={handleToolApproval}
              loading={loading}
            />
          </div>
        )}
        
        {loading && (
          <div className="flex justify-start">
            <div className="bg-gray-100 dark:bg-gray-700 rounded-lg px-3 py-2 text-sm">
              <div className="flex items-center space-x-1">
                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></div>
                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.1s' }}></div>
                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
              </div>
            </div>
          </div>
        )}

        {isTransitioning && transitionMessage && (
          <div className="flex justify-start">
            <div className="bg-blue-50 dark:bg-blue-900/30 border border-blue-200 dark:border-blue-700 rounded-lg px-4 py-3">
              <div className="flex items-center space-x-3">
                <div className="flex items-center space-x-1">
                  <div className="w-2 h-2 bg-blue-500 dark:bg-blue-400 rounded-full animate-bounce"></div>
                  <div className="w-2 h-2 bg-blue-500 dark:bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: '0.1s' }}></div>
                  <div className="w-2 h-2 bg-blue-500 dark:bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
                </div>
                <span className="text-sm text-blue-700 dark:text-blue-300 font-medium">{transitionMessage}</span>
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="border-t border-gray-200 dark:border-gray-600 p-4 flex-shrink-0">
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
        {isTransitioning && (
          <p className="text-xs text-blue-600 dark:text-blue-400 mt-2">
            Running action...
          </p>
        )}
      </div>
    </div>
  )
})

export default ConversationChat