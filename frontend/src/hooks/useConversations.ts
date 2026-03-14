import { useState, useEffect, useCallback, useRef } from 'react'
import { apiClient } from '../lib/api'
import type { ConversationListItem } from '../lib/api'
import { useUIStore } from '../stores/uiStore'

const POLL_INTERVAL_MS = 30000

export function useConversations() {
  const [data, setData] = useState<ConversationListItem[] | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const inFlightRef = useRef(false)
  const conversationsVersion = useUIStore(s => s.conversationsVersion)

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

  // Re-fetch when conversationsVersion changes (e.g. after task deletion)
  useEffect(() => {
    if (conversationsVersion > 0) {
      fetchConversations()
    }
  }, [conversationsVersion, fetchConversations])

  return { data, loading, error, refetch: fetchConversations }
}
