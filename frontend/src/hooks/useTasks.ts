import { apiClient } from '../lib/api'
import type { Task, TaskCreate } from '../lib/api'
import { useApi, useMutation } from './useApi'

export function useProjectTasks(projectId: number | string) {
  return useApi(() => apiClient.getProjectTasks(projectId))
}

export function useTask(id: number | string) {
  return useApi(() => apiClient.getTask(id))
}

export function useCreateTask() {
  return useMutation((data: {
    projectId: number | string;
    task: TaskCreate
  }) =>
    apiClient.createTask(data.projectId, data.task)
  )
}

export function useUpdateTask(options?: { updateCache?: (data: Task) => void }) {
  return useMutation((data: { id: number | string; task: Partial<Task> }) => 
    apiClient.updateTask(data.id, data.task), options
  )
}

export function useDeleteTask() {
  return useMutation((id: number | string) => 
    apiClient.deleteTask(id)
  )
}