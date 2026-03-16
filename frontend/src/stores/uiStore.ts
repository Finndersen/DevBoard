import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { immer } from 'zustand/middleware/immer'

export type ViewType = 'task' | 'project' | 'codebase' | 'settings' | 'home' | 'mcp-servers' | 'claude-code' | 'tasks-list' | 'projects-list' | 'codebases-list'

export type ActivityStatus =
  | { type: 'idle' }
  | { type: 'new_messages'; count: number }
  | { type: 'agent_working' }
  | { type: 'action_required' }

export interface CachedViewState {
  id: string
  type: ViewType
  entityId: string
  title: string
  activityStatus: ActivityStatus
  hasDraft: boolean
  lastActivity: Date
}

const MAX_CACHED_VIEWS = 12

interface UIState {
  cachedViews: CachedViewState[]
  activeViewId: string | null
  navigationCompactMode: boolean
  conversationsVersion: number
  tasksVersion: number
  draftMessages: Record<string, string>
  shouldPushHistory: boolean
  createTaskModalOpen: boolean
  conversationsPanelCollapsed: boolean
  expandedPanel: 'chat' | 'details'
  unreadConversationIds: number[]
}

interface UIActions {
  // View cache management
  navigateTo: (viewData: Omit<CachedViewState, 'id' | 'activityStatus' | 'hasDraft' | 'lastActivity'>, options?: { fromUrlSync?: boolean }) => string
  evictView: (viewId: string) => void
  switchTab: (viewId: string, options?: { fromUrlSync?: boolean }) => void
  updateView: (viewId: string, updates: Partial<Omit<CachedViewState, 'id'>>) => void

  // Navigation menu
  setNavigationCompactMode: (compact: boolean) => void
  toggleNavigationCompactMode: () => void

  // Conversations
  invalidateConversations: () => void

  // Tasks
  invalidateTasks: () => void

  // Create task modal
  openCreateTaskModal: () => void
  closeCreateTaskModal: () => void

  // Conversations panel
  toggleConversationsPanel: () => void

  // Panel toggle (chat ↔ details)
  setExpandedPanel: (panel: 'chat' | 'details') => void

  // Unread conversations
  addUnreadConversation: (id: number) => void
  removeUnreadConversation: (id: number) => void
  clearUnreadConversations: () => void

  // Activity status updates
  setViewActivityStatus: (viewId: string, status: ActivityStatus) => void
  updateViewActivity: (viewId: string) => void

  // Draft messages
  setHasDraft: (viewType: ViewType, entityId: string, hasDraft: boolean) => void
  saveDraftText: (viewType: ViewType, entityId: string, text: string) => void
  getDraftMessage: (viewType: ViewType, entityId: string) => string
  clearDraftMessage: (viewType: ViewType, entityId: string) => void

  // Utilities
  findViewByEntity: (type: ViewType, entityId: string) => CachedViewState | undefined
  getActiveView: () => CachedViewState | undefined
}

type UIStore = UIState & UIActions

const STORAGE_KEY = 'devboard-ui-state'

function draftKey(viewType: ViewType, entityId: string): string {
  return `${viewType}:${entityId}`
}

