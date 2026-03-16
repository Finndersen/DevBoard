import { apiClient } from '../lib/api'
import { useApi } from './useApi'

export function useImplementationPlan(taskId: number | null) {
  return useApi(
    () => (taskId ? apiClient.getImplementationPlan(taskId) : Promise.reject(new Error('No task ID'))),
    { immediate: !!taskId },
  )
}
