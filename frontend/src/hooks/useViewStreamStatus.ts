import { useEffect, useCallback } from 'react'
import type { ConversationResponse } from '../lib/api'
import { useConversationStreamStore } from '../stores/conversationStreamStore'
import { useUIStore } from '../stores/uiStore'
import type { ViewType } from '../stores/uiStore'

/**
 * Synchronises view activity status from conversationStreamStore.
 * Maps views → conversations via the conversation list, then checks streaming state.
 */
export function useViewStreamStatus(conversations: ConversationResponse[] | null) {
  // Subscribe only to view identity changes (not activityStatus mutations), to avoid
  // an infinite loop where setViewActivityStatus → cachedViews change → effect re-runs → repeat.
  const viewIds = useUIStore(s => s.cachedViews.map(v => v.id).join(','))
  const setViewActivityStatus = useUIStore(s => s.setViewActivityStatus)

  // Return a stable primitive string from the selector — useSyncExternalStore requires
  // getSnapshot to return a cached reference, so returning a new Map on every call causes
  // the "getSnapshot should be cached" warning and infinite loops.
  const streamStateKey = useConversationStreamStore(
    useCallback((state) => {
      const parts: string[] = []
      for (const [id, stream] of state.activeStreams) {
        const isPending = (stream.pendingToolRequests?.length ?? 0) > 0
        parts.push(`${id}:${stream.isStreaming ? 1 : 0}:${isPending ? 1 : 0}`)
      }
      return parts.sort().join(';')
    }, [])
  )

  useEffect(() => {
    if (!conversations) return

    // Build lookup: "entityType:entityId" → conversationId
    const entityToConversation = new Map<string, number>()
    for (const conv of conversations) {
      const key = `${conv.parent_entity_type.toLowerCase()}:${conv.parent_entity_id}`
      // Use the most recent conversation for each entity (list is sorted by last_activity_at desc)
      if (!entityToConversation.has(key)) {
        entityToConversation.set(key, conv.id)
      }
    }

    const { activeStreams } = useConversationStreamStore.getState()

    for (const view of useUIStore.getState().cachedViews) {
      const key = `${view.type as ViewType}:${view.entityId}`
      const conversationId = entityToConversation.get(key)
      if (!conversationId) {
        // No conversation in the list (e.g. completed task excluded by API) — ensure idle
        setViewActivityStatus(view.id, { type: 'idle' })
        continue
      }

      const stream = activeStreams.get(conversationId)
      if (stream?.isStreaming) {
        setViewActivityStatus(view.id, { type: 'agent_working' })
      } else if ((stream?.pendingToolRequests?.length ?? 0) > 0) {
        setViewActivityStatus(view.id, { type: 'action_required' })
      } else {
        setViewActivityStatus(view.id, { type: 'idle' })
      }
    }
  }, [conversations, viewIds, streamStateKey, setViewActivityStatus])
}
