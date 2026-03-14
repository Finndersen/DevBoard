import { useEffect, useCallback } from 'react'
import type { ConversationListItem } from '../lib/api'
import { useConversationStreamStore } from '../stores/conversationStreamStore'
import { useUIStore } from '../stores/uiStore'
import type { TabType } from '../stores/uiStore'

interface StreamSummary {
  isStreaming: boolean
  hasPendingTools: boolean
}

/**
 * Synchronises tab activity status from conversationStreamStore.
 * Maps tabs → conversations via the conversation list, then checks streaming state.
 */
export function useTabStreamStatus(conversations: ConversationListItem[] | null) {
  const tabs = useUIStore(s => s.tabs)
  const setTabActivityStatus = useUIStore(s => s.setTabActivityStatus)

  // Derive a stable summary of stream states to avoid re-rendering on every Map mutation.
  // Only re-renders when actual streaming/pending-tools state changes.
  const streamSummaries = useConversationStreamStore(
    useCallback((state) => {
      const result = new Map<number, StreamSummary>()
      for (const [id, stream] of state.activeStreams) {
        result.set(id, {
          isStreaming: stream.isStreaming,
          hasPendingTools: (stream.pendingToolRequests?.length ?? 0) > 0,
        })
      }
      return result
    }, []),
    (a, b) => {
      if (a.size !== b.size) return false
      for (const [id, summaryA] of a) {
        const summaryB = b.get(id)
        if (!summaryB || summaryA.isStreaming !== summaryB.isStreaming || summaryA.hasPendingTools !== summaryB.hasPendingTools) {
          return false
        }
      }
      return true
    }
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

    for (const tab of tabs) {
      const key = `${tab.type as TabType}:${tab.entityId}`
      const conversationId = entityToConversation.get(key)
      if (!conversationId) continue

      const summary = streamSummaries.get(conversationId)
      if (summary?.isStreaming) {
        setTabActivityStatus(tab.id, { type: 'agent_working' })
      } else if (summary?.hasPendingTools) {
        setTabActivityStatus(tab.id, { type: 'action_required' })
      } else {
        setTabActivityStatus(tab.id, { type: 'idle' })
      }
    }
  }, [conversations, tabs, streamSummaries, setTabActivityStatus])
}
