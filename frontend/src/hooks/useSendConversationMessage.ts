import { useCallback } from 'react'
import type { ConversationEvent } from '../lib/api'
import { useConversationStreamStore } from '../stores/conversationStreamStore'
import { useConversationStore } from '../stores/conversationStore'
import { usePendingMessages } from '../contexts/PendingMessagesContext'
import { createConversationPendingKey } from '../utils/approvalKeys'

const AUTO_REFOCUS_THRESHOLD = 0.7

interface UseSendConversationMessageOptions {
  conversationId: number
}

interface SendMessageResult {
  sendMessage: (message: string, existingPendingMessageId?: string) => Promise<void>
}

export function useSendConversationMessage({
  conversationId
}: UseSendConversationMessageOptions): SendMessageResult {
  const pendingKey = createConversationPendingKey(conversationId)

  const { addPendingMessage, updateMessageStatus, removeMessage } = usePendingMessages()

  const startStream = useConversationStreamStore(state => state.startStream)
  const addEvent = useConversationStreamStore(state => state.addEvent)
  const contextUsage = useConversationStreamStore(
    state => state.conversationMessages.get(conversationId)?.contextUsage
  )
  const autoRefocusToggle = useConversationStore(
    state => state.conversations.get(conversationId)?.autoRefocus ?? true
  )

  const sendMessage = useCallback(async (
    messageText: string,
    existingPendingMessageId?: string
  ) => {
    const pendingMessageId = existingPendingMessageId ?? addPendingMessage(pendingKey, {
      conversationId,
      text_content: messageText
    })

    try {
      updateMessageStatus(pendingKey, pendingMessageId, 'sent')

      const userMessage: ConversationEvent = {
        event_type: 'message',
        role: 'user',
        text_content: messageText,
        timestamp: new Date().toISOString()
      }

      const contextWindow = contextUsage?.context_window
      const utilizationExceedsThreshold = contextWindow != null && contextWindow > 0
        ? (contextUsage!.input_tokens / contextWindow) >= AUTO_REFOCUS_THRESHOLD
        : false
      const autoRefocus = autoRefocusToggle && utilizationExceedsThreshold

      await startStream(
        conversationId,
        messageText,
        () => {
          // First event received — add user message and remove pending indicator
          addEvent(conversationId, userMessage)
          removeMessage(pendingKey, pendingMessageId)
        },
        (error) => {
          // Execution failed before any events arrived — show error on pending message
          updateMessageStatus(pendingKey, pendingMessageId, 'failed', error.message)
        },
        { autoRefocus },
      )
    } catch (error) {
      // POST failed
      console.error('Failed to send message:', error)
      let errorMessage = 'Failed to send message'
      if (error instanceof TypeError && error.message === 'Failed to fetch') {
        errorMessage = 'Unable to connect to server. Please check if the backend is running.'
      } else if (error instanceof Error) {
        errorMessage = error.message
      }
      updateMessageStatus(pendingKey, pendingMessageId, 'failed', errorMessage)
    }
  }, [
    pendingKey,
    conversationId,
    addPendingMessage,
    updateMessageStatus,
    removeMessage,
    startStream,
    addEvent,
    contextUsage,
    autoRefocusToggle,
  ])

  return { sendMessage }
}
