import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { immer } from 'zustand/middleware/immer'
import type { ConversationEvent } from '../lib/api'

export interface ConversationState {
  id: number
  messages: ConversationEvent[]
  draftMessage: string
  scrollPosition: number
  isTyping: boolean
  lastActivity: Date
}

interface ConversationsState {
  conversations: Map<number, ConversationState>
}

interface ConversationsActions {
  // Conversation lifecycle
  addConversation: (conversationId: number) => void
  removeConversation: (conversationId: number) => void
  getConversation: (conversationId: number) => ConversationState | undefined

  // Message management
  setMessages: (conversationId: number, messages: ConversationEvent[]) => void
  addMessage: (conversationId: number, message: ConversationEvent) => void
  clearMessages: (conversationId: number) => void

  // Draft message
  setDraftMessage: (conversationId: number, draft: string) => void
  getDraftMessage: (conversationId: number) => string

  // Scroll position
  setScrollPosition: (conversationId: number, position: number) => void
  getScrollPosition: (conversationId: number) => number

  // Typing indicator
  setIsTyping: (conversationId: number, isTyping: boolean) => void

  // Activity
  updateLastActivity: (conversationId: number) => void

  // Utilities
  hasUnreadMessages: (conversationId: number) => boolean
  getMessageCount: (conversationId: number) => number
}

type ConversationStore = ConversationsState & ConversationsActions

const STORAGE_KEY = 'devboard-conversations'

export const useConversationStore = create<ConversationStore>()(
  persist(
    immer((set, get) => ({
      // Initial state
      conversations: new Map(),

      // Conversation lifecycle
      addConversation: (conversationId) => {
        set((draft) => {
          if (!draft.conversations.has(conversationId)) {
            draft.conversations.set(conversationId, {
              id: conversationId,
              messages: [],
              draftMessage: '',
              scrollPosition: 0,
              isTyping: false,
              lastActivity: new Date()
            })
          }
        })
      },

      removeConversation: (conversationId) => {
        set((draft) => {
          draft.conversations.delete(conversationId)
        })
      },

      getConversation: (conversationId) => {
        return get().conversations.get(conversationId)
      },

      // Message management
      setMessages: (conversationId, messages) => {
        set((draft) => {
          const conversation = draft.conversations.get(conversationId)
          if (conversation) {
            conversation.messages = messages
            conversation.lastActivity = new Date()
          }
        })
      },

      addMessage: (conversationId, message) => {
        set((draft) => {
          const conversation = draft.conversations.get(conversationId)
          if (conversation) {
            conversation.messages.push(message)
            conversation.lastActivity = new Date()
          }
        })
      },

      clearMessages: (conversationId) => {
        set((draft) => {
          const conversation = draft.conversations.get(conversationId)
          if (conversation) {
            conversation.messages = []
            conversation.lastActivity = new Date()
          }
        })
      },

      // Draft message
      setDraftMessage: (conversationId, draftText) => {
        set((draft) => {
          const conversation = draft.conversations.get(conversationId)
          if (conversation) {
            conversation.draftMessage = draftText
          }
        })
      },

      getDraftMessage: (conversationId) => {
        const conversation = get().conversations.get(conversationId)
        return conversation?.draftMessage || ''
      },

      // Scroll position
      setScrollPosition: (conversationId, position) => {
        set((draft) => {
          const conversation = draft.conversations.get(conversationId)
          if (conversation) {
            conversation.scrollPosition = position
          }
        })
      },

      getScrollPosition: (conversationId) => {
        const conversation = get().conversations.get(conversationId)
        return conversation?.scrollPosition || 0
      },

      // Typing indicator
      setIsTyping: (conversationId, isTyping) => {
        set((draft) => {
          const conversation = draft.conversations.get(conversationId)
          if (conversation) {
            conversation.isTyping = isTyping
          }
        })
      },

      // Activity
      updateLastActivity: (conversationId) => {
        set((draft) => {
          const conversation = draft.conversations.get(conversationId)
          if (conversation) {
            conversation.lastActivity = new Date()
          }
        })
      },

      // Utilities
      hasUnreadMessages: (conversationId) => {
        const conversation = get().conversations.get(conversationId)
        return (conversation?.messages.length || 0) > 0
      },

      getMessageCount: (conversationId) => {
        const conversation = get().conversations.get(conversationId)
        return conversation?.messages.length || 0
      }
    })),
    {
      name: STORAGE_KEY,
      partialize: (state) => ({
        conversations: Array.from(state.conversations.entries()).map(([id, conv]) => ({
          id,
          messages: conv.messages,
          draftMessage: conv.draftMessage,
          scrollPosition: conv.scrollPosition,
          // Don't persist typing state
          isTyping: false,
          lastActivity: conv.lastActivity
        }))
      }),
      merge: (persistedState, currentState) => {
        const persisted = persistedState as { conversations: Array<{ id: number } & Omit<ConversationState, 'id'>> }
        if (persisted?.conversations) {
          const conversationsMap = new Map(
            persisted.conversations.map(conv => [conv.id, conv as ConversationState])
          )
          return {
            ...currentState,
            conversations: conversationsMap
          }
        }
        return currentState
      }
    }
  )
)
