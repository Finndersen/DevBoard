import { useEffect, useRef } from 'react'
import { apiClient } from '../lib/api'
import { useConversationStreamStore, reconnectingConversations } from '../stores/conversationStreamStore'

const HEALTH_CHECK_INTERVAL_MS = 15_000

/**
 * Periodically polls backend for active executions and fails any frontend
 * streams that have no corresponding backend execution (stale streams).
 * Reconnection is no longer needed since the WebSocket connection is always open.
 */
export function useStreamHealthCheck() {
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)
  // Tracks whether the last backend poll found active executions.
  // Initialized to true so the first check always runs (backend state is unknown).
  const lastBackendHadExecutions = useRef(true)

  useEffect(() => {
    const checkHealth = async () => {
      const { getAllStreamingConversations, setError } = useConversationStreamStore.getState()

      const frontendStreaming = getAllStreamingConversations()

      // Skip if both sides were idle in the last check — avoids unnecessary API calls
      if (frontendStreaming.length === 0 && !lastBackendHadExecutions.current) return

      try {
        const { executions } = await apiClient.getActiveExecutions()
        lastBackendHadExecutions.current = executions.length > 0
        const backendConversationIds = new Set(executions.map(e => e.conversation_id))

        for (const conversationId of frontendStreaming) {
          if (!backendConversationIds.has(conversationId) && !reconnectingConversations.has(conversationId)) {
            console.log('[StreamHealthCheck] Stale frontend stream detected, failing:', conversationId)
            setError(conversationId, new Error('Agent execution ended unexpectedly'))
          }
        }
      } catch (err) {
        console.debug('[StreamHealthCheck] Poll failed:', err)
      }
    }

    // Delay first check to avoid duplicating useStreamBootstrap on startup
    const initialDelay = setTimeout(() => {
      checkHealth()
      intervalRef.current = setInterval(checkHealth, HEALTH_CHECK_INTERVAL_MS)
    }, HEALTH_CHECK_INTERVAL_MS)

    return () => {
      clearTimeout(initialDelay)
      if (intervalRef.current) {
        clearInterval(intervalRef.current)
      }
    }
  }, [])
}
