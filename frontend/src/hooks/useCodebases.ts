import { apiClient } from '../lib/api'
import type { Codebase, CodebaseCreate, CodebaseClone, CodebaseInit } from '../lib/api'
import { useApi, useMutation } from './useApi'

export function useCodebases() {
  return useApi(() => apiClient.getCodebases())
}

export function useCodebase(id: number | string) {
  return useApi(() => apiClient.getCodebase(id))
}

export function useCreateCodebase() {
  return useMutation((codebase: CodebaseCreate) =>
    apiClient.createCodebase(codebase)
  )
}

export function useCloneCodebase() {
  return useMutation((data: CodebaseClone) =>
    apiClient.cloneCodebase(data)
  )
}

export function useInitCodebase() {
  return useMutation((data: CodebaseInit) =>
    apiClient.initCodebase(data)
  )
}

export function useUpdateCodebase(options?: { updateCache?: (data: Codebase) => void }) {
  return useMutation((data: { id: number | string; codebase: Partial<Codebase> }) =>
    apiClient.updateCodebase(data.id, data.codebase), options
  )
}

export function useDeleteCodebase() {
  return useMutation((id: number | string) =>
    apiClient.deleteCodebase(id)
  )
}
