import { useState, useRef, useEffect } from 'react'
import { PaperAirplaneIcon } from '@heroicons/react/24/outline'
import { apiClient } from '../lib/api'
import type { ConversationMessage, ToolCallRequest, ToolApprovalRequest, PendingApproval, DocumentEdit } from '../lib/api'
import PendingApprovalsList from './PendingApprovalsList'

interface ChatProps {
  projectId: number
}

export default function Chat({ projectId }: ChatProps) {
  const [messages, setMessages] = useState<ConversationMessage[]>([])
  const [newMessage, setNewMessage] = useState('')
  const [loading, setLoading] = useState(false)
  const [pendingApprovals, setPendingApprovals] = useState<PendingApproval[]>([])
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  useEffect(() => {
    fetchChatHistory()
  }, [projectId])

  const fetchChatHistory = async () => {
    try {
      const data = await apiClient.getProjectAgentMessages(projectId)
      setMessages(data)
    } catch (error) {
      console.error('Failed to fetch chat history:', error)
    }
  }

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!newMessage.trim() || loading || pendingApprovals.length > 0) return

    // Add user message to chat immediately
    const userMessage: ConversationMessage = {
      id: Date.now(), // temporary ID
      role: 'user',
      text_content: newMessage.trim(),
      timestamp: new Date().toISOString()
    }

    setMessages(prev => [...prev, userMessage])
    setNewMessage('')
    setLoading(true)

    try {
      const response = await apiClient.sendProjectAgentMessage(projectId, {
        message: userMessage.text_content
      })

      if (response.type === 'message' && response.message) {
        // Agent provided a direct response
        setMessages(prev => [...prev, response.message!])
        setPendingApprovals([]) // Clear any existing approvals
      } else if (response.type === 'tool_request' && response.tool_requests) {
        // Agent wants to use tools - convert to PendingApproval format
        const approvals = await convertToolRequestsToApprovals(response.tool_requests)
        setPendingApprovals(approvals)
      }
    } catch (error) {
      console.error('Failed to send message:', error)
      const errorMessage: ConversationMessage = {
        id: Date.now() + 1,
        role: 'agent',
        text_content: 'Sorry, I encountered an error processing your request. Please try again.',
        timestamp: new Date().toISOString()
      }
      setMessages(prev => [...prev, errorMessage])
    } finally {
      setLoading(false)
    }
  }

  const convertToolRequestsToApprovals = async (toolRequests: ToolCallRequest[]): Promise<PendingApproval[]> => {
    return toolRequests.map((request) => {
      let documentType: string | null = null
      let edits: DocumentEdit[] | null = null
      let reasoning: string | null = null

      // Check if this is a document editing tool
      if (request.tool_name.startsWith('edit_')) {
        documentType = request.tool_name.replace('edit_', '')
        
        // Extract edits and reasoning from tool_args
        if (typeof request.tool_args === 'object' && request.tool_args !== null) {
          edits = request.tool_args.edits || null
          reasoning = request.tool_args.reasoning || null
        }
      }

      return {
        tool_call_id: request.tool_call_id,
        tool_name: request.tool_name,
        document_type: documentType,
        edits: edits,
        diff_preview: null, // Backend doesn't provide this yet
        reasoning: reasoning
      }
    })
  }

  const handleToolApproval = async (approvalRequest: ToolApprovalRequest) => {
    if (pendingApprovals.length === 0) return

    setLoading(true)

    try {
      const response = await apiClient.approveProjectAgentTools(projectId, approvalRequest)

      // Clear pending approvals first
      setPendingApprovals([])

      if (response.type === 'message' && response.message) {
        // Agent provided response after tool execution
        setMessages(prev => [...prev, response.message!])
      } else if (response.type === 'tool_request' && response.tool_requests) {
        // Agent wants to use more tools
        const newApprovals = await convertToolRequestsToApprovals(response.tool_requests)
        setPendingApprovals(newApprovals)
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
      setPendingApprovals([]) // Clear approvals on error
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex flex-col h-full">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 min-h-0">
        {messages.length === 0 ? (
          <div className="text-center text-gray-500 dark:text-gray-400 py-8">
            <p className="text-sm">Ask me anything about this project!</p>
            <p className="text-xs mt-2">I can help with code analysis, documentation, and project insights.</p>
          </div>
        ) : (
          messages.map((message) => (
            <div
              key={message.id}
              className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              <div
                className={`max-w-[80%] rounded-lg px-3 py-2 text-sm ${
                  message.role === 'user'
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-100 dark:bg-gray-700 text-gray-900 dark:text-white'
                }`}
              >
                <div className="whitespace-pre-wrap">{message.text_content}</div>
                <div className={`text-xs mt-1 opacity-70 ${
                  message.role === 'user' ? 'text-blue-100' : 'text-gray-500 dark:text-gray-400'
                }`}>
                  {new Date(message.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </div>
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
            placeholder="Ask a question about this project..."
            disabled={loading || pendingApprovals.length > 0}
            className="flex-1 px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent dark:bg-gray-700 dark:text-white disabled:opacity-50 disabled:cursor-not-allowed"
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
    </div>
  )
}