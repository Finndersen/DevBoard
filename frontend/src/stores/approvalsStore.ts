import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { immer } from 'zustand/middleware/immer'
import { useShallow } from 'zustand/react/shallow'
import type { PendingApproval, ToolApprovalDecision, ToolApprovalRequest } from '../lib/api'
import { apiClient } from '../lib/api'

// Enhanced approval with conversation context
export interface PendingApprovalWithContext extends PendingApproval {
  conversationId?: number
}

interface ApprovalsState {
  // Key structure: `project-${projectId}`, `task-${taskId}`, or `conversation-${conversationId}`
  approvals: Record<string, PendingApprovalWithContext[]>
}

interface ApprovalsActions {
  setApprovals: (key: string, approvals: PendingApprovalWithContext[]) => void
  addApproval: (key: string, approval: PendingApprovalWithContext) => void
  removeApproval: (key: string, toolCallId: string) => void
  clearApprovals: (key: string) => void
  getApprovals: (key: string) => PendingApprovalWithContext[]
  hasApprovals: (key: string) => boolean
  processApprovalDecision: (key: string, toolCallId: string, decision: ToolApprovalDecision) => Promise<void>
}

type ApprovalsStore = ApprovalsState & ApprovalsActions

const STORAGE_KEY = 'devboard_pending_approvals'

// Stable empty array reference to prevent infinite re-renders when no approvals exist
const EMPTY_APPROVALS: PendingApprovalWithContext[] = []

export const useApprovalsStore = create<ApprovalsStore>()(
  persist(
    immer((set, get) => ({
      // Initial state
      approvals: {},

      // Set approvals with deduplication - only update if IDs changed
      setApprovals: (key, approvals) => {
        const existing = get().approvals[key] || []
        const existingIds = new Set(existing.map(a => a.tool_call_id))
        const newIds = new Set(approvals.map(a => a.tool_call_id))

        // Only update if the set of approval IDs has changed
        const hasChanged = existingIds.size !== newIds.size ||
          ![...existingIds].every(id => newIds.has(id))

        if (hasChanged) {
          set(draft => {
            draft.approvals[key] = approvals
          })
        }
      },

      addApproval: (key, approval) => {
        set(draft => {
          if (!draft.approvals[key]) {
            draft.approvals[key] = []
          }
          draft.approvals[key].push(approval)
        })
      },

      removeApproval: (key, toolCallId) => {
        set(draft => {
          if (draft.approvals[key]) {
            draft.approvals[key] = draft.approvals[key].filter(
              approval => approval.tool_call_id !== toolCallId
            )
          }
        })
      },

      clearApprovals: (key) => {
        set(draft => {
          delete draft.approvals[key]
        })
      },

      getApprovals: (key) => {
        return get().approvals[key] || []
      },

      hasApprovals: (key) => {
        const approvals = get().approvals[key]
        return approvals && approvals.length > 0
      },

      processApprovalDecision: async (key, toolCallId, decision) => {
        // Find the approval to get conversation context
        const approvals = get().approvals[key] || []
        const approval = approvals.find(a => a.tool_call_id === toolCallId)

        if (!approval) {
          console.warn('approvalsStore: Could not find approval for toolCallId:', toolCallId)
          return
        }

        // For conversation approvals, send the decision to the backend
        if (approval.conversationId) {
          const approvalRequest: ToolApprovalRequest = {
            approvals: {
              [toolCallId]: decision
            }
          }

          // Send the approval decision to the backend
          await apiClient.approveConversationTools(approval.conversationId, approvalRequest)
        }

        // Remove the approval from state after successful backend call
        set(draft => {
          if (draft.approvals[key]) {
            draft.approvals[key] = draft.approvals[key].filter(
              a => a.tool_call_id !== toolCallId
            )
          }
        })
      }
    })),
    {
      name: STORAGE_KEY,
      // Only persist the approvals state, not the actions
      partialize: (state) => ({ approvals: state.approvals })
    }
  )
)

/**
 * Selector hook for components that only need actions (no re-renders on state change)
 * Use this for AgentChat, ConversationChat
 * Uses useShallow to prevent infinite re-render loops by doing shallow comparison
 */
export const useApprovalActions = () => {
  return useApprovalsStore(
    useShallow(state => ({
      setApprovals: state.setApprovals,
      addApproval: state.addApproval,
      removeApproval: state.removeApproval,
      clearApprovals: state.clearApprovals,
      getApprovals: state.getApprovals,
      hasApprovals: state.hasApprovals,
      processApprovalDecision: state.processApprovalDecision
    }))
  )
}

/**
 * Selector hook for components that need approvals data for a specific key
 * Use this for ConversationChat
 * Uses stable EMPTY_APPROVALS reference to prevent infinite re-renders
 */
export const useApprovals = (key: string): PendingApprovalWithContext[] => {
  return useApprovalsStore(state => state.approvals[key] ?? EMPTY_APPROVALS)
}

/**
 * Selector hook for components that need all approvals
 * Use this for NotificationsPanel
 */
export const useAllApprovals = () => {
  return useApprovalsStore(state => state.approvals)
}
