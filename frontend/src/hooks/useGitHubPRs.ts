import { apiClient } from '../lib/api'
import { useApi } from './useApi'

export function useOpenPRs() {
  return useApi(() => apiClient.getOpenPRs())
}
