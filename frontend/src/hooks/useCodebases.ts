import { apiClient } from '../lib/api'
import type { Codebase } from '../lib/api'
import { useApi, useMutation } from './useApi'

export function useCodebases() {
  return useApi(() => apiClient.getCodebases())
}

export function useCodebase(id: number | string) {
  return useApi(() => apiClient.getCodebase(id))
}

export function useCreateCodebase() {
  return useMutation((codebase: Omit<Codebase, 'id' | 'repository_url'>) => 
    apiClient.createCodebase(codebase)
  )
}

export function useUpdateCodebase() {
  return useMutation((data: { id: number | string; codebase: Partial<Codebase> }) => 
    apiClient.updateCodebase(data.id, data.codebase)
  )
}

export function useDeleteCodebase() {
  return useMutation((id: number | string) => 
    apiClient.deleteCodebase(id)
  )
}