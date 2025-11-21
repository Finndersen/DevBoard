import { createContext, useContext, useReducer, useEffect, useState, useCallback, useMemo, type ReactNode } from 'react'
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

type ApprovalsAction =
  | { type: 'SET_APPROVALS'; payload: { key: string; approvals: PendingApprovalWithContext[] } }
  | { type: 'ADD_APPROVAL'; payload: { key: string; approval: PendingApprovalWithContext } }
  | { type: 'REMOVE_APPROVAL'; payload: { key: string; toolCallId: string } }
  | { type: 'CLEAR_APPROVALS'; payload: { key: string } }

interface ApprovalsContextType {
  state: ApprovalsState
  setApprovals: (key: string, approvals: PendingApprovalWithContext[]) => void
  addApproval: (key: string, approval: PendingApprovalWithContext) => void
  removeApproval: (key: string, toolCallId: string) => void
  clearApprovals: (key: string) => void
  getApprovals: (key: string) => PendingApprovalWithContext[]
  hasApprovals: (key: string) => boolean
  // Method to handle approval decisions with backend integration
  processApprovalDecision: (key: string, toolCallId: string, decision: ToolApprovalDecision) => Promise<void>
  // Refresh handler registry methods
  registerRefreshHandler: (conversationId: number, refreshAction: string, callback: () => Promise<void>) => void
  unregisterRefreshHandlers: (conversationId: number) => void
  // Execute refresh handlers for approved tools
  executeRefreshHandlers: (conversationId: number, toolNames: string[]) => Promise<void>
}

const ApprovalsContext = createContext<ApprovalsContextType | undefined>(undefined)

const STORAGE_KEY = 'devboard_pending_approvals'

function approvalsReducer(state: ApprovalsState, action: ApprovalsAction): ApprovalsState {
  switch (action.type) {
    case 'SET_APPROVALS':
      console.log('ApprovalsContext reducer: SET_APPROVALS', action.payload)
      return {
        ...state,
        approvals: {
          ...state.approvals,
          [action.payload.key]: action.payload.approvals
        }
      }
    
    case 'ADD_APPROVAL':
      return {
        ...state,
        approvals: {
          ...state.approvals,
          [action.payload.key]: [
            ...(state.approvals[action.payload.key] || []),
            action.payload.approval
          ]
        }
      }
    
    case 'REMOVE_APPROVAL':
      return {
        ...state,
        approvals: {
          ...state.approvals,
          [action.payload.key]: (state.approvals[action.payload.key] || [])
            .filter(approval => approval.tool_call_id !== action.payload.toolCallId)
        }
      }
    
    case 'CLEAR_APPROVALS': {
      // eslint-disable-next-line @typescript-eslint/no-unused-vars
      const { [action.payload.key]: removed, ...rest } = state.approvals
      return {
        ...state,
        approvals: rest
      }
    }
    
    default:
      return state
  }
}

interface ApprovalsProviderProps {
  children: ReactNode
}

// Lazy initial state function to load from localStorage synchronously
function initializeApprovals(): ApprovalsState {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored) {
      const parsedApprovals = JSON.parse(stored)
      return { approvals: parsedApprovals }
    }
  } catch (error) {
    console.warn('Failed to load initial approvals from localStorage:', error)
  }
  return { approvals: {} }
}

