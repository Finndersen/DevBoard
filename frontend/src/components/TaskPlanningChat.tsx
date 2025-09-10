import { useState, useRef, useEffect } from 'react'
import { PaperAirplaneIcon, CheckIcon, XMarkIcon } from '@heroicons/react/24/outline'
import { apiClient } from '../lib/api'
import type { 
  ConversationMessageResponse, 
  PendingApproval, 
  MessageRequest,
  ToolApprovalRequest,
  ToolApprovalDecision
} from '../lib/api'

interface TaskPlanningChatProps {
  taskId: number
}

export default function TaskPlanningChat({ taskId }: TaskPlanningChatProps) {
  const [messages, setMessages] = useState<ConversationMessageResponse[]>([])
  const [newMessage, setNewMessage] = useState('')
  const [loading, setLoading] = useState(false)
  const [pendingApprovals, setPendingApprovals] = useState<PendingApproval[]>([])
  const [approvalFeedback, setApprovalFeedback] = useState<Record<string, string>>({})
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!newMessage.trim() || loading) return

    const messageRequest: MessageRequest = {
      message: newMessage.trim()
    }

    setNewMessage('')
    setLoading(true)

    try {
      const response = await apiClient.sendTaskConversationMessage(taskId, messageRequest)
      
      // Update messages
      setMessages(response.messages)
      
      // Update pending approvals
      setPendingApprovals(response.pending_approvals || [])
      
      // Clear approval feedback
      setApprovalFeedback({})
      
    } catch (error) {
      console.error('Failed to send message:', error)
      // TODO: Show error to user
    } finally {
      setLoading(false)
    }
  }

  const handleToolApproval = async (toolCallId: string, approved: boolean) => {
    if (!pendingApprovals.length) return

    const approvals: Record<string, ToolApprovalDecision> = {}
    
    // For now, handle single approval at a time
    approvals[toolCallId] = {
      approved,
      feedback: approvalFeedback[toolCallId] || undefined
    }

    const approvalRequest: ToolApprovalRequest = { approvals }

    setLoading(true)

    try {
      const response = await apiClient.approveTaskTools(taskId, approvalRequest)
      
      // Update messages with continuation
      setMessages(prev => [...prev, ...response.messages])
      
      // Clear pending approvals (should be empty after approval)
      setPendingApprovals([])
      setApprovalFeedback({})
      
    } catch (error) {
      console.error('Failed to process tool approval:', error)
      // TODO: Show error to user
    } finally {
      setLoading(false)
    }
  }

  const updateApprovalFeedback = (toolCallId: string, feedback: string) => {
    setApprovalFeedback(prev => ({
      ...prev,
      [toolCallId]: feedback
    }))
  }

  return (
    <div className="flex flex-col h-full">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 ? (
          <div className="text-center text-gray-500 dark:text-gray-400 py-8">
            <p className="text-sm">Welcome to the Task Planning Agent!</p>
            <p className="text-xs mt-2">I can help you create and refine task specifications and implementation plans.</p>
          </div>
        ) : (
          messages.map((message) => (
            <div
              key={message.id}
              className={`flex ${message.message_type === 'request' ? 'justify-end' : 'justify-start'}`}
            >
              <div
                className={`max-w-[80%] rounded-lg px-3 py-2 text-sm ${
                  message.message_type === 'request'
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-100 dark:bg-gray-700 text-gray-900 dark:text-white'
                }`}
              >
                <div className="whitespace-pre-wrap">{message.text_content}</div>
                <div className={`text-xs mt-1 opacity-70 ${
                  message.message_type === 'request' ? 'text-blue-100' : 'text-gray-500 dark:text-gray-400'
                }`}>
                  {new Date(message.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </div>
              </div>
            </div>
          ))
        )}
        
        {/* Pending Approvals */}
        {pendingApprovals.map((approval) => (
          <div key={approval.tool_call_id} className="border-2 border-orange-200 dark:border-orange-800 rounded-lg p-4 bg-orange-50 dark:bg-orange-900/20">
            <div className="flex items-center justify-between mb-3">
              <h4 className="font-medium text-orange-800 dark:text-orange-200">
                Tool Approval Required: {approval.tool_name}
              </h4>
              <div className="flex space-x-2">
                <button
                  onClick={() => handleToolApproval(approval.tool_call_id, true)}
                  disabled={loading}
                  className="inline-flex items-center px-3 py-1 text-sm font-medium text-white bg-green-600 border border-transparent rounded-md hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-green-500 disabled:opacity-50"
                >
                  <CheckIcon className="w-4 h-4 mr-1" />
                  Approve
                </button>
                <button
                  onClick={() => handleToolApproval(approval.tool_call_id, false)}
                  disabled={loading}
                  className="inline-flex items-center px-3 py-1 text-sm font-medium text-white bg-red-600 border border-transparent rounded-md hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500 disabled:opacity-50"
                >
                  <XMarkIcon className="w-4 h-4 mr-1" />
                  Deny
                </button>
              </div>
            </div>
            
            {approval.reasoning && (
              <div className="mb-3">
                <p className="text-sm text-gray-700 dark:text-gray-300 font-medium">Reasoning:</p>
                <p className="text-sm text-gray-600 dark:text-gray-400">{approval.reasoning}</p>
              </div>
            )}
            
            {approval.diff_preview && (
              <div className="mb-3">
                <p className="text-sm text-gray-700 dark:text-gray-300 font-medium">Proposed Changes:</p>
                <pre className="text-xs bg-gray-100 dark:bg-gray-800 p-2 rounded mt-1 overflow-x-auto">
                  {approval.diff_preview}
                </pre>
              </div>
            )}
            
            {approval.edits && approval.edits.length > 0 && (
              <div className="mb-3">
                <p className="text-sm text-gray-700 dark:text-gray-300 font-medium">Document Edits:</p>
                <div className="space-y-2 mt-1">
                  {approval.edits.map((edit, index) => (
                    <div key={index} className="text-xs bg-gray-100 dark:bg-gray-800 p-2 rounded">
                      <div className="text-red-600 dark:text-red-400">- {edit.find}</div>
                      <div className="text-green-600 dark:text-green-400">+ {edit.replace}</div>
                    </div>
                  ))}
                </div>
              </div>
            )}
            
            <div className="mt-3">
              <label className="block text-sm text-gray-700 dark:text-gray-300 mb-1">
                Optional feedback (especially for denials):
              </label>
              <textarea
                value={approvalFeedback[approval.tool_call_id] || ''}
                onChange={(e) => updateApprovalFeedback(approval.tool_call_id, e.target.value)}
                className="w-full px-2 py-1 text-sm border border-gray-300 dark:border-gray-600 rounded focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent dark:bg-gray-700 dark:text-white"
                rows={2}
                placeholder="Provide feedback or reasons for your decision..."
              />
            </div>
          </div>
        ))}
        
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
      <div className="border-t border-gray-200 dark:border-gray-600 p-4">
        <form onSubmit={handleSendMessage} className="flex space-x-2">
          <input
            type="text"
            value={newMessage}
            onChange={(e) => setNewMessage(e.target.value)}
            placeholder="Ask me to help with task specification or implementation planning..."
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