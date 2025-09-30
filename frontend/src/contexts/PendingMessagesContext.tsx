import { createContext, useContext, useReducer, useEffect, type ReactNode } from 'react'

export interface PendingMessage {
  id: string // unique client-generated ID
  conversationId: number
  text_content: string
  timestamp: string
  status: 'pending' | 'sent' | 'awaiting_approval' | 'failed'
  retryCount: number
  error?: string
}

interface PendingMessagesState {
  // Key structure: `conversation-${conversationId}`
  messages: Record<string, PendingMessage[]>
}

type PendingMessagesAction =
  | { type: 'ADD_PENDING_MESSAGE'; payload: { key: string; message: PendingMessage } }
  | { type: 'UPDATE_MESSAGE_STATUS'; payload: { key: string; messageId: string; status: PendingMessage['status']; error?: string } }
  | { type: 'REMOVE_MESSAGE'; payload: { key: string; messageId: string } }
  | { type: 'CLEAR_CONVERSATION_MESSAGES'; payload: { key: string } }
  | { type: 'LOAD_FROM_STORAGE' }
  | { type: 'CLEANUP_OLD_MESSAGES' }

interface PendingMessagesContextType {
  state: PendingMessagesState
  addPendingMessage: (key: string, message: Omit<PendingMessage, 'id' | 'timestamp' | 'status' | 'retryCount'>) => string
  updateMessageStatus: (key: string, messageId: string, status: PendingMessage['status'], error?: string) => void
  removeMessage: (key: string, messageId: string) => void
  clearConversationMessages: (key: string) => void
  getPendingMessages: (key: string) => PendingMessage[]
  hasPendingMessages: (key: string) => boolean
  retryMessage: (key: string, messageId: string) => void
}

const PendingMessagesContext = createContext<PendingMessagesContextType | undefined>(undefined)

const STORAGE_KEY = 'devboard_pending_messages'
const MAX_AGE_HOURS = 24

