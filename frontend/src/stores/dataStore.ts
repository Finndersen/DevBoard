import { create } from 'zustand'
import { immer } from 'zustand/middleware/immer'
import { enableMapSet } from 'immer'
import { apiClient } from '../lib/api'
import type { Project, Task, Codebase } from '../lib/api'

// Enable Immer's MapSet plugin for Map and Set support
enableMapSet()

interface DataState {
  // Normalized entity storage
  projects: Map<string, Project>
  tasks: Map<string, Task>
  codebases: Map<string, Codebase>

  // Loading states per entity
  loading: {
    projects: Set<string>
    tasks: Set<string>
    codebases: Set<string>
  }

  // Error states per entity
  errors: {
    projects: Map<string, Error>
    tasks: Map<string, Error>
    codebases: Map<string, Error>
  }
}

interface DataActions {
  // Projects
  fetchProject: (projectId: string) => Promise<Project>
  updateProject: (projectId: string, updates: Partial<Project>) => Promise<Project>
  deleteProject: (projectId: string) => Promise<void>
  setProject: (project: Project) => void

  // Tasks
  fetchTask: (taskId: string) => Promise<Task>
  fetchProjectTasks: (projectId: string) => Promise<Task[]>
  updateTask: (taskId: string, updates: Partial<Task>) => Promise<Task>
  deleteTask: (taskId: string) => Promise<void>
  setTask: (task: Task) => void

  // Codebases
  fetchCodebase: (codebaseId: string) => Promise<Codebase>
  fetchCodebases: () => Promise<Codebase[]>
  updateCodebase: (codebaseId: string, updates: Partial<Codebase>) => Promise<Codebase>
  deleteCodebase: (codebaseId: string) => Promise<void>
  setCodebase: (codebase: Codebase) => void

  // Utilities
  getProject: (projectId: string) => Project | undefined
  getTask: (taskId: string) => Task | undefined
  getCodebase: (codebaseId: string) => Codebase | undefined
  isLoading: (type: 'projects' | 'tasks' | 'codebases', id: string) => boolean
  getError: (type: 'projects' | 'tasks' | 'codebases', id: string) => Error | undefined
  clearError: (type: 'projects' | 'tasks' | 'codebases', id: string) => void
}

type DataStore = DataState & DataActions

export const useDataStore = create<DataStore>()(
  immer((set, get) => ({
    // Initial state
    projects: new Map(),
    tasks: new Map(),
    codebases: new Map(),
    loading: {
      projects: new Set(),
      tasks: new Set(),
      codebases: new Set()
    },
    errors: {
      projects: new Map(),
      tasks: new Map(),
      codebases: new Map()
    },

    // Project actions
    fetchProject: async (projectId) => {
      const state = get()

      // Return cached if available and not loading
      const cached = state.projects.get(projectId)
      if (cached && !state.loading.projects.has(projectId)) {
        return cached
      }

      set((draft) => {
        draft.loading.projects.add(projectId)
        draft.errors.projects.delete(projectId)
      })

      try {
        const project = await apiClient.getProject(projectId)
        set((draft) => {
          draft.projects.set(projectId, project)
          draft.loading.projects.delete(projectId)
        })
        return project
      } catch (error) {
        set((draft) => {
          draft.loading.projects.delete(projectId)
          draft.errors.projects.set(projectId, error as Error)
        })
        throw error
      }
    },

    updateProject: async (projectId, updates) => {
      const updated = await apiClient.updateProject(projectId, updates)
      set((draft) => {
        draft.projects.set(projectId, updated)
      })
      return updated
    },

    deleteProject: async (projectId) => {
      set((draft) => {
        draft.projects.delete(projectId)
      })
    },

    setProject: (project) => {
      set((draft) => {
        draft.projects.set(String(project.id), project)
      })
    },

    // Task actions
    fetchTask: async (taskId) => {
      const state = get()

      // Return cached if available and not loading
      const cached = state.tasks.get(taskId)
      if (cached && !state.loading.tasks.has(taskId)) {
        return cached
      }

      set((draft) => {
        draft.loading.tasks.add(taskId)
        draft.errors.tasks.delete(taskId)
      })

      try {
        const task = await apiClient.getTask(taskId)
        set((draft) => {
          draft.tasks.set(taskId, task)
          draft.loading.tasks.delete(taskId)
        })
        return task
      } catch (error) {
        set((draft) => {
          draft.loading.tasks.delete(taskId)
          draft.errors.tasks.set(taskId, error as Error)
        })
        throw error
      }
    },

    fetchProjectTasks: async (projectId) => {
      const tasks = await apiClient.getProjectTasks(projectId)
      set((draft) => {
        tasks.forEach(task => {
          draft.tasks.set(String(task.id), task)
        })
      })
      return tasks
    },

    updateTask: async (taskId, updates) => {
      const updated = await apiClient.updateTask(taskId, updates)
      set((draft) => {
        draft.tasks.set(taskId, updated)
      })
      return updated
    },

    deleteTask: async (taskId) => {
      set((draft) => {
        draft.tasks.delete(taskId)
      })
    },

    setTask: (task) => {
      set((draft) => {
        draft.tasks.set(String(task.id), task)
      })
    },

    // Codebase actions
    fetchCodebase: async (codebaseId) => {
      const state = get()

      // Return cached if available and not loading
      const cached = state.codebases.get(codebaseId)
      if (cached && !state.loading.codebases.has(codebaseId)) {
        return cached
      }

      set((draft) => {
        draft.loading.codebases.add(codebaseId)
        draft.errors.codebases.delete(codebaseId)
      })

      try {
        const codebase = await apiClient.getCodebase(codebaseId)
        set((draft) => {
          draft.codebases.set(codebaseId, codebase)
          draft.loading.codebases.delete(codebaseId)
        })
        return codebase
      } catch (error) {
        set((draft) => {
          draft.loading.codebases.delete(codebaseId)
          draft.errors.codebases.set(codebaseId, error as Error)
        })
        throw error
      }
    },

    fetchCodebases: async () => {
      const codebases = await apiClient.getCodebases()
      set((draft) => {
        codebases.forEach(codebase => {
          draft.codebases.set(String(codebase.id), codebase)
        })
      })
      return codebases
    },

    updateCodebase: async (codebaseId, updates) => {
      const updated = await apiClient.updateCodebase(codebaseId, updates)
      set((draft) => {
        draft.codebases.set(codebaseId, updated)
      })
      return updated
    },

    deleteCodebase: async (codebaseId) => {
      set((draft) => {
        draft.codebases.delete(codebaseId)
      })
    },

    setCodebase: (codebase) => {
      set((draft) => {
        draft.codebases.set(String(codebase.id), codebase)
      })
    },

    // Utilities
    getProject: (projectId) => {
      return get().projects.get(projectId)
    },

    getTask: (taskId) => {
      return get().tasks.get(taskId)
    },

    getCodebase: (codebaseId) => {
      return get().codebases.get(codebaseId)
    },

    isLoading: (type, id) => {
      return get().loading[type].has(id)
    },

    getError: (type, id) => {
      return get().errors[type].get(id)
    },

    clearError: (type, id) => {
      set((draft) => {
        draft.errors[type].delete(id)
      })
    }
  }))
)
