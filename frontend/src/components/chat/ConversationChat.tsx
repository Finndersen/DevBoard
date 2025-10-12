import { useState, useRef, useEffect, useCallback, useMemo } from 'react'
import { PaperAirplaneIcon } from '@heroicons/react/24/outline'
import { apiClient } from '../../lib/api'
import type { ConversationMessage, ToolCallRequest, ToolApprovalRequest } from '../../lib/api'
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
}

export default function ConversationChat({
  conversationId,
  placeholder = "Ask a question...",
  emptyStateMessage = "Start a conversation!",
  onClearHistory
}: ConversationChatProps) {
  const [messages, setMessages] = useState<ConversationMessage[]>([])
  const [newMessage, setNewMessage] = useState('')
  const [loading, setLoading] = useState(false)
  const [showClearModal, setShowClearModal] = useState(false)
  const [clearing, setClearing] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const messagesContainerRef = useRef<HTMLDivElement>(null)

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

  // Get single pending message (only support one at a time)
  const pendingMessage = pendingMessages[0] || null

  // Helper to update current tab's activity status
  const updateCurrentTabStatus = useCallback((status: { type: 'idle' } | { type: 'new_messages'; count: number } | { type: 'agent_working' } | { type: 'action_required' }) => {
    const activeTab = getActiveTab()
    if (activeTab) {
      setTabActivityStatus(activeTab.id, status)
    }
  }, [getActiveTab, setTabActivityStatus])

  // Update tab status when loading state changes
  useEffect(() => {
    if (loading) {
      updateCurrentTabStatus({ type: 'agent_working' })
    } else if (pendingApprovals.length > 0) {
      updateCurrentTabStatus({ type: 'action_required' })
    } else {
      updateCurrentTabStatus({ type: 'idle' })
    }
  }, [loading, pendingApprovals.length, updateCurrentTabStatus])

  const scrollToBottom = () => {
    if (messagesContainerRef.current) {
      messagesContainerRef.current.scrollTop = messagesContainerRef.current.scrollHeight
    }
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages, pendingMessage])

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

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!newMessage.trim() || loading || pendingApprovals.length > 0 || pendingMessage !== null) return

    const messageText = newMessage.trim()
    setNewMessage('') // Clear input immediately

    // Add message to pending state
    const pendingMessageId = addPendingMessage(pendingKey, {
      conversationId,
      text_content: messageText
    })

    setLoading(true)

    try {
      // Update status to 'sent' when making API call
      updateMessageStatus(pendingKey, pendingMessageId, 'sent')
      
      const response = await apiClient.sendConversationMessage(conversationId, {
        message: messageText
      })

      if (response.type === 'message' && response.message) {
        // Success: remove from pending and add both user and agent messages to history
        removeMessage(pendingKey, pendingMessageId)
        // Add both the user message and agent response to confirmed messages
        const userMessage: ConversationMessage = {
          id: Date.now(),
          role: 'user',
          text_content: messageText,
          timestamp: new Date().toISOString()
        }
        setMessages(prev => [...prev, userMessage, response.message!])
      } else if (response.type === 'tool_request' && response.tool_requests) {
        // Tool request: update status to awaiting_approval, DON'T remove from pending
        updateMessageStatus(pendingKey, pendingMessageId, 'awaiting_approval')
        const approvals = await convertToolRequestsToApprovals(response.tool_requests)
        setApprovals(approvalKey, approvals)
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
      
      const response = await apiClient.sendConversationMessage(conversationId, {
        message: pendingMessage.text_content
      })

      if (response.type === 'message' && response.message) {
        // Success: remove from pending and add both user and agent messages
        removeMessage(pendingKey, pendingMessage.id)
        const userMessage: ConversationMessage = {
          id: Date.now(),
          role: 'user',
          text_content: pendingMessage.text_content,
          timestamp: pendingMessage.timestamp
        }
        setMessages(prev => [...prev, userMessage, response.message!])
      } else if (response.type === 'tool_request' && response.tool_requests) {
        // Tool request: update status, DON'T remove
        updateMessageStatus(pendingKey, pendingMessage.id, 'awaiting_approval')
        const approvals = await convertToolRequestsToApprovals(response.tool_requests)
        setApprovals(approvalKey, approvals)
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
      const response = await apiClient.approveConversationTools(conversationId, approvalRequest)

      // Clear pending approvals after successful response
      clearApprovals(approvalKey)

      // Execute refresh handlers for approved tools after successful backend response
      if (approvedToolNames.length > 0) {
        console.log('ConversationChat: Executing refresh handlers for approved tools:', approvedToolNames)
        await executeRefreshHandlers(conversationId, approvedToolNames)
      }

      if (response.type === 'message' && response.message) {
        // Agent provided response after tool execution
        // If there's a pending message in awaiting_approval state, remove it and add user message
        if (pendingMessage && pendingMessage.status === 'awaiting_approval') {
          removeMessage(pendingKey, pendingMessage.id)
          const userMessage: ConversationMessage = {
            id: Date.now(),
            role: 'user',
            text_content: pendingMessage.text_content,
            timestamp: pendingMessage.timestamp
          }
          setMessages(prev => [...prev, userMessage, response.message!])
        } else {
          setMessages(prev => [...prev, response.message!])
        }
      } else if (response.type === 'tool_request' && response.tool_requests) {
        // Agent wants to use more tools
        const newApprovals = await convertToolRequestsToApprovals(response.tool_requests)
        setApprovals(approvalKey, newApprovals)
      }
    } catch (error) {
      console.error('Failed to process tool approval:', error)
      const errorMessage: ConversationMessage = {
        id: Date.now(),
        role: 'agent',
        text_content: 'Sorry, I encountered an error processing your approval. Please try again.',
        timestamp: new Date().toISOString()
      }
      setMessages(prev => [...prev, errorMessage])
      clearApprovals(approvalKey) // Clear approvals on error
    } finally {
      setLoading(false)
    }
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
            {messages.map((message) => (
              <ConversationMessageComponent
                key={message.id}
                message={message}
              />
            ))}
            
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
        
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="border-t border-gray-200 dark:border-gray-600 p-4 flex-shrink-0">
        <form onSubmit={handleSendMessage} className="flex space-x-2">
          <input
            type="text"
            value={newMessage}
            onChange={(e) => setNewMessage(e.target.value)}
            placeholder={placeholder}
            disabled={loading || pendingApprovals.length > 0 || pendingMessage !== null}
            className={`flex-1 ${standardChatInputClasses}`}
          />
          <button
            type="submit"
            disabled={!newMessage.trim() || loading || pendingApprovals.length > 0 || pendingMessage !== null}
            aria-label="Send message"
            className="inline-flex items-center px-3 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
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