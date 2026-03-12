import { useCallback } from 'react'
import { apiClient } from '../lib/api'
import type { ConversationEvent } from '../lib/api'
import { useConversationStreamStore } from '../stores/conversationStreamStore'
import { usePendingMessages } from '../contexts/PendingMessagesContext'
import { createConversationPendingKey } from '../utils/approvalKeys'

interface UseSendConversationMessageOptions {
  conversationId: number
}

interface SendMessageResult {
  sendMessage: (message: string, existingPendingMessageId?: string) => Promise<void>
}

/**
 * Hook that encapsulates the message sending flow for a conversation.
 *
 * This includes:
 * - Creating and managing pending message state (shows "sending..." in UI)
 * - POSTing the message and consuming WebSocket events via the stream store
 * - Adding the user message to the conversation on first response event
 * - Error handling with status updates
 *
 * Note: This hook does NOT handle queueing. Callers should check if the agent
 * is busy before calling sendMessage, or use ConversationChat which handles
 * queueing internally.
 *
 * Note: Event handler registry must be registered separately via the store's
 * updateEventHandlerRegistry() before messages are sent.
 */
export function useSendConversationMessage({
  conversationId
}: UseSendConversationMessageOptions): SendMessageResult {
  const pendingKey = createConversationPendingKey(conversationId)

  // Pending message management
  const { addPendingMessage, updateMessageStatus, removeMessage } = usePendingMessages()

  // Stream store actions
  const startStream = useConversationStreamStore(state => state.startStream)
  const addEvent = useConversationStreamStore(state => state.addEvent)

  const sendMessage = useCallback(async (
    messageText: string,
    existingPendingMessageId?: string
  ) => {
    // Use existing pending message ID for retry, or create new one
    const pendingMessageId = existingPendingMessageId ?? addPendingMessage(pendingKey, {
      conversationId,
      text_content: messageText
    })

    try {
      updateMessageStatus(pendingKey, pendingMessageId, 'sent')

      // Create user message (will be added on first event)
      const userMessage: ConversationEvent = {
        event_type: 'message',
        role: 'user',
        text_content: messageText,
        timestamp: new Date().toISOString()
      }

      // Create stream from API (POST message, then consume WebSocket events)
      const stream = apiClient.streamConversationMessage(
        conversationId,
        { message: messageText },
      )

      // Start streaming via store
      // Messages are stored separately and preserved automatically
      // User message is added when first event is received (via onFirstEvent)
      // This prevents duplicate display of pending message + user message
      // Event handler registry is looked up from the store's internal map
      let firstEventFired = false
      await startStream(
        conversationId,
        stream,
        () => {
          firstEventFired = true
          // First event received - add user message and remove pending
          addEvent(conversationId, userMessage)
          removeMessage(pendingKey, pendingMessageId)
        },
      )
      if (!firstEventFired) {
        updateMessageStatus(pendingKey, pendingMessageId, 'failed', 'No response received. Please try again.')
      }
    } catch (error) {
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
    addEvent
  ])

  return { sendMessage }
}