function generateMessageId(): string {
  return `msg_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
}

function isMessageExpired(timestamp: string): boolean {
  const messageTime = new Date(timestamp).getTime()
  const now = Date.now()
  const maxAge = MAX_AGE_HOURS * 60 * 60 * 1000 // 24 hours in milliseconds
  return now - messageTime > maxAge
}

function pendingMessagesReducer(state: PendingMessagesState, action: PendingMessagesAction): PendingMessagesState {
  switch (action.type) {
    case 'ADD_PENDING_MESSAGE': {
      const messageWithDefaults: PendingMessage = {
        id: generateMessageId(),
        timestamp: new Date().toISOString(),
        status: 'pending',
        retryCount: 0,
        ...action.payload.message
      }
      
      return {
        ...state,
        messages: {
          ...state.messages,
          [action.payload.key]: [
            ...(state.messages[action.payload.key] || []),
            messageWithDefaults
          ]
        }
      }
    }
    
    case 'UPDATE_MESSAGE_STATUS': {
      const messages = state.messages[action.payload.key] || []
      const updatedMessages = messages.map(message => {
        if (message.id === action.payload.messageId) {
          return {
            ...message,
            status: action.payload.status,
            error: action.payload.error,
            retryCount: action.payload.status === 'failed' ? message.retryCount + 1 : message.retryCount
          }
        }
        return message
      })
      
      return {
        ...state,
        messages: {
          ...state.messages,
          [action.payload.key]: updatedMessages
        }
      }
    }
    
    case 'REMOVE_MESSAGE': {
      const messages = state.messages[action.payload.key] || []
      const filteredMessages = messages.filter(message => message.id !== action.payload.messageId)
      
      return {
        ...state,
        messages: {
          ...state.messages,
          [action.payload.key]: filteredMessages
        }
      }
    }
    
    case 'CLEAR_CONVERSATION_MESSAGES': {
      // eslint-disable-next-line @typescript-eslint/no-unused-vars
      const { [action.payload.key]: removed, ...rest } = state.messages
      return {
        ...state,
        messages: rest
      }
    }
    
    case 'CLEANUP_OLD_MESSAGES': {
      const cleanedMessages: Record<string, PendingMessage[]> = {}
      
      Object.entries(state.messages).forEach(([key, messages]) => {
        const validMessages = messages.filter(message => !isMessageExpired(message.timestamp))
        if (validMessages.length > 0) {
          cleanedMessages[key] = validMessages
        }
      })
      
      return {
        ...state,
        messages: cleanedMessages
      }
    }
    
    case 'LOAD_FROM_STORAGE':
      try {
        const stored = localStorage.getItem(STORAGE_KEY)
        if (stored) {
          const parsedMessages = JSON.parse(stored)
          return {
            ...state,
            messages: parsedMessages
          }
        }
      } catch (error) {
        console.warn('Failed to load pending messages from localStorage:', error)
      }
      return state
    
    default:
      return state
  }
}

interface PendingMessagesProviderProps {
  children: ReactNode
}

export function PendingMessagesProvider({ children }: PendingMessagesProviderProps) {
  const [state, dispatch] = useReducer(pendingMessagesReducer, {
    messages: {}
  })

  // Load from localStorage on mount
  useEffect(() => {
    dispatch({ type: 'LOAD_FROM_STORAGE' })
  }, [])

  // Save to localStorage whenever state changes
  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(state.messages))
    } catch (error) {
      console.warn('Failed to save pending messages to localStorage:', error)
    }
  }, [state.messages])

  // Clean up old messages periodically
  useEffect(() => {
    const cleanupInterval = setInterval(() => {
      dispatch({ type: 'CLEANUP_OLD_MESSAGES' })
    }, 60 * 60 * 1000) // Run cleanup every hour

    return () => clearInterval(cleanupInterval)
  }, [])

  const addPendingMessage = (key: string, message: Omit<PendingMessage, 'id' | 'timestamp' | 'status' | 'retryCount'>): string => {
    const fullMessage: PendingMessage = {
      id: generateMessageId(),
      timestamp: new Date().toISOString(),
      status: 'pending',
      retryCount: 0,
      ...message
    }
    
    dispatch({ type: 'ADD_PENDING_MESSAGE', payload: { key, message: fullMessage } })
    return fullMessage.id
  }

  const updateMessageStatus = (key: string, messageId: string, status: PendingMessage['status'], error?: string) => {
    dispatch({ type: 'UPDATE_MESSAGE_STATUS', payload: { key, messageId, status, error } })
  }

  const removeMessage = (key: string, messageId: string) => {
    dispatch({ type: 'REMOVE_MESSAGE', payload: { key, messageId } })
  }

  const clearConversationMessages = (key: string) => {
    dispatch({ type: 'CLEAR_CONVERSATION_MESSAGES', payload: { key } })
  }

  const getPendingMessages = (key: string): PendingMessage[] => {
    return state.messages[key] || []
  }

  const hasPendingMessages = (key: string): boolean => {
    const messages = state.messages[key]
    return messages && messages.length > 0
  }

  const retryMessage = (key: string, messageId: string) => {
    updateMessageStatus(key, messageId, 'pending')
  }

  const contextValue: PendingMessagesContextType = {
    state,
    addPendingMessage,
    updateMessageStatus,
    removeMessage,
    clearConversationMessages,
    getPendingMessages,
    hasPendingMessages,
    retryMessage
  }

  return (
    <PendingMessagesContext.Provider value={contextValue}>
      {children}
    </PendingMessagesContext.Provider>
  )
}

// eslint-disable-next-line react-refresh/only-export-components
export function usePendingMessages() {
  const context = useContext(PendingMessagesContext)
  if (context === undefined) {
    throw new Error('usePendingMessages must be used within a PendingMessagesProvider')
  }
  return context
}