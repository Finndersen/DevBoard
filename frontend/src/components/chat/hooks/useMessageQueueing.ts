import { useState, useCallback, useEffect, useRef } from 'react'
import type { PendingApprovalWithContext } from '../../../stores/approvalsStore'
import { useConversationStreamStore } from '../../../stores/conversationStreamStore'
import { useUIStore, type ViewType } from '../../../stores/uiStore'
import { useStreamCompleteHandler } from '../../../hooks/useConversationEventHandlers'

export function useMessageQueueing(
  conversationId: number,
  isStreaming: boolean,
  pendingApprovals: PendingApprovalWithContext[],
  isRunningAction: boolean,
  isQueued: boolean,
  setQueued: (id: number, queued: boolean) => void,
  sendMessageViaHook: (text: string, id?: string) => Promise<void>,
  viewType: ViewType,
  entityId: string,
) {
  const [inputMessage, setInputMessageRaw] = useState(
    () => useUIStore.getState().getDraftMessage(viewType, entityId)
  )

  const setInputMessage = useCallback((text: string) => {
    setInputMessageRaw(text)
    useUIStore.getState().setDraftMessage(viewType, entityId, text)
  }, [viewType, entityId])

  const handleSendMessage = useCallback(async () => {
    const messageText = inputMessage.trim()
    if (!messageText) return

    if (isStreaming || pendingApprovals.length > 0 || isRunningAction) {
      setQueued(conversationId, true)
      return
    }

    setInputMessageRaw('')
    useUIStore.getState().clearDraftMessage(viewType, entityId)
    await sendMessageViaHook(messageText)
  }, [inputMessage, isStreaming, pendingApprovals.length, isRunningAction, conversationId, setQueued, sendMessageViaHook, viewType, entityId])

  // Unqueue when user edits the input text
  const lastInputRef = useRef(inputMessage)
  useEffect(() => {
    const prevInput = lastInputRef.current
    lastInputRef.current = inputMessage
    if (isQueued && inputMessage !== prevInput) {
      setQueued(conversationId, false)
    }
  }, [inputMessage, isQueued, conversationId, setQueued])

  // Auto-send queued message when stream completes successfully
  useStreamCompleteHandler(useCallback(() => {
    const currentStreamState = useConversationStreamStore.getState().activeStreams.get(conversationId)

    // Only send queued message when the agent's entire turn is complete
    // (no pending tool requests that need approval first)
    if (
      currentStreamState?.isQueued &&
      inputMessage.trim() &&
      (!currentStreamState.pendingToolRequests || currentStreamState.pendingToolRequests.length === 0)
    ) {
      const messageToSend = inputMessage.trim()
      setInputMessageRaw('')
      useUIStore.getState().clearDraftMessage(viewType, entityId)
      setQueued(conversationId, false)
      sendMessageViaHook(messageToSend)
    }
  }, [conversationId, inputMessage, setQueued, sendMessageViaHook, viewType, entityId]))

  return { inputMessage, setInputMessage, handleSendMessage }
}
