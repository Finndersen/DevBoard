import { apiClient } from '../lib/api'
import type { Codebase, Project, ProjectCreate } from '../lib/api'
import { useApi, useMutation, type UseApiOptions } from './useApi'

export function useProjects(params?: { parentProjectId?: number; complete?: boolean }) {
  return useApi(() => apiClient.getProjects(params))
}

export function useProject(id: number | string, options?: UseApiOptions) {
  return useApi(() => apiClient.getProject(id), options)
}

export function useCreateProject() {
  return useMutation((project: ProjectCreate) =>
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

// Project Codebases
export function useProjectCodebases(projectId: number | string, options?: UseApiOptions) {
  return useApi<Codebase[]>(() => apiClient.getProjectCodebases(projectId), options)
}

export function useLinkCodebaseToProject() {
  return useMutation((data: { projectId: number | string; codebaseId: number | string }) =>
    apiClient.linkCodebaseToProject(data.projectId, data.codebaseId)
  )
}

export function useUnlinkCodebaseFromProject() {
  return useMutation((data: { projectId: number | string; codebaseId: number | string }) =>
    apiClient.unlinkCodebaseFromProject(data.projectId, data.codebaseId)
  )
}
