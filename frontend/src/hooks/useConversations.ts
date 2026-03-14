import { useState, useEffect, useCallback, useRef } from 'react'
import { apiClient } from '../lib/api'
import type { ConversationListItem } from '../lib/api'
import { useUIStore } from '../stores/uiStore'
import { useConversationStreamStore } from '../stores/conversationStreamStore'

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

  // Fetch once on mount
  useEffect(() => {
    fetchConversations()
  }, [fetchConversations])

  // Refetch on stream lifecycle events (active / complete) with debounce
  useEffect(() => {
    const registerCallback = useConversationStreamStore.getState().registerStreamLifecycleCallback
    let debounceTimer: ReturnType<typeof setTimeout> | null = null

    const unsubscribe = registerCallback(() => {
      if (debounceTimer) clearTimeout(debounceTimer)
      debounceTimer = setTimeout(() => {
        fetchConversations()
      }, 300)
    })

    return () => {
      unsubscribe()
      if (debounceTimer) clearTimeout(debounceTimer)
    }
  }, [fetchConversations])

  // Re-fetch when conversationsVersion changes (e.g. after task deletion)
  useEffect(() => {
    if (conversationsVersion > 0) {
      fetchConversations()
    }
  }, [conversationsVersion, fetchConversations])

  return { data, loading, error, refetch: fetchConversations }
}
