import { apiClient } from '../lib/api'
import type { Project } from '../lib/api'
import { useApi, useMutation } from './useApi'

export function useProjects() {
  return useApi(() => apiClient.getProjects())
}

export function useProject(id: number | string) {
  return useApi(() => apiClient.getProject(id))
}

export function useCreateProject() {
  return useMutation((project: Omit<Project, 'id' | 'created_at'>) => 
    apiClient.createProject(project)
  )
}

export function useUpdateProject() {
  return useMutation((data: { id: number | string; project: Partial<Project> }) => 
    apiClient.updateProject(data.id, data.project)
  )
}

export function useDeleteProject() {
  return useMutation((id: number | string) => 
    apiClient.deleteProject(id)
  )
}