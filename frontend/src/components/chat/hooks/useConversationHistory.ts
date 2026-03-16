import { useState, useRef, useEffect } from 'react'
import { apiClient } from '../../../lib/api'
import type { ConversationEvent, ToolCallRequest } from '../../../lib/api'
import type { PendingApprovalWithContext } from '../../../stores/approvalsStore'

export function useConversationHistory(
  conversationId: number,
  messages: ConversationEvent[],
  setStoreMessages: (id: number, msgs: ConversationEvent[]) => void,
  setApprovals: (key: string, approvals: PendingApprovalWithContext[]) => void,
  approvalKey: string,
) {
  const [fetchHistoryError, setFetchHistoryError] = useState<string | null>(null)
  const lastFetchedConversationIdRef = useRef<number | null>(null)

  useEffect(() => {
    // Already have messages in store — no fetch needed
    if (messages.length > 0) {
      lastFetchedConversationIdRef.current = conversationId
      return
    }

    // Always re-fetch when messages are empty. The Zustand store may have been cleared
    // by HMR while React Fast Refresh preserved the ref — without this, the conversation
    // would stay empty until a full page refresh. A duplicate fetch in React StrictMode
    // dev mode (effect runs twice) is a known dev-only limitation and harmless.
    lastFetchedConversationIdRef.current = conversationId

    const fetchHistory = async () => {
      setFetchHistoryError(null)
      try {
        const data = await apiClient.getConversationMessages(conversationId)

        const systemEvents = data.filter(e => e.event_type === 'system')
        if (systemEvents.length > 0) {
          console.log('[ConversationChat] System events received from history:', systemEvents)
        }

        const historyMessages: ConversationEvent[] = []
        const toolRequests: ToolCallRequest[] = []

        data.forEach(event => {
          if (event.event_type === 'tool_call_request') {
            toolRequests.push(event as ToolCallRequest)
          } else {
            historyMessages.push(event)
          }
        })

        console.log('[ConversationChat] Setting messages from history, count:', historyMessages.length, 'types:', historyMessages.map(m => m.event_type))
        setStoreMessages(conversationId, historyMessages)

        if (toolRequests.length > 0) {
          const approvals: PendingApprovalWithContext[] = toolRequests.map((request) => {
            let toolArgs: Record<string, unknown> | null = null
            if (typeof request.tool_args === 'object' && request.tool_args !== null) {
              toolArgs = request.tool_args as Record<string, unknown>
            } else if (typeof request.tool_args === 'string') {
              try {
                toolArgs = JSON.parse(request.tool_args)
              } catch (e) {
                console.warn('Failed to parse tool_args from history:', e)
              }
            }

            return {
              tool_call_id: request.tool_call_id,
              tool_name: request.tool_name,
              tool_args: toolArgs,
              conversationId: conversationId
            }
          })

          setApprovals(approvalKey, approvals)
        }
      } catch (error) {
        console.error('Failed to fetch chat history:', error)
        let errorMessage = 'Failed to load conversation history'
        if (error instanceof TypeError && error.message === 'Failed to fetch') {
          errorMessage = 'Unable to connect to server. Please check if the backend is running.'
        } else if (error instanceof Error) {
          errorMessage = `Failed to load conversation history: ${error.message}`
        }
        setFetchHistoryError(errorMessage)
      }
    }

    fetchHistory()
  }, [conversationId, messages.length, setApprovals, approvalKey, setStoreMessages])

  return { fetchHistoryError, lastFetchedConversationIdRef }
}