export const useUIStore = create<UIStore>()(
  persist(
    immer((set, get) => ({
      // Initial state
      cachedViews: [],
      activeViewId: null,
      navigationCompactMode: false,
      conversationsVersion: 0,
      tasksVersion: 0,
      draftMessages: {},
      shouldPushHistory: false,
      createTaskModalOpen: false,
      conversationsPanelCollapsed: false,
      expandedPanel: 'chat' as const,
      unreadConversationIds: [],

      // View cache management actions
      navigateTo: (viewData, options = {}) => {
        const state = get()

        // Check if view already exists for this entity
        const existingView = state.findViewByEntity(viewData.type, viewData.entityId)
        if (existingView) {
          // Switch to existing view instead of creating duplicate
          set((draft) => {
            const wasActive = draft.activeViewId === existingView.id
            draft.activeViewId = existingView.id
            if (!options.fromUrlSync) {
              draft.shouldPushHistory = !wasActive
            }
            const view = draft.cachedViews.find(v => v.id === existingView.id)
            if (view) {
              view.lastActivity = new Date()
            }
          })
          return existingView.id
        }

        // Create new view
        const newViewId = `view-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`
        const key = draftKey(viewData.type, viewData.entityId)
        const newView: CachedViewState = {
          ...viewData,
          id: newViewId,
          activityStatus: { type: 'idle' },
          hasDraft: !!state.draftMessages[key],
          lastActivity: new Date()
        }

        set((draft) => {
          // LRU eviction: if cache is full, evict least recently used non-draft entry
          if (draft.cachedViews.length >= MAX_CACHED_VIEWS) {
            const candidates = draft.cachedViews
              .filter(v => !v.hasDraft && v.id !== draft.activeViewId)
              .sort((a, b) => new Date(a.lastActivity).getTime() - new Date(b.lastActivity).getTime())

            if (candidates.length > 0) {
              const evictIdx = draft.cachedViews.findIndex(v => v.id === candidates[0].id)
              if (evictIdx !== -1) {
                draft.cachedViews.splice(evictIdx, 1)
              }
            }
            // If all entries are draft-pinned, allow cache to exceed max size
          }

          draft.cachedViews.push(newView)
          draft.activeViewId = newViewId
          if (!options.fromUrlSync) {
            draft.shouldPushHistory = true
          }
        })

        return newViewId
      },

      evictView: (viewId) => {
        set((draft) => {
          const viewIndex = draft.cachedViews.findIndex(v => v.id === viewId)
          if (viewIndex === -1) return

          draft.cachedViews.splice(viewIndex, 1)

          if (draft.activeViewId === viewId) {
            if (draft.cachedViews.length === 0) {
              draft.activeViewId = null
            } else {
              draft.shouldPushHistory = false
              if (viewIndex >= draft.cachedViews.length) {
                draft.activeViewId = draft.cachedViews[draft.cachedViews.length - 1].id
              } else {
                draft.activeViewId = draft.cachedViews[viewIndex].id
              }
            }
          }
        })
      },

      switchTab: (viewId, options = {}) => {
        set((draft) => {
          const view = draft.cachedViews.find(v => v.id === viewId)
          if (view) {
            const wasActive = draft.activeViewId === viewId
            draft.activeViewId = viewId
            if (!options.fromUrlSync) {
              draft.shouldPushHistory = !wasActive
            }
            view.lastActivity = new Date()
          }
        })
      },

      updateView: (viewId, updates) => {
        set((draft) => {
          const view = draft.cachedViews.find(v => v.id === viewId)
          if (view) {
            Object.assign(view, updates)
          }
        })
      },

      // Navigation menu
      setNavigationCompactMode: (compact) => {
        set((draft) => {
          draft.navigationCompactMode = compact
        })
      },

      toggleNavigationCompactMode: () => {
        set((draft) => {
          draft.navigationCompactMode = !draft.navigationCompactMode
        })
      },

      invalidateConversations: () => {
        set((draft) => {
          draft.conversationsVersion += 1
        })
      },

      invalidateTasks: () => {
        set((draft) => {
          draft.tasksVersion += 1
        })
      },

      openCreateTaskModal: () => {
        set((draft) => {
          draft.createTaskModalOpen = true
        })
      },

      closeCreateTaskModal: () => {
        set((draft) => {
          draft.createTaskModalOpen = false
        })
      },

      toggleConversationsPanel: () => {
        set((draft) => {
          draft.conversationsPanelCollapsed = !draft.conversationsPanelCollapsed
        })
      },

      setExpandedPanel: (panel) => {
        set((draft) => {
          draft.expandedPanel = panel
        })
      },

      addUnreadConversation: (id) => {
        set((draft) => {
          if (!draft.unreadConversationIds.includes(id)) {
            draft.unreadConversationIds.push(id)
          }
        })
      },

      removeUnreadConversation: (id) => {
        set((draft) => {
          const idx = draft.unreadConversationIds.indexOf(id)
          if (idx !== -1) {
            draft.unreadConversationIds.splice(idx, 1)
          }
        })
      },

      clearUnreadConversations: () => {
        set((draft) => {
          draft.unreadConversationIds = []
        })
      },

      // Activity status
      setViewActivityStatus: (viewId, status) => {
        set((draft) => {
          const view = draft.cachedViews.find(v => v.id === viewId)
          if (view) {
            view.activityStatus = status
            view.lastActivity = new Date()
          }
        })
      },

      updateViewActivity: (viewId) => {
        set((draft) => {
          const view = draft.cachedViews.find(v => v.id === viewId)
          if (view) {
            view.lastActivity = new Date()
          }
        })
      },

      // Draft messages
      setHasDraft: (viewType, entityId, hasDraft) => {
        set((draft) => {
          const view = draft.cachedViews.find(v => v.type === viewType && v.entityId === entityId)
          if (view && view.hasDraft !== hasDraft) {
            view.hasDraft = hasDraft
          }
        })
      },

      saveDraftText: (viewType, entityId, text) => {
        set((draft) => {
          const key = draftKey(viewType, entityId)
          if (text) {
            draft.draftMessages[key] = text
          } else {
            delete draft.draftMessages[key]
          }
        })
      },

      getDraftMessage: (viewType, entityId) => {
        return get().draftMessages[draftKey(viewType, entityId)] ?? ''
      },

      clearDraftMessage: (viewType, entityId) => {
        set((draft) => {
          const key = draftKey(viewType, entityId)
          delete draft.draftMessages[key]
          const view = draft.cachedViews.find(v => v.type === viewType && v.entityId === entityId)
          if (view) {
            view.hasDraft = false
          }
        })
      },

      // Utilities
      findViewByEntity: (type, entityId) => {
        return get().cachedViews.find(v => v.type === type && v.entityId === entityId)
      },

      getActiveView: () => {
        const state = get()
        return state.cachedViews.find(v => v.id === state.activeViewId)
      }
    })),
    {
      name: STORAGE_KEY,
      partialize: (state) => ({
        navigationCompactMode: state.navigationCompactMode,
        draftMessages: state.draftMessages,
        conversationsPanelCollapsed: state.conversationsPanelCollapsed,
        expandedPanel: state.expandedPanel,
      }),
    }
  )
)
