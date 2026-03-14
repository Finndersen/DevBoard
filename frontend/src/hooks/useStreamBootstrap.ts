import { useEffect, useRef } from 'react'
import { apiClient } from '../lib/api'
import { useConversationStreamStore } from '../stores/conversationStreamStore'

/**
 * On app startup, fetch active executions once and reconnect WebSocket streams
 * for each. This ensures streaming indicators are correct after page load/refresh.
 */
export function useStreamBootstrap() {
  const hasRun = useRef(false)

  useEffect(() => {
    if (hasRun.current) return
    hasRun.current = true

    const bootstrap = async () => {
      try {
        const { executions } = await apiClient.getActiveExecutions()
        if (executions.length === 0) return

        console.log('[StreamBootstrap] Reconnecting', executions.length, 'active executions')
        const { reconnectStream } = useConversationStreamStore.getState()

        const results = await Promise.allSettled(
          executions.map(e => reconnectStream(e.conversation_id))
        )
        const failures = results.filter(r => r.status === 'rejected')
        if (failures.length > 0) {
          console.warn('[StreamBootstrap]', failures.length, 'reconnection(s) failed:', failures)
        }
      } catch (err) {
        console.error('[StreamBootstrap] Failed to bootstrap streams:', err)
      }
    }

    bootstrap()
  }, [])
}
