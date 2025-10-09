import { create } from 'zustand'
import { immer } from 'zustand/middleware/immer'

export type TaskEditMode = 'specification' | 'plan' | null

export interface TaskUIState {
  editMode: TaskEditMode
  unsavedChanges: Record<string, string> // field name -> unsaved value
  scrollPosition: number
  activeTab: 'specification' | 'plan'
}

interface TaskUIStoreState {
  tasksUIState: Map<string, TaskUIState> // Keyed by task ID
}

interface TaskUIStoreActions {
  // Initialize task UI state
  initTaskUI: (taskId: string) => void

  // Edit mode
  setEditMode: (taskId: string, mode: TaskEditMode) => void
  getEditMode: (taskId: string) => TaskEditMode

  // Unsaved changes
  setUnsavedChange: (taskId: string, fieldName: string, value: string) => void
  clearUnsavedChange: (taskId: string, fieldName: string) => void
  clearAllUnsavedChanges: (taskId: string) => void
  getUnsavedChanges: (taskId: string) => Record<string, string>
  hasUnsavedChanges: (taskId: string) => boolean

  // Scroll position
  setScrollPosition: (taskId: string, position: number) => void
  getScrollPosition: (taskId: string) => number

  // Active tab
  setActiveTab: (taskId: string, tab: 'specification' | 'plan') => void
  getActiveTab: (taskId: string) => 'specification' | 'plan'

  // Cleanup
  removeTaskUI: (taskId: string) => void
}

type TaskUIStore = TaskUIStoreState & TaskUIStoreActions

const defaultTaskUIState: TaskUIState = {
  editMode: null,
  unsavedChanges: {},
  scrollPosition: 0,
  activeTab: 'specification'
}

export const useTaskUIStore = create<TaskUIStore>()(
  immer((set, get) => ({
    // Initial state
    tasksUIState: new Map(),

    // Initialize
    initTaskUI: (taskId) => {
      set((draft) => {
        if (!draft.tasksUIState.has(taskId)) {
          draft.tasksUIState.set(taskId, { ...defaultTaskUIState })
        }
      })
    },

    // Edit mode
    setEditMode: (taskId, mode) => {
      set((draft) => {
        const state = draft.tasksUIState.get(taskId)
        if (state) {
          state.editMode = mode
        }
      })
    },

    getEditMode: (taskId) => {
      return get().tasksUIState.get(taskId)?.editMode || null
    },

    // Unsaved changes
    setUnsavedChange: (taskId, fieldName, value) => {
      set((draft) => {
        const state = draft.tasksUIState.get(taskId)
        if (state) {
          state.unsavedChanges[fieldName] = value
        }
      })
    },

    clearUnsavedChange: (taskId, fieldName) => {
      set((draft) => {
        const state = draft.tasksUIState.get(taskId)
        if (state) {
          delete state.unsavedChanges[fieldName]
        }
      })
    },

    clearAllUnsavedChanges: (taskId) => {
      set((draft) => {
        const state = draft.tasksUIState.get(taskId)
        if (state) {
          state.unsavedChanges = {}
        }
      })
    },

    getUnsavedChanges: (taskId) => {
      return get().tasksUIState.get(taskId)?.unsavedChanges || {}
    },

    hasUnsavedChanges: (taskId) => {
      const changes = get().tasksUIState.get(taskId)?.unsavedChanges
      return changes ? Object.keys(changes).length > 0 : false
    },

    // Scroll position
    setScrollPosition: (taskId, position) => {
      set((draft) => {
        const state = draft.tasksUIState.get(taskId)
        if (state) {
          state.scrollPosition = position
        }
      })
    },

    getScrollPosition: (taskId) => {
      return get().tasksUIState.get(taskId)?.scrollPosition || 0
    },

    // Active tab
    setActiveTab: (taskId, tab) => {
      set((draft) => {
        const state = draft.tasksUIState.get(taskId)
        if (state) {
          state.activeTab = tab
        }
      })
    },

    getActiveTab: (taskId) => {
      return get().tasksUIState.get(taskId)?.activeTab || 'specification'
    },

    // Cleanup
    removeTaskUI: (taskId) => {
      set((draft) => {
        draft.tasksUIState.delete(taskId)
      })
    }
  }))
)
