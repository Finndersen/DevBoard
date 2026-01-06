import { apiClient } from '../lib/api'
import { useApi, useMutation } from './useApi'

export function useDocument(id: number | string | null) {
  return useApi(
    () => (id ? apiClient.getDocument(id) : Promise.reject(new Error('No document ID'))),
    { immediate: !!id }
  )
}

export function useUpdateDocument() {
  return useMutation((data: { id: number | string; content: string }) =>
    apiClient.updateDocument(data.id, data.content)
  )
}
