import { useEffect, useRef } from 'react'
import { apiClient } from '../lib/api'
import type { LogEntry, LogEntryFilters } from '../lib/api'
import { useApi } from './useApi'

export function useLogEntries(filters: LogEntryFilters = {}) {
  const filtersKey = JSON.stringify(filters)
  const result = useApi<LogEntry[]>(() => apiClient.getLogEntries(filters))
  const refetchRef = useRef(result.refetch)
  refetchRef.current = result.refetch

  // Track first render so we don't double-fetch on mount (useApi already fetches immediately)
  const isFirstRender = useRef(true)
  useEffect(() => {
    if (isFirstRender.current) {
      isFirstRender.current = false
      return
    }
    refetchRef.current()
  }, [filtersKey])

  return result
}

export function usePinnedLogEntries(filters: LogEntryFilters = {}) {
  return useLogEntries({ ...filters, pinned: true, status: 'active' })
}
