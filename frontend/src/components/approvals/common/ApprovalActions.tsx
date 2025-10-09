import { useRef, useState, useCallback } from 'react'
import { CheckIcon, XMarkIcon } from '@heroicons/react/24/outline'
import type { ToolApprovalDecision } from '../../../lib/api'
import { standardFeedbackTextareaClasses } from '../../../styles/inputStyles'

interface ApprovalActionsProps {
  toolCallId: string
  onApproval: (toolCallId: string, decision: ToolApprovalDecision) => void
  onClose: () => void
  disabled?: boolean
  approvalType: 'edit' | 'set'
}

export default function ApprovalActions({
  toolCallId,
  onApproval,
  onClose,
  disabled = false,
  approvalType
}: ApprovalActionsProps) {
  const feedbackRef = useRef<HTMLTextAreaElement>(null)
  const [showDenyFeedback, setShowDenyFeedback] = useState(false)

  const handleApprove = useCallback(() => {
    const feedback = feedbackRef.current?.value
    onApproval(toolCallId, {
      approved: true,
      feedback: feedback || undefined
    })
    onClose()
  }, [toolCallId, onApproval, onClose])

  const handleDeny = useCallback(() => {
    if (!showDenyFeedback) {
      // First click: show feedback input and focus it
      setShowDenyFeedback(true)
      setTimeout(() => {
        feedbackRef.current?.focus()
      }, 100)
    } else {
      // Second click or confirm: proceed with denial
      const feedback = feedbackRef.current?.value
      onApproval(toolCallId, {
        approved: false,
        feedback: feedback || undefined
      })
      onClose()
    }
  }, [showDenyFeedback, toolCallId, onApproval, onClose])

  const handleConfirmDeny = useCallback(() => {
    const feedback = feedbackRef.current?.value
    onApproval(toolCallId, {
      approved: false,
      feedback: feedback || undefined
    })
    onClose()
  }, [toolCallId, onApproval, onClose])

  const handleCancelDeny = useCallback(() => {
    setShowDenyFeedback(false)
    if (feedbackRef.current) {
      feedbackRef.current.value = ''
    }
  }, [])

  const actionVerb = approvalType === 'set' ? 'set' : 'apply'

  return (
    <div className="space-y-4">
      {/* Feedback Section - Show always but highlight when denying */}
      <div className={showDenyFeedback ? 'ring-2 ring-red-500 ring-opacity-50 rounded-lg p-3 bg-red-50 dark:bg-red-900/20' : ''}>
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
          {showDenyFeedback ? (
            <>
              <span className="text-red-700 dark:text-red-400">Please provide feedback for denial:</span>
              <span className="text-xs text-red-600 dark:text-red-400 ml-2">
                Help the agent understand why the {approvalType === 'set' ? 'content was' : 'changes were'} rejected
              </span>
            </>
          ) : (
            <>
              Feedback (optional):
              <span className="text-xs text-gray-500 dark:text-gray-400 ml-2">
                Provide context when denying {approvalType === 'set' ? 'content' : 'changes'}
              </span>
            </>
          )}
        </label>
        <textarea
          ref={feedbackRef}
          disabled={disabled}
          className={`w-full ${standardFeedbackTextareaClasses} resize-vertical ${
            showDenyFeedback ? 'ring-2 ring-red-500 border-red-300 dark:border-red-600' : ''
          }`}
          rows={showDenyFeedback ? 6 : 4}
          placeholder={
            showDenyFeedback
              ? `Explain why this ${approvalType === 'set' ? 'content is' : 'change is'} being rejected and provide guidance for improvement...`
              : "Provide feedback, corrections, or additional instructions for the agent..."
          }
        />
      </div>

      {/* Footer with Actions */}
      <div className="flex items-center justify-between p-6 border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800">
        <div className="text-xs text-gray-500 dark:text-gray-400">
          {showDenyFeedback ? (
            <div>
              <div className="text-red-600 dark:text-red-400">
                <strong>Provide feedback</strong> and click <strong>Confirm Denial</strong> to reject the {approvalType === 'set' ? 'content' : 'changes'}.
              </div>
              <div className="mt-1 space-x-4">
                <span><kbd className="px-1 py-0.5 bg-gray-200 dark:bg-gray-700 rounded text-xs">Esc</kbd> Cancel</span>
                <span><kbd className="px-1 py-0.5 bg-gray-200 dark:bg-gray-700 rounded text-xs">⌘/Ctrl+Enter</kbd> Confirm</span>
              </div>
            </div>
          ) : (
            <div>
              <div>
                <strong>Accept</strong> to {actionVerb} {approvalType === 'set' ? 'this content to' : 'these changes to'} the document.{' '}
                <strong>Deny</strong> to reject them.
              </div>
              <div className="mt-1 space-x-4">
                <span><kbd className="px-1 py-0.5 bg-gray-200 dark:bg-gray-700 rounded text-xs">Esc</kbd> Close</span>
                <span><kbd className="px-1 py-0.5 bg-gray-200 dark:bg-gray-700 rounded text-xs">⌘/Ctrl+Enter</kbd> Accept</span>
                <span><kbd className="px-1 py-0.5 bg-gray-200 dark:bg-gray-700 rounded text-xs">⌘/Ctrl+R</kbd> Deny</span>
              </div>
            </div>
          )}
        </div>
        <div className="flex space-x-3">
          {showDenyFeedback ? (
            <>
              <button
                onClick={handleCancelDeny}
                disabled={disabled}
                className="inline-flex items-center px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-md hover:bg-gray-50 dark:hover:bg-gray-600 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                title="Cancel denial"
              >
                Cancel
              </button>
              <button
                onClick={handleConfirmDeny}
                disabled={disabled}
                className="inline-flex items-center px-4 py-2 text-sm font-medium text-white bg-red-600 border border-transparent rounded-md hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                title="Confirm denial with feedback (Ctrl/Cmd+Enter)"
              >
                <XMarkIcon className="w-4 h-4 mr-2" />
                Confirm Denial
              </button>
            </>
          ) : (
            <>
              <button
                onClick={handleDeny}
                disabled={disabled}
                className="inline-flex items-center px-4 py-2 text-sm font-medium text-white bg-red-600 border border-transparent rounded-md hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                title="Deny changes - provide feedback (Ctrl/Cmd+R)"
              >
                <XMarkIcon className="w-4 h-4 mr-2" />
                Deny
              </button>
              <button
                onClick={handleApprove}
                disabled={disabled}
                className="inline-flex items-center px-4 py-2 text-sm font-medium text-white bg-green-600 border border-transparent rounded-md hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-green-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                title="Accept changes (Ctrl/Cmd+Enter)"
              >
                <CheckIcon className="w-4 h-4 mr-2" />
                Accept
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
