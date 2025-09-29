import { useState, useRef, useEffect, useCallback } from 'react'
import { PaperAirplaneIcon, ArrowPathIcon } from '@heroicons/react/24/outline'
import { apiClient } from '../lib/api'
import type { ConversationMessage, ToolCallRequest, ToolApprovalRequest, PendingApproval, DocumentEdit } from '../lib/api'
import PendingApprovalsList from './PendingApprovalsList'
import { useApprovals } from '../contexts/ApprovalsContext'
import { usePendingMessages, type PendingMessage } from '../contexts/PendingMessagesContext'
import { createConversationApprovalKey, createConversationPendingKey } from '../utils/approvalKeys'
import { standardChatInputClasses } from '../styles/inputStyles'
import Button from './ui/Button'
import Modal from './ui/Modal'

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
  
  const { getApprovals, setApprovals, clearApprovals } = useApprovals()
  const approvalKey = createConversationApprovalKey(conversationId)
  const pendingApprovals = getApprovals(approvalKey)
  
  const { 
    addPendingMessage, 
    updateMessageStatus, 
    removeMessage, 
    getPendingMessages, 
    retryMessage,
    clearConversationMessages
  } = usePendingMessages()
  const pendingKey = createConversationPendingKey(conversationId)
  const pendingMessages = getPendingMessages(pendingKey)
  
  // Debug logging
  useEffect(() => {
    console.log('ConversationChat: approvalKey:', approvalKey)
    console.log('ConversationChat: pendingApprovals:', pendingApprovals)
    console.log('ConversationChat: pendingMessages:', pendingMessages)
  }, [approvalKey, pendingApprovals, pendingMessages])

  // Combine backend messages with pending messages and sort by timestamp
  const allMessages = [...messages, ...pendingMessages.map(pendingMsg => ({
    id: pendingMsg.id,
    role: 'user' as const,
    text_content: pendingMsg.text_content,
    timestamp: pendingMsg.timestamp,
    isPending: true,
    pendingStatus: pendingMsg.status,
    pendingError: pendingMsg.error,
    pendingRetryCount: pendingMsg.retryCount
  } as ConversationMessage & {
    isPending: boolean
    pendingStatus: 'pending' | 'sent' | 'failed'
    pendingError?: string
    pendingRetryCount: number
  }))].sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime())

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [allMessages])

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
    if (!newMessage.trim() || loading || pendingApprovals.length > 0) return

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
        // Success: remove from pending and add agent response to regular messages
        removeMessage(pendingKey, pendingMessageId)
        setMessages(prev => [...prev, response.message!])
      } else if (response.type === 'tool_request' && response.tool_requests) {
        // Tool request: remove from pending and handle approvals
        removeMessage(pendingKey, pendingMessageId)
        const approvals = await convertToolRequestsToApprovals(response.tool_requests)
        console.log('ConversationChat: Setting approvals:', approvals)
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
        removeMessage(pendingKey, pendingMessage.id)
        setMessages(prev => [...prev, response.message!])
      } else if (response.type === 'tool_request' && response.tool_requests) {
        removeMessage(pendingKey, pendingMessage.id)
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

  const convertToolRequestsToApprovals = async (toolRequests: ToolCallRequest[]): Promise<PendingApproval[]> => {
    return toolRequests.map((request) => {
      console.log('ConversationChat: Converting tool request:', request)
      console.log('ConversationChat: tool_args type:', typeof request.tool_args)
      console.log('ConversationChat: tool_args content:', request.tool_args)
      
      let documentType: string | null = null
      let edits: DocumentEdit[] | null = null
      let reasoning: string | null = null

      // Check if this is a document editing tool
      if (request.tool_name.startsWith('edit_')) {
        documentType = request.tool_name.replace('edit_', '')
        
        // Extract edits and reasoning from tool_args
        if (typeof request.tool_args === 'object' && request.tool_args !== null) {
          console.log('ConversationChat: Extracting from object tool_args:', request.tool_args)
          edits = request.tool_args.edits || null
          reasoning = request.tool_args.reasoning || null
        } else if (typeof request.tool_args === 'string') {
          console.log('ConversationChat: Parsing string tool_args:', request.tool_args)
          try {
            const parsed = JSON.parse(request.tool_args)
            console.log("ConversationChat: Parsed JSON successfully:", parsed)
            console.log("ConversationChat: Parsed JSON keys:", Object.keys(parsed))
            edits = parsed.edits || null
            reasoning = parsed.reasoning || null
            console.log("ConversationChat: Extracted edits:", edits)
            console.log("ConversationChat: Extracted reasoning:", reasoning)
          } catch (e) {
            console.warn('ConversationChat: Failed to parse tool_args as JSON:', e)
          }
        }
      }

      const approvalObject = {
        tool_call_id: request.tool_call_id,
        tool_name: request.tool_name,
        document_type: documentType,
        edits: edits,
        diff_preview: null, // Backend doesn't provide this yet
        reasoning: reasoning
      }
      
      console.log("ConversationChat: Final approval object:", approvalObject)
      return approvalObject
    })
  }

  const handleToolApproval = async (approvalRequest: ToolApprovalRequest) => {
    if (pendingApprovals.length === 0) return

    setLoading(true)

    try {
      const response = await apiClient.approveConversationTools(conversationId, approvalRequest)

      // Clear pending approvals first
      clearApprovals(approvalKey)

      if (response.type === 'message' && response.message) {
        // Agent provided response after tool execution
        setMessages(prev => [...prev, response.message!])
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
      <div className="flex-1 overflow-y-auto p-4 space-y-4 min-h-0">{/* Removed floating Clear History Button - now handled externally */}
        
        {allMessages.length === 0 ? (
          <div className="text-center text-gray-500 dark:text-gray-400 py-8">
            <p className="text-sm">{emptyStateMessage}</p>
            <p className="text-xs mt-2">I can help with code analysis, documentation, and project insights.</p>
          </div>
        ) : (
          allMessages.map((message) => (
            <div
              key={message.id}
              className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              <div className={`max-w-[80%] flex flex-col ${message.role === 'user' ? 'items-end' : 'items-start'}`}>
                <div
                  className={`rounded-lg px-3 py-2 text-sm ${
                    message.role === 'user'
                      ? (message.isPending && message.pendingStatus === 'failed')
                        ? 'bg-red-500 text-white'
                        : (message.isPending && message.pendingStatus === 'pending')
                        ? 'bg-blue-400 text-white opacity-75'
                        : 'bg-blue-600 text-white'
                      : 'bg-gray-100 dark:bg-gray-700 text-gray-900 dark:text-white'
                  }`}
                >
                  <div className="whitespace-pre-wrap">{message.text_content}</div>
                  <div className={`text-xs mt-1 opacity-70 flex items-center justify-between ${
                    message.role === 'user' ? 'text-blue-100' : 'text-gray-500 dark:text-gray-400'
                  }`}>
                    <span>
                      {new Date(message.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </span>
                    {message.isPending && (
                      <span className="ml-2 flex items-center">
                        {message.pendingStatus === 'pending' && '⏳'}
                        {message.pendingStatus === 'sent' && '📤'}
                        {message.pendingStatus === 'failed' && '⚠️'}
                      </span>
                    )}
                  </div>
                </div>
                
                {/* Retry button for failed messages */}
                {message.isPending && message.pendingStatus === 'failed' && (
                  <div className="mt-1 flex items-center space-x-2">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleRetryMessage(message.id)}
                      disabled={loading}
                      className="text-xs px-2 py-1 h-auto text-red-600 hover:text-red-700 dark:text-red-400 dark:hover:text-red-300"
                    >
                      <ArrowPathIcon className="w-3 h-3 mr-1" />
                      Retry
                    </Button>
                    {message.pendingError && (
                      <span className="text-xs text-red-600 dark:text-red-400">
                        {message.pendingError}
                      </span>
                    )}
                  </div>
                )}
              </div>
            </div>
          ))
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
            disabled={loading || pendingApprovals.length > 0}
            className={`flex-1 ${standardChatInputClasses}`}
          />
          <button
            type="submit"
            disabled={!newMessage.trim() || loading || pendingApprovals.length > 0}
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