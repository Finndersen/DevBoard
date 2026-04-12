import { useState, useRef, useMemo, useEffect } from 'react'
import type { ToolCallRequest, ToolApprovalRequest } from '../../../lib/api'
import { useApprovals, useApprovalActions, type PendingApprovalWithContext } from '../../../stores/approvalsStore'
import { createConversationApprovalKey } from '../../../utils/approvalKeys'
import { useNotificationStore } from '../../../stores/notificationStore'
import { reportMutationError } from '../../../lib/errors'

export function useToolApprovalLogic(
  conversationId: number,
  pendingToolRequests: ToolCallRequest[] | undefined,
  clearPendingToolRequests: (id: number) => void,
  approveTools: (id: number, approvals: Record<string, { approved: boolean; feedback?: string }>) => Promise<void>,
) {
  const approvalKey = useMemo(() => createConversationApprovalKey(conversationId), [conversationId])
  const pendingApprovals = useApprovals(approvalKey)
  const { setApprovals, clearApprovals } = useApprovalActions()
  const hasSetApprovalsRef = useRef(false)
  const [approvalError, setApprovalError] = useState<string | null>(null)
  const addNotification = useNotificationStore(s => s.addNotification)

  useEffect(() => {
    if (pendingToolRequests && pendingToolRequests.length > 0) {
      const approvals: PendingApprovalWithContext[] = pendingToolRequests.map((request) => {
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

        return {
          tool_call_id: request.tool_call_id,
          tool_name: request.tool_name,
          tool_args: toolArgs,
          conversationId: conversationId
        }
      })

      setApprovals(approvalKey, approvals)
      hasSetApprovalsRef.current = true
    }
    // DO NOT clear approvals when stream state disappears - approvals persist until handled
  }, [pendingToolRequests, conversationId, setApprovals, approvalKey])

  const handleToolApproval = async (approvalRequest: ToolApprovalRequest) => {
    if (pendingApprovals.length === 0) return

    setApprovalError(null)

    try {
      clearApprovals(approvalKey)
      clearPendingToolRequests(conversationId)
      await approveTools(conversationId, approvalRequest.approvals)
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : 'An unknown error occurred'
      setApprovalError(`Failed to process approval: ${errorMsg}. Please try again.`)
      reportMutationError(addNotification, error, {
        entityType: null,
        entityId: null,
        entityTitle: null,
        fallbackMessage: 'Failed to process tool approval',
      })
    }
  }

  return {
    approvalKey,
    pendingApprovals,
    setApprovals,
    approvalError,
    handleToolApproval,
  }
}
