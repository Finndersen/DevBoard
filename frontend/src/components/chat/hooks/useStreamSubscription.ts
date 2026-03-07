import { useEffect } from 'react'
import type { ConversationEvent, ToolCallRequest } from '../../../lib/api'
import { useConversationStreamStore } from '../../../stores/conversationStreamStore'
import { useEventHandlerRegistryForStream } from '../../../hooks/useConversationEventHandlers'

const EMPTY_MESSAGES: ConversationEvent[] = []

export function useStreamSubscription(conversationId: number) {
  const messages = useConversationStreamStore(
    state => state.conversationMessages.get(conversationId)?.messages ?? EMPTY_MESSAGES
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

  const eventHandlerRegistry = useEventHandlerRegistryForStream()

  useEffect(() => {
    updateEventHandlerRegistry(conversationId, eventHandlerRegistry)
  }, [conversationId, eventHandlerRegistry, updateEventHandlerRegistry])

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
