import type { ConversationEvent, ToolCallRequest, ToolResult } from './api'
import { invokeEventHandlers } from '../hooks/useConversationEventHandlers'
import type { EventHandlerRegistry } from '../hooks/useConversationEventHandlers'

export interface StreamProcessorOptions {
  stream: AsyncGenerator<ConversationEvent>
  onFirstEvent?: () => void | Promise<void>
  onEvent: (event: ConversationEvent) => void | Promise<void>
  getEventHandlerRegistry?: () => EventHandlerRegistry | undefined
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
  const { stream, onFirstEvent, onEvent, getEventHandlerRegistry } = options
  const toolRequests: ToolCallRequest[] = []
  const toolCallMap = new Map<string, string>() // Maps tool_call_id -> tool_name
  const completedToolCalls = new Set<string>() // tool_call_ids that received results
  let eventCount = 0
  let firstEventProcessed = false

  try {
    for await (const event of stream) {
      eventCount++

      console.log('[StreamProcessor] Event received:', {
        eventType: event.event_type,
        eventCount,
        timestamp: new Date().toISOString(),
        ...(event.event_type === 'message' && {
          role: event.role,
          contentPreview: event.text_content?.slice(0, 100)
        }),
        ...(event.event_type === 'tool_call' && {
          toolName: event.tool_name,
          toolCallId: event.tool_call_id
        }),
        ...(event.event_type === 'tool_result' && {
          toolCallId: event.tool_call_id,
          isError: event.is_error
        }),
        ...(event.event_type === 'system' && {
          systemType: event.type,
          data: event.data
        })
      })

      // Invoke first event callback once
      if (!firstEventProcessed && onFirstEvent) {
        await onFirstEvent()
        firstEventProcessed = true
      }

      // Track tool calls for mapping tool_call_id to tool_name
      if (event.event_type === 'tool_call') {
        toolCallMap.set(event.tool_call_id, event.tool_name)
      }

      // Track tool results to detect orphaned tool calls
      if (event.event_type === 'tool_result') {
        completedToolCalls.add(event.tool_call_id)
      }

      // Separate tool requests from other events
      // Note: We still pass ToolCallRequest to onEvent for deduplication
      // (the store will remove duplicate ToolCall but not add the request to messages)
      if (event.event_type === 'tool_call_request') {
        toolRequests.push(event as ToolCallRequest)
      }

      // Invoke event handlers for tool results and system events
      // Error handling ensures handler failures don't crash the stream
      // Uses lazy getter so handlers registered after stream start are still found
      if (getEventHandlerRegistry && (event.event_type === 'tool_call' || event.event_type === 'tool_result' || event.event_type === 'system')) {
        const registry = getEventHandlerRegistry()
        if (registry) {
          try {
            await invokeEventHandlers(event, registry, toolCallMap)
          } catch (error) {
            console.error('Error invoking event handlers:', error)
            // Continue processing stream despite handler errors
          }
        }
      }

      // Process all events (including system events for temporary display during streaming)
      // System events won't persist since the backend doesn't include them in message history
      await onEvent(event)

      // Throw on stream error events to trigger catch block in caller
      // This allows graceful error handling with pending message updates
      if (event.event_type === 'system' && event.type === 'stream_error') {
        const errorMessage = (event.data?.message as string) || 'An error occurred'
        throw new Error(errorMessage)
      }
    }
  } finally {
    // Synthesize error results for tool calls that never received a ToolResult.
    // This handles stream interruptions (client disconnect, cancellation) where
    // the backend never sends ToolResult events for in-flight tools.
    for (const [toolCallId] of toolCallMap) {
      if (!completedToolCalls.has(toolCallId)) {
        const synthesizedResult: ToolResult = {
          event_type: 'tool_result',
          tool_call_id: toolCallId,
          result_content: 'Tool execution was interrupted.',
          is_error: true,
          timestamp: new Date().toISOString(),
        }
        await onEvent(synthesizedResult)
      }
    }
  }

  return { toolRequests, eventCount }
}
