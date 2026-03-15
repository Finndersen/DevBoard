import { useEffect, useCallback } from 'react'
import type { ConversationListItem } from '../lib/api'
import { useConversationStreamStore } from '../stores/conversationStreamStore'
import { useUIStore } from '../stores/uiStore'
import type { TabType } from '../stores/uiStore'

/**
 * Synchronises tab activity status from conversationStreamStore.
 * Maps tabs → conversations via the conversation list, then checks streaming state.
 */
export function useTabStreamStatus(conversations: ConversationListItem[] | null) {
  // Subscribe only to tab identity changes (not activityStatus mutations), to avoid
  // an infinite loop where setTabActivityStatus → tabs change → effect re-runs → repeat.
  const tabIds = useUIStore(s => s.tabs.map(t => t.id).join(','))
  const setTabActivityStatus = useUIStore(s => s.setTabActivityStatus)

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

    for (const tab of useUIStore.getState().tabs) {
      const key = `${tab.type as TabType}:${tab.entityId}`
      const conversationId = entityToConversation.get(key)
      if (!conversationId) {
        // No conversation in the list (e.g. completed task excluded by API) — ensure idle
        setTabActivityStatus(tab.id, { type: 'idle' })
        continue
      }

      const stream = activeStreams.get(conversationId)
      if (stream?.isStreaming) {
        setTabActivityStatus(tab.id, { type: 'agent_working' })
      } else if ((stream?.pendingToolRequests?.length ?? 0) > 0) {
        setTabActivityStatus(tab.id, { type: 'action_required' })
      } else {
        setTabActivityStatus(tab.id, { type: 'idle' })
      }
    }
  }, [conversations, tabIds, streamStateKey, setTabActivityStatus])
}
