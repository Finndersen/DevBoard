import { apiClient } from '../lib/api'
import { useApi } from './useApi'

export function useDocument(id: number | string | null) {
  return useApi(
    () => (id ? apiClient.getDocument(id) : Promise.reject(new Error('No document ID'))),
    { immediate: !!id }
  )
}
