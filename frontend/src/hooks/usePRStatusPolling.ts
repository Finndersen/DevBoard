import { useEffect, useCallback, useRef } from 'react'
import { useGithubStore } from '../stores/githubStore'

const POLL_INTERVAL_MS = 60_000

export function usePRStatusPolling() {
  const fetchAll = useGithubStore(s => s.fetchAll)
  const loading = useGithubStore(s => s.loading)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    fetchAll()
    intervalRef.current = setInterval(() => fetchAll(), POLL_INTERVAL_MS)
    return () => {
      if (intervalRef.current !== null) clearInterval(intervalRef.current)
    }
  }, [fetchAll])

  const refetch = useCallback((forceRefresh?: boolean) => {
    fetchAll(forceRefresh)
  }, [fetchAll])

  return { loading, refetch }
}
