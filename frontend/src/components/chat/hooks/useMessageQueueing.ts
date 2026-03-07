import { useState, useCallback, useEffect } from 'react'
import type { PendingApprovalWithContext } from '../../../stores/approvalsStore'
import { useConversationStreamStore } from '../../../stores/conversationStreamStore'
import { useStreamCompleteHandler } from '../../../hooks/useConversationEventHandlers'

export function useMessageQueueing(
  conversationId: number,
  isStreaming: boolean,
  pendingApprovals: PendingApprovalWithContext[],
  isRunningAction: boolean,
  isQueued: boolean,
  setQueued: (id: number, queued: boolean) => void,
  sendMessageViaHook: (text: string, id?: string) => Promise<void>,
) {
  const [inputMessage, setInputMessage] = useState('')

  const handleSendMessage = useCallback(async () => {
    const messageText = inputMessage.trim()
    if (!messageText) return

    if (isStreaming || pendingApprovals.length > 0 || isRunningAction) {
      setQueued(conversationId, true)
      return
    }

    setInputMessage('')
    await sendMessageViaHook(messageText)
  }, [inputMessage, isStreaming, pendingApprovals.length, isRunningAction, conversationId, setQueued, sendMessageViaHook])

  const handleCancelQueue = useCallback(() => {
    setQueued(conversationId, false)
  }, [conversationId, setQueued])

  // Clear queue state when input is cleared while queued
  useEffect(() => {
    if (isQueued && !inputMessage.trim()) {
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
      setInputMessage('')
      setQueued(conversationId, false)
      sendMessageViaHook(messageToSend)
    }
  }, [conversationId, inputMessage, setQueued, sendMessageViaHook]))

  return { inputMessage, setInputMessage, handleSendMessage, handleCancelQueue }
}
