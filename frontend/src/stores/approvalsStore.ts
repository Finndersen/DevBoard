import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { immer } from 'zustand/middleware/immer'
import { useShallow } from 'zustand/react/shallow'
import type { PendingApproval, ToolApprovalDecision, ToolApprovalRequest } from '../lib/api'
import { apiClient } from '../lib/api'
import { toolApprovalConfig, type RefreshHandler } from '../services/toolApprovalConfig'

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
  registerRefreshHandler: (conversationId: number, refreshAction: string, callback: () => Promise<void>) => void
  unregisterRefreshHandlers: (conversationId: number) => void
  executeRefreshHandlers: (conversationId: number, toolNames: string[]) => Promise<void>
}

type ApprovalsStore = ApprovalsState & ApprovalsActions

const STORAGE_KEY = 'devboard_pending_approvals'

// Stable empty array reference to prevent infinite re-renders when no approvals exist
const EMPTY_APPROVALS: PendingApprovalWithContext[] = []

/**
 * Refresh handler registry - kept outside Zustand state because:
 * 1. It contains functions (not serializable)
 * 2. It doesn't need to be persisted
 * 3. It doesn't need to trigger re-renders
 */
const refreshHandlerRegistry = new Map<number, RefreshHandler[]>()

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

          // Execute refresh handlers after successful backend response
          if (decision.approved) {
            const handlers = refreshHandlerRegistry.get(approval.conversationId)
            if (handlers && handlers.length > 0) {
              const requiredActions = toolApprovalConfig.getRequiredRefreshActions([approval.tool_name])
              const refreshPromises: Promise<void>[] = []

              for (const handler of handlers) {
                if (requiredActions.includes(handler.refreshAction)) {
                  refreshPromises.push(handler.callback())
                }
              }

              await Promise.allSettled(refreshPromises)
            }
          }
        }

        // Remove the approval from state after successful backend call
        set(draft => {
          if (draft.approvals[key]) {
            draft.approvals[key] = draft.approvals[key].filter(
              a => a.tool_call_id !== toolCallId
            )
          }
        })
      },

      registerRefreshHandler: (conversationId, refreshAction, callback) => {
        const handlers = refreshHandlerRegistry.get(conversationId) || []

        // Remove existing handler for the same refresh action to avoid duplicates
        const filteredHandlers = handlers.filter(h => h.refreshAction !== refreshAction)

        filteredHandlers.push({
          conversationId,
          refreshAction,
          callback
        })

        refreshHandlerRegistry.set(conversationId, filteredHandlers)
      },

      unregisterRefreshHandlers: (conversationId) => {
        refreshHandlerRegistry.delete(conversationId)
      },

      executeRefreshHandlers: async (conversationId, toolNames) => {
        const handlers = refreshHandlerRegistry.get(conversationId)
        if (!handlers || handlers.length === 0) {
          return
        }

        // Get required refresh actions for the approved tools
        const requiredActions = toolApprovalConfig.getRequiredRefreshActions(toolNames)
        if (requiredActions.length === 0) {
          return
        }

        // Execute handlers for the required refresh actions
        const refreshPromises: Promise<void>[] = []
        for (const handler of handlers) {
          if (requiredActions.includes(handler.refreshAction)) {
            refreshPromises.push(handler.callback())
          }
        }

        await Promise.allSettled(refreshPromises)
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
 * Use this for TaskDetail, ProjectDetail, AgentChat
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
      processApprovalDecision: state.processApprovalDecision,
      registerRefreshHandler: state.registerRefreshHandler,
      unregisterRefreshHandlers: state.unregisterRefreshHandlers,
      executeRefreshHandlers: state.executeRefreshHandlers
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
