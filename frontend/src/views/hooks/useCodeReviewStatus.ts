import { useMemo } from 'react'
import { useConversationStreamStore } from '../../stores/conversationStreamStore'
import type { ConversationEvent, ToolCall, ToolResult } from '../../lib/api'

export type CodeReviewStatus = 'not_reviewed' | 'reviewed'

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

    // Find the latest successful review_code_changes or execute_implementation_step (code_review) tool result
    let latestReviewTimestamp: string | null = null
    for (const event of messages) {
      if (event.event_type === 'tool_result') {
        const toolResult = event as ToolResult
        const toolName = toolCallNames.get(toolResult.tool_call_id) ?? ''
        const isDirectReview = toolName === 'review_code_changes'
        const isStepReview = toolName === 'execute_implementation_step' && (() => {
          try {
            return JSON.parse(toolResult.result_content)?.step_type === 'code_review'
          } catch {
            return false
          }
        })()
        if (!toolResult.is_error && (isDirectReview || isStepReview)) {
          if (latestReviewTimestamp === null || toolResult.timestamp > latestReviewTimestamp) {
            latestReviewTimestamp = toolResult.timestamp
          }
        }
      }
    }

    return latestReviewTimestamp === null ? 'not_reviewed' : 'reviewed'
  }, [messages])

  return { status }
}
