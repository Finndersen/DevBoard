import { create } from 'zustand'
import { immer } from 'zustand/middleware/immer'
import { enableMapSet } from 'immer'
import { apiClient } from '../lib/api'
import type { GitHubPRStatusResponse, OpenPRItem } from '../lib/api'

// enableMapSet is idempotent — safe to call in multiple store files
enableMapSet()

// Composite PR key: "owner/repo#123"
export function prKey(repoFullName: string, prNumber: number): string {
  return `${repoFullName}#${prNumber}`
}

interface GitHubState {
  byPrKey: Map<string, GitHubPRStatusResponse>
  taskIdToPrKey: Map<number, string>
  openPRItems: OpenPRItem[]
  errors: string[]
  loading: boolean
}

interface GitHubActions {
  fetchAll: (forceRefresh?: boolean) => Promise<void>
  fetchForTask: (taskId: number, forceRefresh?: boolean) => Promise<GitHubPRStatusResponse | null>
  getPrStatusForTask: (taskId: number) => GitHubPRStatusResponse | undefined
}

export const useGithubStore = create<GitHubState & GitHubActions>()(
  immer((set, get) => ({
    byPrKey: new Map(),
    taskIdToPrKey: new Map(),
    openPRItems: [],
    errors: [],
    loading: false,

    fetchAll: async (forceRefresh = false) => {
      set(state => { state.loading = true })
      try {
        const response = await apiClient.getOpenPRs(forceRefresh)
        set(state => {
          state.loading = false
          state.errors = response.errors
          state.openPRItems = response.prs
          for (const item of response.prs) {
            const key = prKey(item.pr_status.repo_full_name, item.pr_status.pr_number)
            state.byPrKey.set(key, item.pr_status)
            if (item.associated_task) {
              state.taskIdToPrKey.set(item.associated_task.task_id, key)
            }
          }
        })
      } catch {
        set(state => { state.loading = false })
      }
    },

    fetchForTask: async (taskId, forceRefresh = false) => {
      try {
        const status = await apiClient.getTaskPRStatus(taskId, forceRefresh)
        set(state => {
          const key = prKey(status.repo_full_name, status.pr_number)
          state.byPrKey.set(key, status)
          state.taskIdToPrKey.set(taskId, key)
        })
        return status
      } catch {
        return null
      }
    },

    getPrStatusForTask: (taskId) => {
      const key = get().taskIdToPrKey.get(taskId)
      return key ? get().byPrKey.get(key) : undefined
    },
  }))
)
