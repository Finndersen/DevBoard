import { useState, useRef, useEffect, useCallback, useMemo } from 'react'
import { flushSync } from 'react-dom'
import { PaperAirplaneIcon } from '@heroicons/react/24/outline'
import { apiClient } from '../../lib/api'
import type { ConversationEvent, ToolCallRequest, ToolApprovalRequest, ToolResult } from '../../lib/api'
import PendingApprovalsList from '../approvals/common/PendingApprovalsList'
import { useApprovals, type PendingApprovalWithContext } from '../../contexts/ApprovalsContext'
import { usePendingMessages, type PendingMessage } from '../../contexts/PendingMessagesContext'
import { createConversationApprovalKey, createConversationPendingKey } from '../../utils/approvalKeys'
import { standardChatInputClasses } from '../../styles/inputStyles'
import ConversationMessageComponent from './ConversationMessage'
import PendingMessageComponent from './PendingMessage'
import Button from '../ui/Button'
import Modal from '../ui/Modal'
import { useUIStore } from '../../stores/uiStore'

interface ConversationChatProps {
  conversationId: number
  placeholder?: string
  emptyStateMessage?: string
  onClearHistory?: () => void
  showClearButton?: boolean
  isTransitioning?: boolean
  transitionMessage?: string
}

const MAX_TEXTAREA_ROWS = 10

