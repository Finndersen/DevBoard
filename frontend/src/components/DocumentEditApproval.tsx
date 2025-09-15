import { useState } from 'react'
import { CheckIcon, XMarkIcon, DocumentTextIcon, EyeIcon } from '@heroicons/react/24/outline'
import DocumentDiffModal from './DocumentDiffModal'
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
  const [isModalOpen, setIsModalOpen] = useState(false)

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

  const getChangeSummary = () => {
    if (approval.edits && approval.edits.length > 0) {
      return `${approval.edits.length} change${approval.edits.length !== 1 ? 's' : ''}`
    }
    if (approval.diff_preview) {
      const lines = approval.diff_preview.split('\n')
      const addedLines = lines.filter(line => line.startsWith('+')).length
      const removedLines = lines.filter(line => line.startsWith('-')).length
      return `+${addedLines} -${removedLines} lines`
    }
    return 'Changes pending'
  }

  const handleApprove = () => {
    onApproval(approval.tool_call_id, {
      approved: true
    })
  }

  const handleDeny = () => {
    onApproval(approval.tool_call_id, {
      approved: false
    })
  }

  return (
    <>
      <div className="border-2 border-orange-200 dark:border-orange-800 rounded-lg p-4 bg-orange-50 dark:bg-orange-900/20">
        {/* Compact Header */}
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center space-x-3">
            <DocumentTextIcon className="w-5 h-5 text-orange-600 dark:text-orange-400" />
            <div>
              <h4 className="font-medium text-orange-800 dark:text-orange-200">
                Edit {getDocumentTypeDisplay(approval.document_type)}
              </h4>
              <p className="text-xs text-orange-600 dark:text-orange-400">
                {getChangeSummary()}
              </p>
            </div>
          </div>
          <div className="flex items-center space-x-2">
            <button
              onClick={() => setIsModalOpen(true)}
              disabled={disabled}
              className="inline-flex items-center px-3 py-1 text-sm font-medium text-orange-700 dark:text-orange-300 bg-orange-100 dark:bg-orange-800/30 border border-orange-300 dark:border-orange-600 rounded-md hover:bg-orange-200 dark:hover:bg-orange-800/50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-orange-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              <EyeIcon className="w-4 h-4 mr-1" />
              Review
            </button>
          </div>
        </div>

        {/* Agent Reasoning Preview */}
        {approval.reasoning && (
          <div className="mb-3">
            <p className="text-sm text-gray-700 dark:text-gray-300 font-medium mb-1">Agent Reasoning:</p>
            <p className="text-sm text-gray-600 dark:text-gray-400 bg-gray-100 dark:bg-gray-800 p-2 rounded line-clamp-2">
              {approval.reasoning}
            </p>
          </div>
        )}

        {/* Quick Action Buttons */}
        <div className="flex items-center justify-between">
          <div className="text-xs text-gray-500 dark:text-gray-400">
            Click <strong>Review</strong> for detailed diff view, or use quick actions:
          </div>
          <div className="flex space-x-2">
            <button
              onClick={handleDeny}
              disabled={disabled}
              className="inline-flex items-center px-3 py-1 text-sm font-medium text-white bg-red-600 border border-transparent rounded-md hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              <XMarkIcon className="w-4 h-4 mr-1" />
              Quick Deny
            </button>
            <button
              onClick={handleApprove}
              disabled={disabled}
              className="inline-flex items-center px-3 py-1 text-sm font-medium text-white bg-green-600 border border-transparent rounded-md hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-green-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              <CheckIcon className="w-4 h-4 mr-1" />
              Quick Approve
            </button>
          </div>
        </div>
      </div>

      {/* Modal for detailed review */}
      <DocumentDiffModal
        approval={approval}
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onApproval={onApproval}
        disabled={disabled}
      />
    </>
  )
}