import { useMemo } from 'react'
import { useConversationStreamStore } from '../../stores/conversationStreamStore'
import type { ConversationEvent, ToolCall, ToolResult } from '../../lib/api'

export type CodeReviewStatus = 'not_reviewed' | 'reviewed' | 'stale'

const EMPTY_MESSAGES: ConversationEvent[] = []

export function useCodeReviewStatus(conversationId: number | null): { status: CodeReviewStatus } {
  const messages = useConversationStreamStore(
    state => conversationId !== null ? state.conversationMessages.get(conversationId)?.messages ?? EMPTY_MESSAGES : EMPTY_MESSAGES
  )

  const status = useMemo((): CodeReviewStatus => {
    // Build a map of tool_call_id -> tool_name from all tool_call events
    const toolCallNames = new Map<string, string>()
    for (const event of messages) {
      if (event.event_type === 'tool_call') {
        const toolCall = event as ToolCall
        toolCallNames.set(toolCall.tool_call_id, toolCall.tool_name)
      }
    }

    // Find the latest successful review_code_changes tool result
    let latestReviewTimestamp: string | null = null
    for (const event of messages) {
      if (event.event_type === 'tool_result') {
        const toolResult = event as ToolResult
        if (!toolResult.is_error && toolCallNames.get(toolResult.tool_call_id) === 'review_code_changes') {
          if (latestReviewTimestamp === null || toolResult.timestamp > latestReviewTimestamp) {
            latestReviewTimestamp = toolResult.timestamp
          }
        }
      }
    }

    if (latestReviewTimestamp === null) {
      return 'not_reviewed'
    }

    // Check for any Edit or Write tool calls after the latest review
    for (const event of messages) {
      if (event.event_type === 'tool_call') {
        const toolCall = event as ToolCall
        if (
          (toolCall.tool_name === 'Edit' || toolCall.tool_name === 'Write') &&
          toolCall.timestamp > latestReviewTimestamp
        ) {
          return 'stale'
        }
      }
    }

    return 'reviewed'
  }, [messages])

  return { status }
}
