import { useState } from 'react'
import { ExclamationTriangleIcon, CheckIcon, XMarkIcon } from '@heroicons/react/24/outline'
import DocumentEditApproval from '../documents/DocumentEditApproval'
import type { PendingApproval, ToolApprovalDecision, ToolApprovalRequest } from '../../../lib/api'
import { standardFeedbackTextareaClasses } from '../../../styles/inputStyles'

interface PendingApprovalsListProps {
  approvals: PendingApproval[]
  onBatchApproval: (approvalRequest: ToolApprovalRequest) => void
  loading?: boolean
}

export default function PendingApprovalsList({ 
  approvals, 
  onBatchApproval, 
  loading = false 
}: PendingApprovalsListProps) {
  const [decisions, setDecisions] = useState<Record<string, ToolApprovalDecision>>({})
  const [globalFeedback, setGlobalFeedback] = useState('')

  const handleSingleApproval = (toolCallId: string, decision: ToolApprovalDecision) => {
    // For single approval, immediately submit
    onBatchApproval({
      approvals: { [toolCallId]: decision }
    })
  }

  const handleApproveAll = () => {
    const allApprovals: Record<string, ToolApprovalDecision> = {}
    approvals.forEach(approval => {
      allApprovals[approval.tool_call_id] = {
        approved: true,
        feedback: globalFeedback || undefined
      }
    })
    onBatchApproval({ approvals: allApprovals })
    setDecisions({})
    setGlobalFeedback('')
  }

  const handleDenyAll = () => {
    const allDenials: Record<string, ToolApprovalDecision> = {}
    approvals.forEach(approval => {
      allDenials[approval.tool_call_id] = {
        approved: false,
        feedback: globalFeedback || 'Batch denial'
      }
    })
    onBatchApproval({ approvals: allDenials })
    setDecisions({})
    setGlobalFeedback('')
  }

  const handleSubmitDecisions = () => {
    // Add global feedback to decisions that don't have individual feedback
    const finalDecisions: Record<string, ToolApprovalDecision> = {}
    Object.entries(decisions).forEach(([toolCallId, decision]) => {
      finalDecisions[toolCallId] = {
        ...decision,
        feedback: decision.feedback || globalFeedback || undefined
      }
    })
    
    onBatchApproval({ approvals: finalDecisions })
    setDecisions({})
    setGlobalFeedback('')
  }

  const hasPendingDecisions = Object.keys(decisions).length > 0
  const allDecisionsMade = approvals.every(approval => decisions[approval.tool_call_id])

  if (approvals.length === 0) {
    return null
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between p-4 bg-orange-100 dark:bg-orange-900/30 rounded-lg border border-orange-200 dark:border-orange-800">
        <div className="flex items-center space-x-2">
          <ExclamationTriangleIcon className="w-5 h-5 text-orange-600 dark:text-orange-400" />
          <h3 className="font-medium text-orange-800 dark:text-orange-200">
            {approvals.length} Tool{approvals.length !== 1 ? 's' : ''} Awaiting Approval
          </h3>
        </div>
        
        {/* Batch Actions */}
        {approvals.length > 1 && (
          <div className="flex space-x-2">
            <button
              onClick={handleApproveAll}
              disabled={loading}
              className="inline-flex items-center px-3 py-1 text-sm font-medium text-white bg-green-600 border border-transparent rounded-md hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-green-500 disabled:opacity-50"
            >
              <CheckIcon className="w-4 h-4 mr-1" />
              Approve All
            </button>
            <button
              onClick={handleDenyAll}
              disabled={loading}
              className="inline-flex items-center px-3 py-1 text-sm font-medium text-white bg-red-600 border border-transparent rounded-md hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500 disabled:opacity-50"
            >
              <XMarkIcon className="w-4 h-4 mr-1" />
              Deny All
            </button>
          </div>
        )}
      </div>

      {/* Global Feedback for Batch Operations */}
      {approvals.length > 1 && (
        <div className="p-4 bg-gray-50 dark:bg-gray-800/50 rounded-lg">
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
            Global feedback (applies to all tools):
          </label>
          <textarea
            value={globalFeedback}
            onChange={(e) => setGlobalFeedback(e.target.value)}
            disabled={loading}
            className={`w-full ${standardFeedbackTextareaClasses}`}
            rows={2}
            placeholder="Optional feedback that will apply to all tools..."
          />
        </div>
      )}

      {/* Individual Approvals */}
      <div className="space-y-4">
        {approvals.map((approval, index) => (
          <div key={approval.tool_call_id}>
            <div className="flex items-center justify-between mb-2">
              <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Tool {index + 1} of {approvals.length}: {approval.tool_name}
              </h4>
              {decisions[approval.tool_call_id] && (
                <span className={`text-xs px-2 py-1 rounded ${
                  decisions[approval.tool_call_id].approved
                    ? 'bg-green-100 text-green-800 dark:bg-green-900/20 dark:text-green-400'
                    : 'bg-red-100 text-red-800 dark:bg-red-900/20 dark:text-red-400'
                }`}>
                  {decisions[approval.tool_call_id].approved ? 'Approved' : 'Denied'}
                </span>
              )}
            </div>
            
            <DocumentEditApproval
              approval={approval}
              onApproval={handleSingleApproval}
              disabled={loading}
            />
          </div>
        ))}
      </div>

      {/* Batch Decision Submission */}
      {hasPendingDecisions && (
        <div className="p-4 bg-blue-50 dark:bg-blue-900/20 rounded-lg border border-blue-200 dark:border-blue-800">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-blue-800 dark:text-blue-200">
                {Object.keys(decisions).length} of {approvals.length} decisions made
              </p>
              <p className="text-xs text-blue-600 dark:text-blue-400">
                {allDecisionsMade 
                  ? 'Ready to submit all decisions' 
                  : 'Make decisions for remaining tools, or submit partial decisions'
                }
              </p>
            </div>
            <button
              onClick={handleSubmitDecisions}
              disabled={loading}
              className="inline-flex items-center px-4 py-2 text-sm font-medium text-white bg-blue-600 border border-transparent rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50"
            >
              Submit Decisions
            </button>
          </div>
        </div>
      )}

      {/* Help Text */}
      <div className="p-3 bg-gray-100 dark:bg-gray-800 rounded text-xs text-gray-600 dark:text-gray-400">
        <p>
          <strong>Individual approval:</strong> Click approve/deny on each tool to process immediately.
        </p>
        {approvals.length > 1 && (
          <p className="mt-1">
            <strong>Batch processing:</strong> Use "Approve All" / "Deny All" for quick decisions, 
            or make individual decisions and click "Submit Decisions" to process them together.
          </p>
        )}
      </div>
    </div>
  )
}