import type { ConversationEvent, ToolCallRequest } from './api'

export interface StreamProcessorOptions {
  stream: AsyncGenerator<ConversationEvent>
  onFirstEvent?: () => void | Promise<void>
  onEvent: (event: ConversationEvent) => void | Promise<void>
}

export interface StreamProcessorResult {
  toolRequests: ToolCallRequest[]
  eventCount: number
}

/**
 * Process a conversation event stream, filtering tool requests
 * and invoking callbacks for other events.
 *
 * This utility standardizes stream processing across different conversation
 * operations (sending messages, approving tools, executing prompt actions).
 *
 * @param options - Configuration for stream processing
 * @param options.stream - AsyncGenerator of conversation events to process
 * @param options.onFirstEvent - Optional callback invoked once on first event
 * @param options.onEvent - Callback invoked for each non-tool-request event
 * @returns Promise resolving to tool requests and event count
 *
 * @example
 * ```typescript
 * const { toolRequests } = await processConversationStream({
 *   stream: apiClient.streamConversationMessage(conversationId, { message }),
 *   onFirstEvent: () => {
 *     // Handle first event (e.g., add user message)
 *   },
 *   onEvent: (event) => {
 *     // Handle each event (e.g., add to messages)
 *     setMessages(prev => [...prev, event])
 *   }
 * })
 * ```
 */
export async function processConversationStream(
  options: StreamProcessorOptions
): Promise<StreamProcessorResult> {
  const { stream, onFirstEvent, onEvent } = options
  const toolRequests: ToolCallRequest[] = []
  let eventCount = 0
  let firstEventProcessed = false

  for await (const event of stream) {
    eventCount++

    // Invoke first event callback once
    if (!firstEventProcessed && onFirstEvent) {
      await onFirstEvent()
      firstEventProcessed = true
    }

    // Separate tool requests from other events
    if (event.event_type === 'tool_call_request') {
      toolRequests.push(event as ToolCallRequest)
    } else {
      await onEvent(event)
    }
  }

  return { toolRequests, eventCount }
}
