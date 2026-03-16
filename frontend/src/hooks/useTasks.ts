import { useEffect, useRef } from 'react'
import { apiClient } from '../lib/api'
import type { Task, TaskCreate, TaskListItem } from '../lib/api'
import { useApi, useMutation } from './useApi'
import { useUIStore } from '../stores/uiStore'

export function useAllTasks(projectId?: number) {
  const tasksVersion = useUIStore(s => s.tasksVersion)
  const result = useApi<TaskListItem[]>(() => apiClient.getAllTasks(projectId))
  const refetchRef = useRef(result.refetch)
  refetchRef.current = result.refetch

  useEffect(() => {
    if (tasksVersion > 0) {
      refetchRef.current()
    }
  }, [tasksVersion])

  return result
}

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
  return useMutation((id: number | string, deleteBranch?: boolean) =>
    apiClient.deleteTask(id, deleteBranch)
  )
}

export function useTransitionTaskState(options?: { updateCache?: (data: Task) => void }) {
  return useMutation((data: { id: number | string; newState: string }) =>
    apiClient.transitionTaskState(data.id, { new_state: data.newState }), options
  )
}