import type { PendingApproval, ToolApprovalDecision } from '../../lib/api'
import {
  isSetContentTool,
  getDocumentTypeDisplay,
  getDocumentTypeFromToolName,
  getContentFromToolArgs,
  getReasoningFromToolArgs
} from '../../utils/toolTypeUtils'
import DocumentApprovalModal from '../approvals/documents/DocumentApprovalModal'
import AgentReasoning from '../chat/AgentReasoning'
import DocumentEditViewer from './DocumentEditViewer'
import DocumentContentViewer from './DocumentContentViewer'
import ApprovalActions from '../approvals/common/ApprovalActions'

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
  const isSetTool = isSetContentTool(approval.tool_name)
  const approvalType = isSetTool ? 'set' : 'edit'
  const documentType = getDocumentTypeFromToolName(approval.tool_name)
  const content = getContentFromToolArgs(approval)
  const reasoning = getReasoningFromToolArgs(approval)

  const modalTitle = `${isSetTool ? 'Review Content:' : 'Review Changes:'} ${getDocumentTypeDisplay(documentType)}`

  return (
    <DocumentApprovalModal
      isOpen={isOpen}
      onClose={onClose}
      title={modalTitle}
    >
      <div className="space-y-6">
        {/* Agent Reasoning */}
        <AgentReasoning reasoning={reasoning} />

        {/* Document Viewer - Edit or Set Content */}
        {isSetTool && content ? (
          <div>
            <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-4">
              Document Content:
            </h3>
            <DocumentContentViewer content={content} />
          </div>
        ) : (
          <div>
            <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-4">
              Proposed Changes:
            </h3>
            <DocumentEditViewer approval={approval} />
          </div>
        )}

        {/* Approval Actions */}
        <ApprovalActions
          toolCallId={approval.tool_call_id}
          onApproval={onApproval}
          onClose={onClose}
          disabled={disabled}
          approvalType={approvalType}
        />
      </div>
    </DocumentApprovalModal>
  )
}