export default function ConversationChat({
  conversationId,
  placeholder = "Ask a question...",
  emptyStateMessage = "Start a conversation!",
  onClearHistory,
  isTransitioning = false,
  transitionMessage = ''
}: ConversationChatProps) {
  const [messages, setMessages] = useState<ConversationEvent[]>([])
  const [newMessage, setNewMessage] = useState('')
  const [loading, setLoading] = useState(false)
  const [showClearModal, setShowClearModal] = useState(false)
  const [clearing, setClearing] = useState(false)
  const [approvalError, setApprovalError] = useState<string | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const messagesContainerRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  // Track removed pending message IDs locally to immediately hide them in UI
  // Use ref for synchronous updates without waiting for re-render
  const removedPendingIdsRef = useRef<Set<string>>(new Set())
  const [renderCount, setRenderCount] = useState(0)

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
    retryMessage,
    clearConversationMessages
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

  const scrollToBottom = () => {
    if (messagesContainerRef.current) {
      messagesContainerRef.current.scrollTop = messagesContainerRef.current.scrollHeight
    }
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages, pendingMessage, isTransitioning])

  // Auto-resize textarea based on content
  const adjustTextareaHeight = useCallback(() => {
    const textarea = textareaRef.current
    if (!textarea) return

    // Reset height to calculate scrollHeight properly
    textarea.style.height = 'auto'

    // Calculate the number of lines based on line height
    const lineHeight = parseInt(window.getComputedStyle(textarea).lineHeight)
    const maxHeight = lineHeight * MAX_TEXTAREA_ROWS

    // Set height to scrollHeight (content height) but cap at maxHeight
    const newHeight = Math.min(textarea.scrollHeight, maxHeight)
    textarea.style.height = `${newHeight}px`
  }, [])

  useEffect(() => {
    adjustTextareaHeight()
  }, [newMessage, adjustTextareaHeight])

  const fetchChatHistory = useCallback(async () => {
    try {
      const data = await apiClient.getConversationMessages(conversationId)
      setMessages(data)
    } catch (error) {
      console.error('Failed to fetch chat history:', error)
    }
  }, [conversationId])

  useEffect(() => {
    fetchChatHistory()
  }, [fetchChatHistory])

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

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!newMessage.trim() || loading || pendingApprovals.length > 0 || pendingMessage !== null || isTransitioning) return

    const messageText = newMessage.trim()
    setNewMessage('') // Clear input immediately

    // Reset textarea height after clearing
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
    }

    // Add message to pending state
    const pendingMessageId = addPendingMessage(pendingKey, {
      conversationId,
      text_content: messageText
    })

    setLoading(true)

    try {
      // Update status to 'sent' when making API call
      updateMessageStatus(pendingKey, pendingMessageId, 'sent')

      const events = await apiClient.sendConversationMessage(conversationId, {
        message: messageText
      })

      // Check if we have any tool_call_request events (need approval)
      const toolRequests = events.filter(e => e.event_type === 'tool_call_request') as ToolCallRequest[]

      if (toolRequests.length > 0) {
        // Tool request: update status to awaiting_approval, DON'T remove from pending
        updateMessageStatus(pendingKey, pendingMessageId, 'awaiting_approval')
        const approvals = await convertToolRequestsToApprovals(toolRequests)
        setApprovals(approvalKey, approvals)
      } else {
        // Success: remove from pending FIRST, then add both user and agent messages to history
        // Mark as removed locally for immediate UI update (synchronous ref update)
        removedPendingIdsRef.current.add(pendingMessageId)
        removeMessage(pendingKey, pendingMessageId)

        // Use flushSync to force synchronous state updates and immediate re-render
        flushSync(() => {
          setRenderCount(prev => prev + 1) // Force re-render to reflect removal immediately
        })

        // Now add the confirmed messages after pending is hidden
        const userMessage: ConversationEvent = {
          event_type: 'message',
          role: 'user',
          text_content: messageText,
          timestamp: new Date().toISOString()
        }
        setMessages(prev => [...prev, userMessage, ...events])
      }
    } catch (error) {
      console.error('Failed to send message:', error)
      // Update pending message status to failed
      const errorMessage = error instanceof Error ? error.message : 'Failed to send message'
      updateMessageStatus(pendingKey, pendingMessageId, 'failed', errorMessage)
    } finally {
      setLoading(false)
    }
  }

  const handleRetryMessage = (messageId: string) => {
    const pendingMessage = pendingMessages.find(msg => msg.id === messageId)
    if (!pendingMessage) return

    // Retry the message
    retryMessage(pendingKey, messageId)
    
    // Resend using the same flow as regular send
    resendPendingMessage(pendingMessage)
  }

  const resendPendingMessage = async (pendingMessage: PendingMessage) => {
    setLoading(true)

    try {
      updateMessageStatus(pendingKey, pendingMessage.id, 'sent')

      const events = await apiClient.sendConversationMessage(conversationId, {
        message: pendingMessage.text_content
      })

      // Check if we have any tool_call_request events (need approval)
      const toolRequests = events.filter(e => e.event_type === 'tool_call_request') as ToolCallRequest[]

      if (toolRequests.length > 0) {
        // Tool request: update status, DON'T remove
        updateMessageStatus(pendingKey, pendingMessage.id, 'awaiting_approval')
        const approvals = await convertToolRequestsToApprovals(toolRequests)
        setApprovals(approvalKey, approvals)
      } else {
        // Success: remove from pending FIRST, then add both user and agent messages
        // Mark as removed locally for immediate UI update (synchronous ref update)
        removedPendingIdsRef.current.add(pendingMessage.id)
        removeMessage(pendingKey, pendingMessage.id)

        // Use flushSync to force synchronous state updates and immediate re-render
        flushSync(() => {
          setRenderCount(prev => prev + 1) // Force re-render to reflect removal immediately
        })

        // Now add the confirmed messages after pending is hidden
        const userMessage: ConversationEvent = {
          event_type: 'message',
          role: 'user',
          text_content: pendingMessage.text_content,
          timestamp: pendingMessage.timestamp
        }
        setMessages(prev => [...prev, userMessage, ...events])
      }
    } catch (error) {
      console.error('Failed to retry message:', error)
      const errorMessage = error instanceof Error ? error.message : 'Failed to send message'
      updateMessageStatus(pendingKey, pendingMessage.id, 'failed', errorMessage)
    } finally {
      setLoading(false)
    }
  }

  const convertToolRequestsToApprovals = async (toolRequests: ToolCallRequest[]): Promise<PendingApprovalWithContext[]> => {
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
  }

  const handleToolApproval = async (approvalRequest: ToolApprovalRequest) => {
    if (pendingApprovals.length === 0) return

    setLoading(true)
    setApprovalError(null) // Clear any previous errors

    // Extract tool names from pending approvals before clearing them (for refresh handlers)
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
      const events = await apiClient.approveConversationTools(conversationId, approvalRequest)

      // Clear pending approvals after successful response
      clearApprovals(approvalKey)

      // Execute refresh handlers for approved tools after successful backend response
      if (approvedToolNames.length > 0) {
        console.log('ConversationChat: Executing refresh handlers for approved tools:', approvedToolNames)
        await executeRefreshHandlers(conversationId, approvedToolNames)
      }

      // Check if we have any tool_call_request events (agent wants to use more tools)
      const toolRequests = events.filter(e => e.event_type === 'tool_call_request') as ToolCallRequest[]

      if (toolRequests.length > 0) {
        // Agent wants to use more tools
        const newApprovals = await convertToolRequestsToApprovals(toolRequests)
        setApprovals(approvalKey, newApprovals)
      } else {
        // Agent provided response after tool execution
        // If there's a pending message, remove it FIRST and add user message
        // (The pending message is the original user message that triggered the tool request)
        if (pendingMessage) {
          // Mark as removed locally for immediate UI update (synchronous ref update)
          removedPendingIdsRef.current.add(pendingMessage.id)
          removeMessage(pendingKey, pendingMessage.id)

          // Use flushSync to force synchronous state updates and immediate re-render
          flushSync(() => {
            setRenderCount(prev => prev + 1) // Force re-render to reflect removal immediately
          })

          // Now add the confirmed messages after pending is hidden
          const userMessage: ConversationEvent = {
            event_type: 'message',
            role: 'user',
            text_content: pendingMessage.text_content,
            timestamp: pendingMessage.timestamp
          }
          setMessages(prev => [...prev, userMessage, ...events])
        } else {
          setMessages(prev => [...prev, ...events])
        }
      }
    } catch (error) {
      console.error('Failed to process tool approval:', error)
      // Set error message to display above approvals, keep approvals visible
      const errorMsg = error instanceof Error ? error.message : 'An unknown error occurred'
      setApprovalError(`Failed to process approval: ${errorMsg}. Please try again.`)
      // DON'T clear approvals - keep them visible so user can retry
    } finally {
      setLoading(false)
    }
  }

  // Helper to find matching tool result for a tool call
  // Searches for the NEXT ToolResult with matching tool_call_id that comes AFTER the tool call
  // This is important for virtual tool calls which may have non-unique tool_call_ids
  const findToolResult = (toolCallId: string, toolCallIndex: number): ToolResult | undefined => {
    // Search only messages that come after the tool call
    for (let i = toolCallIndex + 1; i < messages.length; i++) {
      const msg = messages[i]
      if (msg.event_type === 'tool_result' && msg.tool_call_id === toolCallId) {
        return msg as ToolResult
      }
    }
    return undefined
  }

  const handleClearHistory = async () => {
    if (onClearHistory) {
      // Use external clear handler if provided
      onClearHistory()
      return
    }

    // Fallback to internal clear handler
    setClearing(true)
    try {
      const response = await apiClient.clearConversationMessages(conversationId)
      console.log('Clear history response:', response)
      setMessages([])
      // Also clear pending messages
      clearConversationMessages(pendingKey)
      // Clear pending tool approvals
      clearApprovals(approvalKey)
      setShowClearModal(false)
    } catch (error) {
      console.error('Failed to clear chat history:', error)
    } finally {
      setClearing(false)
    }
  }

  return (
    <div className="flex flex-col h-full">
      {/* Messages */}
      <div ref={messagesContainerRef} className="flex-1 overflow-y-auto p-4 space-y-4 min-h-0">{/* Removed floating Clear History Button - now handled externally */}
        
        {messages.length === 0 && !pendingMessage ? (
          <div className="text-center text-gray-500 dark:text-gray-400 py-8">
            <p className="text-sm">{emptyStateMessage}</p>
            <p className="text-xs mt-2">I can help with code analysis, documentation, and project insights.</p>
          </div>
        ) : (
          <>
            {/* Render confirmed messages */}
            {messages.map((message, index) => {
              // For tool calls, find the matching result
              const toolResult = message.event_type === 'tool_call'
                ? findToolResult(message.tool_call_id, index)
                : undefined

              return (
                <ConversationMessageComponent
                  key={`${index}-${message.timestamp}`}
                  message={message}
                  toolResult={toolResult}
                />
              )
            })}
            
            {/* Render pending message if exists */}
            {pendingMessage && (
              <PendingMessageComponent
                key={pendingMessage.id}
                message={pendingMessage}
                onRetry={handleRetryMessage}
              />
            )}
          </>
        )}
        
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
        <form onSubmit={handleSendMessage} className="flex space-x-2 items-end">
          <textarea
            ref={textareaRef}
            value={newMessage}
            onChange={(e) => setNewMessage(e.target.value)}
            onKeyDown={(e) => {
              // Submit on Enter (without Shift)
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                handleSendMessage(e)
              }
            }}
            placeholder={placeholder}
            disabled={loading || pendingApprovals.length > 0 || pendingMessage !== null || isTransitioning}
            className={`flex-1 resize-none overflow-y-auto ${standardChatInputClasses}`}
            rows={1}
          />
          <button
            type="submit"
            disabled={!newMessage.trim() || loading || pendingApprovals.length > 0 || pendingMessage !== null || isTransitioning}
            aria-label="Send message"
            className="inline-flex items-center px-3 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed flex-shrink-0"
          >
            <PaperAirplaneIcon className="w-4 h-4" />
          </button>
        </form>

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

      {/* Clear History Confirmation Modal */}
      {showClearModal && (
        <Modal 
          isOpen={showClearModal}
          onClose={() => setShowClearModal(false)}
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
                onClick={() => setShowClearModal(false)}
                disabled={clearing}
              >
                Cancel
              </Button>
              <Button 
                variant="primary" 
                onClick={handleClearHistory}
                loading={clearing}
              >
                Clear History
              </Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  )
}