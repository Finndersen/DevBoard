import { useState, useCallback, useEffect, useRef } from 'react'
import type { PendingApprovalWithContext } from '../../../stores/approvalsStore'
import { useConversationStreamStore } from '../../../stores/conversationStreamStore'
import { useUIStore, type ViewType } from '../../../stores/uiStore'
import { useStreamCompleteHandler } from '../../../hooks/useConversationEventHandlers'

const DRAFT_SAVE_DELAY_MS = 500

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
  const draftSaveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const hadTextRef = useRef(!!inputMessage.trim())
  const inputMessageRef = useRef(inputMessage)

  const setInputMessage = useCallback((text: string) => {
    inputMessageRef.current = text
    setInputMessageRaw(text)

    // Update hasDraft flag immediately but only on empty↔non-empty transitions
    const hasText = !!text.trim()
    if (hasText !== hadTextRef.current) {
      hadTextRef.current = hasText
      useUIStore.getState().setHasDraft(viewType, entityId, hasText)
    }

    // Debounce persisting the actual draft text
    if (draftSaveTimerRef.current) clearTimeout(draftSaveTimerRef.current)
    draftSaveTimerRef.current = setTimeout(() => {
      useUIStore.getState().saveDraftText(viewType, entityId, text)
    }, DRAFT_SAVE_DELAY_MS)
  }, [viewType, entityId])

  // Save draft text on unmount
  useEffect(() => {
    return () => {
      if (draftSaveTimerRef.current) {
        clearTimeout(draftSaveTimerRef.current)
      }
      // Flush current input to store on unmount (use ref to get latest value, not stale closure)
      useUIStore.getState().saveDraftText(viewType, entityId, inputMessageRef.current)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps -- intentionally capture initial refs only; flushed via ref
  }, [viewType, entityId])

  const handleSendMessage = useCallback(async () => {
    const messageText = inputMessage.trim()
    if (!messageText) return

    if (isStreaming || pendingApprovals.length > 0 || isRunningAction) {
      setQueued(conversationId, true)
      return
    }

    inputMessageRef.current = ''
    setInputMessageRaw('')
    hadTextRef.current = false
    if (draftSaveTimerRef.current) clearTimeout(draftSaveTimerRef.current)
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

    if (
      currentStreamState?.isQueued &&
      inputMessage.trim() &&
      (!currentStreamState.pendingToolRequests || currentStreamState.pendingToolRequests.length === 0)
    ) {
      const messageToSend = inputMessage.trim()
      inputMessageRef.current = ''
      setInputMessageRaw('')
      hadTextRef.current = false
      if (draftSaveTimerRef.current) clearTimeout(draftSaveTimerRef.current)
      useUIStore.getState().clearDraftMessage(viewType, entityId)
      setQueued(conversationId, false)
      sendMessageViaHook(messageToSend)
    }
  }, [conversationId, inputMessage, setQueued, sendMessageViaHook, viewType, entityId]))

  return { inputMessage, setInputMessage, handleSendMessage }
}
