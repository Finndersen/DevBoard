import { useState } from 'react'
import { CheckIcon, XMarkIcon, DocumentTextIcon } from '@heroicons/react/24/outline'
import type { PendingApproval, ToolApprovalDecision } from '../lib/api'

interface DocumentEditApprovalProps {
  approval: PendingApproval
  onApproval: (toolCallId: string, decision: ToolApprovalDecision) => void
  disabled?: boolean
}

export default function DocumentEditApproval({ 
  approval, 
  onApproval, 
  disabled = false 
}: DocumentEditApprovalProps) {
  const [feedback, setFeedback] = useState('')

  const handleApprove = () => {
    onApproval(approval.tool_call_id, {
      approved: true,
      feedback: feedback || undefined
    })
    setFeedback('')
  }

  const handleDeny = () => {
    onApproval(approval.tool_call_id, {
      approved: false,
      feedback: feedback || undefined
    })
    setFeedback('')
  }

  const getDocumentTypeDisplay = (documentType: string | null) => {
    switch (documentType) {
      case 'task_specification':
        return 'Task Specification'
      case 'implementation_plan':
        return 'Implementation Plan'
      default:
        return documentType || 'Document'
    }
  }

  return (
    <div className="border-2 border-orange-200 dark:border-orange-800 rounded-lg p-4 bg-orange-50 dark:bg-orange-900/20">
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center space-x-2">
          <DocumentTextIcon className="w-5 h-5 text-orange-600 dark:text-orange-400" />
          <h4 className="font-medium text-orange-800 dark:text-orange-200">
            Edit {approval.document_type ? getDocumentTypeDisplay(approval.document_type) : 'Document'}
          </h4>
        </div>
        <div className="flex space-x-2">
          <button
            onClick={handleApprove}
            disabled={disabled}
            className="inline-flex items-center px-3 py-1 text-sm font-medium text-white bg-green-600 border border-transparent rounded-md hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-green-500 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <CheckIcon className="w-4 h-4 mr-1" />
            Approve
          </button>
          <button
            onClick={handleDeny}
            disabled={disabled}
            className="inline-flex items-center px-3 py-1 text-sm font-medium text-white bg-red-600 border border-transparent rounded-md hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <XMarkIcon className="w-4 h-4 mr-1" />
            Deny
          </button>
        </div>
      </div>

      {/* Agent Reasoning */}
      {approval.reasoning && (
        <div className="mb-3">
          <p className="text-sm text-gray-700 dark:text-gray-300 font-medium mb-1">Agent Reasoning:</p>
          <p className="text-sm text-gray-600 dark:text-gray-400 bg-gray-100 dark:bg-gray-800 p-2 rounded">
            {approval.reasoning}
          </p>
        </div>
      )}

      {/* Diff Preview */}
      {approval.diff_preview && (
        <div className="mb-3">
          <p className="text-sm text-gray-700 dark:text-gray-300 font-medium mb-1">Proposed Changes:</p>
          <pre className="text-xs bg-gray-100 dark:bg-gray-800 p-3 rounded border overflow-x-auto whitespace-pre-wrap">
            {approval.diff_preview}
          </pre>
        </div>
      )}

      {/* Individual Edits */}
      {approval.edits && approval.edits.length > 0 && (
        <div className="mb-3">
          <p className="text-sm text-gray-700 dark:text-gray-300 font-medium mb-2">
            Document Edits ({approval.edits.length}):
          </p>
          <div className="space-y-3">
            {approval.edits.map((edit, index) => (
              <div key={index} className="border border-gray-200 dark:border-gray-700 rounded p-3 bg-white dark:bg-gray-800">
                <div className="text-xs text-gray-500 dark:text-gray-400 mb-2">Edit {index + 1}</div>
                <div className="space-y-2">
                  <div>
                    <div className="text-xs font-medium text-red-700 dark:text-red-400 mb-1">Remove:</div>
                    <pre className="text-xs bg-red-50 dark:bg-red-900/20 text-red-800 dark:text-red-200 p-2 rounded border-l-2 border-red-400 whitespace-pre-wrap">
                      {edit.find}
                    </pre>
                  </div>
                  <div>
                    <div className="text-xs font-medium text-green-700 dark:text-green-400 mb-1">Replace with:</div>
                    <pre className="text-xs bg-green-50 dark:bg-green-900/20 text-green-800 dark:text-green-200 p-2 rounded border-l-2 border-green-400 whitespace-pre-wrap">
                      {edit.replace}
                    </pre>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Feedback Input */}
      <div className="mt-3">
        <label className="block text-sm text-gray-700 dark:text-gray-300 mb-1">
          Optional feedback:
          <span className="text-xs text-gray-500 dark:text-gray-400 ml-1">
            (Especially helpful when denying changes)
          </span>
        </label>
        <textarea
          value={feedback}
          onChange={(e) => setFeedback(e.target.value)}
          disabled={disabled}
          className="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent dark:bg-gray-700 dark:text-white disabled:opacity-50 disabled:cursor-not-allowed"
          rows={3}
          placeholder="Provide feedback, corrections, or additional instructions for the agent..."
        />
      </div>

      {/* Help Text */}
      <div className="mt-3 p-2 bg-blue-50 dark:bg-blue-900/20 rounded text-xs text-blue-700 dark:text-blue-300">
        <p>
          <strong>Approve</strong> to apply these changes to the document. 
          <strong> Deny</strong> to reject them (provide feedback to help the agent improve).
        </p>
      </div>
    </div>
  )
}