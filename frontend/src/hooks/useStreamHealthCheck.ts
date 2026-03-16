import { useEffect, useRef } from 'react'
import { apiClient } from '../lib/api'
import { useConversationStreamStore, reconnectingConversations } from '../stores/conversationStreamStore'

const HEALTH_CHECK_INTERVAL_MS = 15_000

/**
 * Periodically polls backend for active executions and reconnects
 * any streams that are running on the backend but have no active
 * frontend WebSocket connection. Also detects stale frontend streams
 * with no corresponding backend execution and completes them.
 */
export function useStreamHealthCheck() {
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)
  // Tracks whether the last backend poll found active executions.
  // Initialized to true so the first check always runs (backend state is unknown).
  const lastBackendHadExecutions = useRef(true)

  useEffect(() => {
    const checkHealth = async () => {
      const { getAllStreamingConversations, reconnectStream, completeStream } =
        useConversationStreamStore.getState()

      const frontendStreaming = getAllStreamingConversations()

      // Skip if both sides were idle in the last check — avoids unnecessary API calls
      if (frontendStreaming.length === 0 && !lastBackendHadExecutions.current) return

      try {
        const { executions } = await apiClient.getActiveExecutions()
        lastBackendHadExecutions.current = executions.length > 0
        const backendConversationIds = new Set(executions.map(e => e.conversation_id))

        // Reconnect backend executions with no active frontend stream
        for (const execution of executions) {
          if (!frontendStreaming.includes(execution.conversation_id)) {
            console.log('[StreamHealthCheck] Orphaned execution detected, reconnecting:', execution.conversation_id)
            reconnectStream(execution.conversation_id).catch(err => {
              console.error('[StreamHealthCheck] Reconnection failed:', execution.conversation_id, err)
            })
          }
        }

        // Complete stale frontend streams with no backend execution
        // Skip conversations mid-reconnect — they may re-establish momentarily
        for (const conversationId of frontendStreaming) {
          if (!backendConversationIds.has(conversationId) && !reconnectingConversations.has(conversationId)) {
            console.log('[StreamHealthCheck] Stale frontend stream detected, completing:', conversationId)
            completeStream(conversationId)
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
