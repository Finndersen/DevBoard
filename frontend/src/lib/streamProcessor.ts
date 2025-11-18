import type { ConversationEvent, ToolCallRequest } from './api'
import { invokeEventHandlers } from '../hooks/useConversationEventHandlers'
import type { ToolResultHandler, ToolResultMatcher, SystemEventHandler, SystemEventMatcher } from '../hooks/useConversationEventHandlers'

interface EventHandlerRegistry {
  toolResultHandlers: Map<ToolResultMatcher, Set<ToolResultHandler>>
  systemEventHandlers: Map<SystemEventMatcher, Set<SystemEventHandler>>
}

export interface StreamProcessorOptions {
  stream: AsyncGenerator<ConversationEvent>
  onFirstEvent?: () => void | Promise<void>
  onEvent: (event: ConversationEvent) => void | Promise<void>
  eventHandlerRegistry?: EventHandlerRegistry
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
  const { stream, onFirstEvent, onEvent, eventHandlerRegistry } = options
  const toolRequests: ToolCallRequest[] = []
  const toolCallMap = new Map<string, string>() // Maps tool_call_id -> tool_name
  let eventCount = 0
  let firstEventProcessed = false

  for await (const event of stream) {
    eventCount++

    // Invoke first event callback once
    if (!firstEventProcessed && onFirstEvent) {
      await onFirstEvent()
      firstEventProcessed = true
    }

    // Track tool calls for mapping tool_call_id to tool_name
    if (event.event_type === 'tool_call') {
      toolCallMap.set(event.tool_call_id, event.tool_name)
    }

    // Separate tool requests from other events
    // Note: We still pass ToolCallRequest to onEvent for deduplication
    // (the store will remove duplicate ToolCall but not add the request to messages)
    if (event.event_type === 'tool_call_request') {
      toolRequests.push(event as ToolCallRequest)
    }

    // Invoke event handlers for tool results and system events
    if (eventHandlerRegistry && (event.event_type === 'tool_result' || event.event_type === 'system')) {
      await invokeEventHandlers(event, eventHandlerRegistry, toolCallMap)
    }

    // Skip system events from regular event processing (handlers deal with them)
    if (event.event_type === 'system') {
      continue
    }

    // Process all other events
    await onEvent(event)
  }

  return { toolRequests, eventCount }
}
