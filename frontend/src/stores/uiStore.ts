import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { immer } from 'zustand/middleware/immer'
import { enableMapSet } from 'immer'

// Enable Immer's MapSet plugin for Set and Map support
enableMapSet()

export type TabType = 'task' | 'project' | 'codebase' | 'settings' | 'home' | 'mcp-servers' | 'claude-code' | 'tasks-list' | 'projects-list' | 'codebases-list'

export type ActivityStatus =
  | { type: 'idle' }
  | { type: 'new_messages'; count: number }
  | { type: 'agent_working' }
  | { type: 'action_required' }

export interface TabState {
  id: string // Unique tab instance ID (UUID)
  type: TabType
  entityId: string // ID of entity being displayed (or special values like 'main' for home)
  title: string
  activityStatus: ActivityStatus
  hasUnsavedChanges: boolean
  lastActivity: Date
}

interface UIState {
  tabs: TabState[]
  activeTabId: string | null
  navigationCompactMode: boolean
  visitedTabs: Set<string> // Track which tabs have been mounted (session-only, not persisted)
  shouldPushHistory: boolean // Track if next navigation should push to history (session-only, not persisted)
}

interface UIActions {
  // Tab management
  openTab: (tabData: Omit<TabState, 'id' | 'activityStatus' | 'hasUnsavedChanges' | 'lastActivity'>, options?: { fromUrlSync?: boolean }) => string
  closeTab: (tabId: string) => void
  switchTab: (tabId: string, options?: { fromUrlSync?: boolean }) => void
  updateTab: (tabId: string, updates: Partial<Omit<TabState, 'id'>>) => void
  reorderTabs: (fromIndex: number, toIndex: number) => void
  markTabVisited: (tabId: string) => void

  // Navigation menu
  setNavigationCompactMode: (compact: boolean) => void
  toggleNavigationCompactMode: () => void

  // Activity status updates
  setTabActivityStatus: (tabId: string, status: ActivityStatus) => void
  setTabUnsavedChanges: (tabId: string, hasChanges: boolean) => void
  updateTabActivity: (tabId: string) => void

  // Utilities
  findTabByEntity: (type: TabType, entityId: string) => TabState | undefined
  getActiveTab: () => TabState | undefined
}

type UIStore = UIState & UIActions

const STORAGE_KEY = 'devboard-ui-state'

export const useUIStore = create<UIStore>()(
  persist(
    immer((set, get) => ({
      // Initial state
      tabs: [],
      activeTabId: null,
      navigationCompactMode: false,
      visitedTabs: new Set<string>(),
      shouldPushHistory: false,

      // Tab management actions
      openTab: (tabData, options = {}) => {
        const state = get()

        // Check if tab already exists for this entity
        const existingTab = state.findTabByEntity(tabData.type, tabData.entityId)
        if (existingTab) {
          // Switch to existing tab instead of creating duplicate
          set((draft) => {
            const wasActive = draft.activeTabId === existingTab.id
            draft.activeTabId = existingTab.id
            draft.visitedTabs.add(existingTab.id)
            // Only set shouldPushHistory if not from URL sync
            if (!options.fromUrlSync) {
              // Push to history if switching FROM a different tab (not already active)
              // Replace if already on this tab (just updating URL, e.g., query params)
              draft.shouldPushHistory = !wasActive
            }
            const tab = draft.tabs.find(t => t.id === existingTab.id)
            if (tab) {
              tab.lastActivity = new Date()
            }
          })
          return existingTab.id
        }

        // Create new tab
        const newTabId = `tab-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`
        const newTab: TabState = {
          ...tabData,
          id: newTabId,
          activityStatus: { type: 'idle' },
          hasUnsavedChanges: false,
          lastActivity: new Date()
        }

        set((draft) => {
          draft.tabs.push(newTab)
          draft.activeTabId = newTabId
          draft.visitedTabs.add(newTabId)
          // Only set shouldPushHistory if not from URL sync (which means URL already changed)
          if (!options.fromUrlSync) {
            draft.shouldPushHistory = true // Push to history when opening new tab
          }
        })

        return newTabId
      },

      closeTab: (tabId) => {
        set((draft) => {
          const tabIndex = draft.tabs.findIndex(t => t.id === tabId)
          if (tabIndex === -1) return

          // Remove the tab
          draft.tabs.splice(tabIndex, 1)
          draft.visitedTabs.delete(tabId)

          // Update active tab if necessary
          if (draft.activeTabId === tabId) {
            if (draft.tabs.length === 0) {
              draft.activeTabId = null
            } else {
              // When switching to another tab after close, use replace (not push)
              draft.shouldPushHistory = false
              if (tabIndex >= draft.tabs.length) {
                // Select previous tab
                draft.activeTabId = draft.tabs[draft.tabs.length - 1].id
              } else {
                // Select next tab
                draft.activeTabId = draft.tabs[tabIndex].id
              }
            }
          }
        })
      },

      switchTab: (tabId, options = {}) => {
        set((draft) => {
          const tab = draft.tabs.find(t => t.id === tabId)
          if (tab) {
            const wasActive = draft.activeTabId === tabId
            draft.activeTabId = tabId
            draft.visitedTabs.add(tabId)
            // Only set shouldPushHistory if not from URL sync (which means URL already changed)
            if (!options.fromUrlSync) {
              // Push to history if switching FROM a different tab (not already active)
              // Replace if already on this tab (shouldn't happen, but handle it)
              draft.shouldPushHistory = !wasActive
            }
            tab.lastActivity = new Date()
          }
        })
      },

      updateTab: (tabId, updates) => {
        set((draft) => {
          const tab = draft.tabs.find(t => t.id === tabId)
          if (tab) {
            Object.assign(tab, updates)
          }
        })
      },

      reorderTabs: (fromIndex, toIndex) => {
        set((draft) => {
          const [movedTab] = draft.tabs.splice(fromIndex, 1)
          draft.tabs.splice(toIndex, 0, movedTab)
        })
      },

      markTabVisited: (tabId) => {
        set((draft) => {
          draft.visitedTabs.add(tabId)
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

      // Activity status
      setTabActivityStatus: (tabId, status) => {
        set((draft) => {
          const tab = draft.tabs.find(t => t.id === tabId)
          if (tab) {
            tab.activityStatus = status
            tab.lastActivity = new Date()
          }
        })
      },

      setTabUnsavedChanges: (tabId, hasChanges) => {
        set((draft) => {
          const tab = draft.tabs.find(t => t.id === tabId)
          if (tab) {
            tab.hasUnsavedChanges = hasChanges
          }
        })
      },

      updateTabActivity: (tabId) => {
        set((draft) => {
          const tab = draft.tabs.find(t => t.id === tabId)
          if (tab) {
            tab.lastActivity = new Date()
          }
        })
      },

      // Utilities
      findTabByEntity: (type, entityId) => {
        return get().tabs.find(t => t.type === type && t.entityId === entityId)
      },

      getActiveTab: () => {
        const state = get()
        return state.tabs.find(t => t.id === state.activeTabId)
      }
    })),
    {
      name: STORAGE_KEY,
      partialize: (state) => ({
        tabs: state.tabs,
        activeTabId: state.activeTabId,
        navigationCompactMode: state.navigationCompactMode
      })
    }
  )
)
