import { useEffect, useRef } from 'react'
import type { ConversationEvent, ToolCallRequest } from '../../../lib/api'
import { apiClient } from '../../../lib/api'
import { useConversationStreamStore } from '../../../stores/conversationStreamStore'
import { useEventHandlerRegistryForStream } from '../../../hooks/useConversationEventHandlers'

const EMPTY_MESSAGES: ConversationEvent[] = []

export function useStreamSubscription(conversationId: number) {
  const messages = useConversationStreamStore(
    state => state.conversationMessages.get(conversationId)?.messages ?? EMPTY_MESSAGES
  )
  const historyLoaded = useConversationStreamStore(
    state => state.conversationMessages.get(conversationId)?.historyLoaded ?? false
  )
  const isStreaming = useConversationStreamStore(
    state => state.activeStreams.get(conversationId)?.isStreaming ?? false
  )
  const pendingToolRequests = useConversationStreamStore(
    state => state.activeStreams.get(conversationId)?.pendingToolRequests
  ) as ToolCallRequest[] | undefined
  const isQueued = useConversationStreamStore(
    state => state.activeStreams.get(conversationId)?.isQueued ?? false
  )
  const streamState = useConversationStreamStore(state => state.activeStreams.get(conversationId))

  const stopStream = useConversationStreamStore(state => state.stopStream)
  const approveTools = useConversationStreamStore(state => state.approveTools)
  const clearPendingToolRequests = useConversationStreamStore(state => state.clearPendingToolRequests)
  const updateEventHandlerRegistry = useConversationStreamStore(state => state.updateEventHandlerRegistry)
  const setQueued = useConversationStreamStore(state => state.setQueued)
  const setStoreMessages = useConversationStreamStore(state => state.setMessages)
  const reconnectStream = useConversationStreamStore(state => state.reconnectStream)

  const eventHandlerRegistry = useEventHandlerRegistryForStream()
  const reconnectAttempted = useRef<number | null>(null)

  useEffect(() => {
    updateEventHandlerRegistry(conversationId, eventHandlerRegistry)
  }, [conversationId, eventHandlerRegistry, updateEventHandlerRegistry])

  // On mount, check for active execution and reconnect if needed
  useEffect(() => {
    // Only attempt reconnection once per conversation mount
    if (reconnectAttempted.current === conversationId) return
    // Don't reconnect if already streaming
    if (isStreaming) return

    reconnectAttempted.current = conversationId

    apiClient.hasActiveExecution(conversationId).then((hasActive) => {
      if (hasActive && !useConversationStreamStore.getState().isConversationStreaming(conversationId)) {
        console.log('[useStreamSubscription] Active execution found, reconnecting:', conversationId)
        reconnectStream(conversationId)
      }
    }).catch((error) => {
      console.error('[useStreamSubscription] Failed to check active execution:', error)
    })
  }, [conversationId, isStreaming, reconnectStream])

  useEffect(() => {
    console.log('[ConversationChat] Subscription state changed:', {
      conversationId,
      hasStreamState: !!streamState,
      isStreaming,
      messageCount: messages.length,
      pendingToolRequestCount: pendingToolRequests?.length ?? 0,
      allActiveStreams: Array.from(useConversationStreamStore.getState().activeStreams.keys())
    })
  }, [conversationId, streamState, isStreaming, messages, pendingToolRequests])

  return {
    messages,
    historyLoaded,
    isStreaming,
    pendingToolRequests,
    isQueued,
    streamState,
    stopStream,
    approveTools,
    clearPendingToolRequests,
    setQueued,
    setStoreMessages,
  }
}
