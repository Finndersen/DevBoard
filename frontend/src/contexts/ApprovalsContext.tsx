import { createContext, useContext, useReducer, useEffect, useState, type ReactNode } from 'react'
import type { PendingApproval } from '../lib/api'

interface ApprovalsState {
  // Key structure: `project-${projectId}` or `task-${taskId}`
  approvals: Record<string, PendingApproval[]>
}

type ApprovalsAction =
  | { type: 'SET_APPROVALS'; payload: { key: string; approvals: PendingApproval[] } }
  | { type: 'ADD_APPROVAL'; payload: { key: string; approval: PendingApproval } }
  | { type: 'REMOVE_APPROVAL'; payload: { key: string; toolCallId: string } }
  | { type: 'CLEAR_APPROVALS'; payload: { key: string } }

interface ApprovalsContextType {
  state: ApprovalsState
  setApprovals: (key: string, approvals: PendingApproval[]) => void
  addApproval: (key: string, approval: PendingApproval) => void
  removeApproval: (key: string, toolCallId: string) => void
  clearApprovals: (key: string) => void
  getApprovals: (key: string) => PendingApproval[]
  hasApprovals: (key: string) => boolean
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
    console.log('ApprovalsProvider: Initializing from localStorage, found:', stored)
    if (stored) {
      const parsedApprovals = JSON.parse(stored)
      console.log('ApprovalsProvider: Parsed initial approvals:', parsedApprovals)
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

  // Mark as initialized after first render
  useEffect(() => {
    setIsInitialized(true)
  }, [])

  // Save to localStorage whenever state changes, but only after initialization
  useEffect(() => {
    if (isInitialized) {
      try {
        console.log('ApprovalsProvider: Saving to localStorage:', state.approvals)
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
  }, [state.approvals])

  const setApprovals = (key: string, approvals: PendingApproval[]) => {
    console.log('ApprovalsContext: setApprovals called with key:', key, 'approvals:', approvals)
    dispatch({ type: 'SET_APPROVALS', payload: { key, approvals } })
  }

  const addApproval = (key: string, approval: PendingApproval) => {
    dispatch({ type: 'ADD_APPROVAL', payload: { key, approval } })
  }

  const removeApproval = (key: string, toolCallId: string) => {
    dispatch({ type: 'REMOVE_APPROVAL', payload: { key, toolCallId } })
  }

  const clearApprovals = (key: string) => {
    dispatch({ type: 'CLEAR_APPROVALS', payload: { key } })
  }

  const getApprovals = (key: string): PendingApproval[] => {
    return state.approvals[key] || []
  }

  const hasApprovals = (key: string): boolean => {
    const approvals = state.approvals[key]
    return approvals && approvals.length > 0
  }

  const contextValue: ApprovalsContextType = {
    state,
    setApprovals,
    addApproval,
    removeApproval,
    clearApprovals,
    getApprovals,
    hasApprovals
  }

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

