import { useState, useEffect, useCallback, useRef } from 'react'
import { apiClient } from '../lib/api'
import type { ConversationListItem } from '../lib/api'

const POLL_INTERVAL_MS = 30000

export function useConversations() {
  const [data, setData] = useState<ConversationListItem[] | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const inFlightRef = useRef(false)

  const fetchConversations = useCallback(async () => {
    if (inFlightRef.current) return
    inFlightRef.current = true
    try {
      const result = await apiClient.getConversations()
      setData(result)
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch conversations')
    } finally {
      setLoading(false)
      inFlightRef.current = false
    }
  }, [])

  useEffect(() => {
    fetchConversations()
    const interval = setInterval(fetchConversations, POLL_INTERVAL_MS)
    return () => clearInterval(interval)
  }, [fetchConversations])

  return { data, loading, error, refetch: fetchConversations }
}