export function ApprovalsProvider({ children }: ApprovalsProviderProps) {
  const [state, dispatch] = useReducer(approvalsReducer, undefined, initializeApprovals)
  const [isInitialized, setIsInitialized] = useState(false)
  // Refresh handler registry: Map<conversationId, RefreshHandler[]>
  const [refreshHandlers, setRefreshHandlers] = useState<Map<number, RefreshHandler[]>>(new Map())

  // Mark as initialized after first render
  useEffect(() => {
    setIsInitialized(true)
  }, [])

  // Save to localStorage whenever state changes, but only after initialization
  useEffect(() => {
    if (isInitialized) {
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(state.approvals))
      } catch (error) {
        console.warn('Failed to save approvals to localStorage:', error)
      }
    }
  }, [state.approvals, isInitialized])

  // Clean up expired/old approvals (older than 24 hours)
  useEffect(() => {
    const cleanupInterval = setInterval(() => {
      // Note: Currently no automatic cleanup logic implemented
      // In a real implementation, you might want to add timestamps to approvals
      // and clean up expired ones here
    }, 60 * 60 * 1000) // Run cleanup every hour

    return () => clearInterval(cleanupInterval)
  }, [])

  const setApprovals = useCallback((key: string, approvals: PendingApprovalWithContext[]) => {
    console.log('ApprovalsContext: setApprovals called with key:', key, 'approvals:', approvals)
    dispatch({ type: 'SET_APPROVALS', payload: { key, approvals } })
  }, [])

  const addApproval = useCallback((key: string, approval: PendingApprovalWithContext) => {
    dispatch({ type: 'ADD_APPROVAL', payload: { key, approval } })
  }, [])

  const removeApproval = useCallback((key: string, toolCallId: string) => {
    dispatch({ type: 'REMOVE_APPROVAL', payload: { key, toolCallId } })
  }, [])

  const clearApprovals = useCallback((key: string) => {
    dispatch({ type: 'CLEAR_APPROVALS', payload: { key } })
  }, [])

  // Use direct getter functions instead of useCallback to avoid dependency issues
  // This prevents context value from changing on every state update
  const getApprovals = (key: string): PendingApprovalWithContext[] => {
    return state.approvals[key] || []
  }

  const hasApprovals = (key: string): boolean => {
    const approvals = state.approvals[key]
    return approvals && approvals.length > 0
  }

  const executeRefreshHandlers = useCallback(async (conversationId: number, toolNames: string[]): Promise<void> => {
    const handlers = refreshHandlers.get(conversationId)
    if (!handlers || handlers.length === 0) {
      console.log('ApprovalsContext: No refresh handlers registered for conversation:', conversationId)
      return
    }

    // Get required refresh actions for the approved tools
    const requiredActions = toolApprovalConfig.getRequiredRefreshActions(toolNames)
    if (requiredActions.length === 0) {
      console.log('ApprovalsContext: No refresh actions required for tools:', toolNames)
      return
    }

    console.log('ApprovalsContext: Executing refresh handlers:', { conversationId, toolNames, requiredActions })

    // Execute handlers for the required refresh actions
    const refreshPromises: Promise<void>[] = []
    for (const handler of handlers) {
      if (requiredActions.includes(handler.refreshAction)) {
        console.log('ApprovalsContext: Executing refresh action:', handler.refreshAction)
        refreshPromises.push(handler.callback())
      }
    }

    try {
      await Promise.all(refreshPromises)
      console.log('ApprovalsContext: All refresh handlers completed successfully')
    } catch (error) {
      console.error('ApprovalsContext: Some refresh handlers failed:', error)
      // Don't throw - refresh failures shouldn't block the approval flow
    }
  }, [refreshHandlers])

  const processApprovalDecision = useCallback(async (key: string, toolCallId: string, decision: ToolApprovalDecision): Promise<void> => {
    console.log('ApprovalsContext: Processing approval decision:', { key, toolCallId, decision })
    
    // Find the approval to get conversation context
    const approvals = getApprovals(key)
    const approval = approvals.find(a => a.tool_call_id === toolCallId)
    
    if (!approval) {
      console.warn('ApprovalsContext: Could not find approval for toolCallId:', toolCallId)
      return
    }

    // For conversation approvals, we need to send the decision to the backend
    if (approval.conversationId) {
      try {
        console.log('ApprovalsContext: Sending approval to conversation:', approval.conversationId)
        
        const approvalRequest: ToolApprovalRequest = {
          approvals: {
            [toolCallId]: decision
          }
        }

        // Send the approval decision to the backend
        await apiClient.approveConversationTools(approval.conversationId, approvalRequest)
        
        console.log('ApprovalsContext: Successfully sent approval to backend')

        // NEW: Execute refresh handlers after successful backend response
        if (decision.approved) {
          await executeRefreshHandlers(approval.conversationId, [approval.tool_name])
        }
      } catch (error) {
        console.error('ApprovalsContext: Failed to send approval to backend:', error)
        throw error // Re-throw so the UI can handle the error
      }
    }

    // Remove the approval from local state after successful backend call
    removeApproval(key, toolCallId)
  }, [getApprovals, removeApproval, executeRefreshHandlers])

  const registerRefreshHandler = useCallback((conversationId: number, refreshAction: string, callback: () => Promise<void>) => {
    console.log('ApprovalsContext: Registering refresh handler:', { conversationId, refreshAction })
    
    setRefreshHandlers(prev => {
      const updated = new Map(prev)
      const handlers = updated.get(conversationId) || []
      
      // Remove existing handler for the same refresh action to avoid duplicates
      const filteredHandlers = handlers.filter(h => h.refreshAction !== refreshAction)
      
      filteredHandlers.push({
        conversationId,
        refreshAction,
        callback
      })
      
      updated.set(conversationId, filteredHandlers)
      return updated
    })
  }, [])

  const unregisterRefreshHandlers = useCallback((conversationId: number) => {
    console.log('ApprovalsContext: Unregistering refresh handlers for conversation:', conversationId)
    
    setRefreshHandlers(prev => {
      const updated = new Map(prev)
      updated.delete(conversationId)
      return updated
    })
  }, [])

  const contextValue: ApprovalsContextType = useMemo(() => ({
    state,
    setApprovals,
    addApproval,
    removeApproval,
    clearApprovals,
    getApprovals,
    hasApprovals,
    processApprovalDecision,
    registerRefreshHandler,
    unregisterRefreshHandlers,
    executeRefreshHandlers
  }), [
    state,
    setApprovals,
    addApproval,
    removeApproval,
    clearApprovals,
    // getApprovals and hasApprovals omitted - they're stable functions that only read from state
    processApprovalDecision,
    registerRefreshHandler,
    unregisterRefreshHandlers,
    executeRefreshHandlers
  ])

  return (
    <ApprovalsContext.Provider value={contextValue}>
      {children}
    </ApprovalsContext.Provider>
  )
}

// eslint-disable-next-line react-refresh/only-export-components
export function useApprovals() {
  const context = useContext(ApprovalsContext)
  if (context === undefined) {
    throw new Error('useApprovals must be used within an ApprovalsProvider')
  }
  return context
}

