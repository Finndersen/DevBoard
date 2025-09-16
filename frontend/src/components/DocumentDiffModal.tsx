import { useEffect, useRef, useState, useCallback } from 'react'
import { XMarkIcon, DocumentTextIcon, CheckIcon, XMarkIcon as DenyIcon } from '@heroicons/react/24/outline'
import DiffViewer from './DiffViewer'
import type { PendingApproval, ToolApprovalDecision } from '../lib/api'
import { standardFeedbackTextareaClasses } from '../styles/inputStyles'

interface DocumentDiffModalProps {
  approval: PendingApproval
  isOpen: boolean
  onClose: () => void
  onApproval: (toolCallId: string, decision: ToolApprovalDecision) => void
  disabled?: boolean
}

export default function DocumentDiffModal({
  approval,
  isOpen,
  onClose,
  onApproval,
  disabled = false
}: DocumentDiffModalProps) {
  const modalRef = useRef<HTMLDivElement>(null)
  const feedbackRef = useRef<HTMLTextAreaElement>(null)
  const [showDenyFeedback, setShowDenyFeedback] = useState(false)

  const getDocumentTypeDisplay = (documentType: string | null) => {
    switch (documentType) {
      case 'task_specification':
        return 'Task Specification'
      case 'implementation_plan':
        return 'Implementation Plan'
      case 'project_specification':
        return 'Project Specification'
      default:
        return documentType || 'Document'
    }
  }

  const handleApprove = useCallback(() => {
    const feedback = feedbackRef.current?.value
    onApproval(approval.tool_call_id, {
      approved: true,
      feedback: feedback || undefined
    })
    onClose()
  }, [approval.tool_call_id, onApproval, onClose])

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
      onApproval(approval.tool_call_id, {
        approved: false,
        feedback: feedback || undefined
      })
      onClose()
    }
  }, [showDenyFeedback, approval.tool_call_id, onApproval, onClose])

  const handleConfirmDeny = useCallback(() => {
    const feedback = feedbackRef.current?.value
    onApproval(approval.tool_call_id, {
      approved: false,
      feedback: feedback || undefined
    })
    onClose()
  }, [approval.tool_call_id, onApproval, onClose])

  const handleCancelDeny = useCallback(() => {
    setShowDenyFeedback(false)
    if (feedbackRef.current) {
      feedbackRef.current.value = ''
    }
  }, [])

  // Handle keyboard navigation
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (!isOpen) return

      switch (event.key) {
        case 'Escape':
          if (showDenyFeedback) {
            // Cancel deny feedback mode
            event.preventDefault()
            handleCancelDeny()
          } else {
            onClose()
          }
          break
        case 'Enter':
          if (event.ctrlKey || event.metaKey) {
            event.preventDefault()
            if (showDenyFeedback) {
              // Confirm deny with feedback
              handleConfirmDeny()
            } else {
              // Approve changes
              handleApprove()
            }
          }
          break
        case 'r':
          if (event.ctrlKey || event.metaKey) {
            // Ctrl/Cmd + R to reject/deny (prevent default browser refresh)
            event.preventDefault()
            handleDeny()
          }
          break
        case 'Tab':
          // Focus trapping is handled by the browser within the modal
          break
      }
    }

    if (isOpen) {
      document.addEventListener('keydown', handleKeyDown)
      // Prevent body scroll when modal is open
      document.body.style.overflow = 'hidden'
      
      // Focus the modal when it opens
      requestAnimationFrame(() => {
        modalRef.current?.focus()
      })
    }

    return () => {
      document.removeEventListener('keydown', handleKeyDown)
      document.body.style.overflow = 'unset'
    }
  }, [isOpen, onClose, showDenyFeedback, handleApprove, handleConfirmDeny, handleDeny, handleCancelDeny])

  // Handle click outside modal
  const handleBackdropClick = (event: React.MouseEvent) => {
    if (event.target === event.currentTarget) {
      onClose()
    }
  }


  if (!isOpen) {
    return null
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      onClick={handleBackdropClick}
      role="dialog"
      aria-modal="true"
      aria-labelledby="modal-title"
    >
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black bg-opacity-50 backdrop-blur-sm" />

      {/* Modal */}
      <div
        ref={modalRef}
        tabIndex={-1}
        className="relative w-full max-w-6xl h-full max-h-[90vh] mx-4 bg-white dark:bg-gray-900 rounded-lg shadow-2xl flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-200 dark:border-gray-700">
          <div className="flex items-center space-x-3">
            <DocumentTextIcon className="w-6 h-6 text-blue-600 dark:text-blue-400" />
            <h2 id="modal-title" className="text-xl font-semibold text-gray-900 dark:text-white">
              Review Changes: {getDocumentTypeDisplay(approval.document_type || null)}
            </h2>
          </div>
          <button
            onClick={onClose}
            className="p-2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition-colors"
            aria-label="Close modal"
          >
            <XMarkIcon className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-auto p-6 space-y-6">
          {/* Agent Reasoning */}
          {approval.reasoning && (
            <div>
              <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Agent Reasoning:
              </h3>
              <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-4">
                <p className="text-sm text-gray-700 dark:text-gray-300">
                  {approval.reasoning}
                </p>
              </div>
            </div>
          )}

          {/* Enhanced Diff Viewer */}
          {(approval.diff_preview || (approval.edits && approval.edits.length > 0)) && (
            <div>
              <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-4">
                Proposed Changes:
              </h3>
              <DiffViewer approval={approval} />
            </div>
          )}

          {/* Feedback Section - Show always but highlight when denying */}
          <div className={showDenyFeedback ? 'ring-2 ring-red-500 ring-opacity-50 rounded-lg p-3 bg-red-50 dark:bg-red-900/20' : ''}>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              {showDenyFeedback ? (
                <>
                  <span className="text-red-700 dark:text-red-400">Please provide feedback for denial:</span>
                  <span className="text-xs text-red-600 dark:text-red-400 ml-2">
                    Help the agent understand why the changes were rejected
                  </span>
                </>
              ) : (
                <>
                  Feedback (optional):
                  <span className="text-xs text-gray-500 dark:text-gray-400 ml-2">
                    Provide context when denying changes
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
                  ? "Explain why these changes are being rejected and provide guidance for improvement..."
                  : "Provide feedback, corrections, or additional instructions for the agent..."
              }
            />
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between p-6 border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800">
          <div className="text-xs text-gray-500 dark:text-gray-400">
            {showDenyFeedback ? (
              <div>
                <div className="text-red-600 dark:text-red-400">
                  <strong>Provide feedback</strong> and click <strong>Confirm Denial</strong> to reject the changes.
                </div>
                <div className="mt-1 space-x-4">
                  <span><kbd className="px-1 py-0.5 bg-gray-200 dark:bg-gray-700 rounded text-xs">Esc</kbd> Cancel</span>
                  <span><kbd className="px-1 py-0.5 bg-gray-200 dark:bg-gray-700 rounded text-xs">⌘/Ctrl+Enter</kbd> Confirm</span>
                </div>
              </div>
            ) : (
              <div>
                <div>
                  <strong>Accept</strong> to apply these changes to the document.{' '}
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
                  <DenyIcon className="w-4 h-4 mr-2" />
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
                  <DenyIcon className="w-4 h-4 mr-2" />
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
    </div>
  )
}