import { create } from 'zustand'
import { immer } from 'zustand/middleware/immer'

export type ProjectEditMode = 'specification' | null

export interface ProjectUIState {
  editMode: ProjectEditMode
  unsavedChanges: Record<string, string> // field name -> unsaved value
  scrollPosition: number
}

interface ProjectUIStoreState {
  projectsUIState: Map<string, ProjectUIState> // Keyed by project ID
}

interface ProjectUIStoreActions {
  // Initialize project UI state
  initProjectUI: (projectId: string) => void

  // Edit mode
  setEditMode: (projectId: string, mode: ProjectEditMode) => void
  getEditMode: (projectId: string) => ProjectEditMode

  // Unsaved changes
  setUnsavedChange: (projectId: string, fieldName: string, value: string) => void
  clearUnsavedChange: (projectId: string, fieldName: string) => void
  clearAllUnsavedChanges: (projectId: string) => void
  getUnsavedChanges: (projectId: string) => Record<string, string>
  hasUnsavedChanges: (projectId: string) => boolean

  // Scroll position
  setScrollPosition: (projectId: string, position: number) => void
  getScrollPosition: (projectId: string) => number

  // Cleanup
  removeProjectUI: (projectId: string) => void
}

type ProjectUIStore = ProjectUIStoreState & ProjectUIStoreActions

const defaultProjectUIState: ProjectUIState = {
  editMode: null,
  unsavedChanges: {},
  scrollPosition: 0
}

export const useProjectUIStore = create<ProjectUIStore>()(
  immer((set, get) => ({
    // Initial state
    projectsUIState: new Map(),

    // Initialize
    initProjectUI: (projectId) => {
      set((draft) => {
        if (!draft.projectsUIState.has(projectId)) {
          draft.projectsUIState.set(projectId, { ...defaultProjectUIState })
        }
      })
    },

    // Edit mode
    setEditMode: (projectId, mode) => {
      set((draft) => {
        const state = draft.projectsUIState.get(projectId)
        if (state) {
          state.editMode = mode
        }
      })
    },

    getEditMode: (projectId) => {
      return get().projectsUIState.get(projectId)?.editMode || null
    },

    // Unsaved changes
    setUnsavedChange: (projectId, fieldName, value) => {
      set((draft) => {
        const state = draft.projectsUIState.get(projectId)
        if (state) {
          state.unsavedChanges[fieldName] = value
        }
      })
    },

    clearUnsavedChange: (projectId, fieldName) => {
      set((draft) => {
        const state = draft.projectsUIState.get(projectId)
        if (state) {
          delete state.unsavedChanges[fieldName]
        }
      })
    },

    clearAllUnsavedChanges: (projectId) => {
      set((draft) => {
        const state = draft.projectsUIState.get(projectId)
        if (state) {
          state.unsavedChanges = {}
        }
      })
    },

    getUnsavedChanges: (projectId) => {
      return get().projectsUIState.get(projectId)?.unsavedChanges || {}
    },

    hasUnsavedChanges: (projectId) => {
      const changes = get().projectsUIState.get(projectId)?.unsavedChanges
      return changes ? Object.keys(changes).length > 0 : false
    },

    // Scroll position
    setScrollPosition: (projectId, position) => {
      set((draft) => {
        const state = draft.projectsUIState.get(projectId)
        if (state) {
          state.scrollPosition = position
        }
      })
    },

    getScrollPosition: (projectId) => {
      return get().projectsUIState.get(projectId)?.scrollPosition || 0
    },

    // Cleanup
    removeProjectUI: (projectId) => {
      set((draft) => {
        draft.projectsUIState.delete(projectId)
      })
    }
  }))
)
