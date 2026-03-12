import { useState, useEffect, useCallback, useRef } from 'react'
import { apiClient } from '../lib/api'
import type { ActiveExecutionsResponse } from '../lib/api'

const POLL_INTERVAL_ACTIVE_MS = 5000
const POLL_INTERVAL_IDLE_MS = 30000

/**
 * Polls the active executions endpoint.
 * Polls every 5s when the dropdown is open (isOpen=true), every 30s otherwise
 * to keep the badge count updated without excessive requests.
 */
export function useActiveExecutions(isOpen: boolean) {
  const [data, setData] = useState<ActiveExecutionsResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const inFlightRef = useRef(false)

  const fetch = useCallback(async () => {
    if (inFlightRef.current) return
    inFlightRef.current = true
    try {
      const result = await apiClient.getActiveExecutions()
      setData(result)
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch active executions')
    } finally {
      setLoading(false)
      inFlightRef.current = false
    }
  }, [])

  useEffect(() => {
    fetch()
    const interval = setInterval(fetch, isOpen ? POLL_INTERVAL_ACTIVE_MS : POLL_INTERVAL_IDLE_MS)
    return () => clearInterval(interval)
  }, [fetch, isOpen])

  return { data, loading, error, refetch: fetch }
}
