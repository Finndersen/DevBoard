import { useCallback } from 'react'
import type { ToolResult } from '../../lib/api'
import { useToolResultHandler } from '../../hooks/useConversationEventHandlers'
import { useConversationStreamStore } from '../../stores/conversationStreamStore'

interface UseProjectConversationHandlersParams {
  activeConversationId: number | null
  setActiveConversationId: (id: number) => void
  updateConversationUrl: (id: number) => void
  invalidateConversations: () => void
}

export function useProjectConversationHandlers({
  activeConversationId,
  setActiveConversationId,
  updateConversationUrl,
  invalidateConversations,
}: UseProjectConversationHandlersParams) {
  const migrateStream = useConversationStreamStore(s => s.migrateStream)

  const refocusHandler = useCallback(async (toolName: string, result: ToolResult) => {
    if (toolName !== 'refocus_conversation') return

    const match = result.result_content?.match(/REFOCUSED conversation_id=(\d+)/)
    if (!match) return

    const newId = parseInt(match[1], 10)
    if (activeConversationId !== null) {
      migrateStream(activeConversationId, newId)
    }
    setActiveConversationId(newId)
    updateConversationUrl(newId)
    invalidateConversations()
  }, [activeConversationId, migrateStream, setActiveConversationId, updateConversationUrl, invalidateConversations])

  useToolResultHandler(refocusHandler)
}
