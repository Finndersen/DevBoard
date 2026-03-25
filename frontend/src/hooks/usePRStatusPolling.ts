import { useState, useEffect, useCallback, useRef } from 'react'
import { apiClient } from '../lib/api'
import type { OpenPRsResponse } from '../lib/api'

const POLL_INTERVAL_MS = 60_000

export function usePRStatusPolling() {
  const [data, setData] = useState<OpenPRsResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const fetch = useCallback((forceRefresh?: boolean) => {
    setLoading(true)
    apiClient.getOpenPRs(forceRefresh)
      .then(setData)
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    fetch()
    intervalRef.current = setInterval(() => fetch(), POLL_INTERVAL_MS)
    return () => {
      if (intervalRef.current !== null) {
        clearInterval(intervalRef.current)
      }
    }
  }, [fetch])

  const refetch = useCallback((forceRefresh?: boolean) => {
    fetch(forceRefresh)
  }, [fetch])

  return { data, loading, refetch }
}
