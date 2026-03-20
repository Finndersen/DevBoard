import { createContext, useContext, useEffect, useRef } from 'react'
import type { ConversationEvent, ToolCall, ToolResult, SystemEvent, SystemEventType } from '../lib/api'

/**
 * Handler function for tool calls.
 * Called when a tool is invoked by the agent.
 * Receives both toolName and the full ToolCall event so handler can decide internally whether to act.
 */
export type ToolCallHandler = (toolName: string, toolCall: ToolCall) => void | Promise<void>

/**
 * Handler function for tool results.
 * Called when a tool execution completes.
 * Receives both toolName and result so handler can decide internally whether to act.
 */
export type ToolResultHandler = (toolName: string, result: ToolResult) => void | Promise<void>

/**
 * Handler function for system events.
 * Called when a system event is received.
 * Handler can decide internally whether to act based on event properties.
 */
export type SystemEventHandler = (event: SystemEvent) => void | Promise<void>

/**
 * Handler function for stream completion.
 * Called when a conversation stream finishes processing.
 */
export type StreamCompleteHandler = () => void | Promise<void>

export interface EventHandlerRegistry {
  toolCallHandlers: Set<ToolCallHandler>
  toolResultHandlers: Set<ToolResultHandler>
  systemEventHandlers: Set<SystemEventHandler>
  streamCompleteHandlers: Set<StreamCompleteHandler>
}

const EventHandlerContext = createContext<EventHandlerRegistry | null>(null)

export const EventHandlerProvider = EventHandlerContext.Provider

/**
 * Get the event handler registry from context.
 * @internal - Use useToolResultHandler or useSystemEventHandler instead
 */
function useEventHandlerRegistry(): EventHandlerRegistry {
  const registry = useContext(EventHandlerContext)
  if (!registry) {
    throw new Error('useEventHandlerRegistry must be used within EventHandlerProvider')
  }
  return registry
}

/**
 * Get the event handler registry for passing to stream processor.
 * Use this in components that process conversation streams.
 *
 * @example
 * const eventHandlerRegistry = useEventHandlerRegistryForStream()
 * await processConversationStream({
 *   stream: apiClient.streamConversationMessage(...),
 *   onEvent: handleEvent,
 *   eventHandlerRegistry
 * })
 */
export function useEventHandlerRegistryForStream(): EventHandlerRegistry | undefined {
  // Return undefined if not within provider (optional usage)
  return useContext(EventHandlerContext) || undefined
}

/**
 * Register a handler for tool calls.
 * The handler receives both toolName and the full ToolCall event, and can decide internally whether to act.
 *
 * @param handler - Function to call for each tool call
 *
 * @example
 * useToolCallHandler((toolName, toolCall) => {
 *   if (toolName.includes('execute_implementation_step')) {
 *     const stepNumber = toolCall.tool_args?.step_number
 *     if (typeof stepNumber === 'number') {
 *       markStepRunning(stepNumber)
 *     }
 *   }
 * })
 */
export function useToolCallHandler(handler: ToolCallHandler): void {
  const registry = useEventHandlerRegistry()
  const handlerRef = useRef(handler)

  useEffect(() => {
    handlerRef.current = handler
  }, [handler])

  useEffect(() => {
    const wrappedHandler: ToolCallHandler = (...args) => handlerRef.current(...args)
    registry.toolCallHandlers.add(wrappedHandler)
    return () => {
      registry.toolCallHandlers.delete(wrappedHandler)
    }
  }, [registry])
}

/**
 * Register a handler for tool call results.
 * The handler receives both toolName and result, and can decide internally whether to act.
 *
 * @param handler - Function to call for each tool result
 *
 * @example
 * Handle specific tool:
 * useToolResultHandler((toolName, result) => {
 *   if (toolName === 'edit_specification') {
 *     refetchSpecification()
 *   }
 * })
 *
 * @example
 * Handle multiple tools:
 * useToolResultHandler((toolName, result) => {
 *   if (toolName.includes('edit_specification') || toolName.includes('set_specification_content')) {
 *     refetchSpecification()
 *   }
 * })
 *
 * @example
 * Handle errors explicitly:
 * useToolResultHandler((toolName, result) => {
 *   if (toolName.includes('rebase_task_branch')) {
 *     // Called for both success and error results
 *     refreshGitStatus()
 *   }
 * })
 */
export function useToolResultHandler(handler: ToolResultHandler): void {
  const registry = useEventHandlerRegistry()
  const handlerRef = useRef(handler)

  // Update ref when handler changes
  useEffect(() => {
    handlerRef.current = handler
  }, [handler])

  useEffect(() => {
    // Create wrapper that uses current handler
    const wrappedHandler: ToolResultHandler = (...args) => handlerRef.current(...args)

    // Register handler
    registry.toolResultHandlers.add(wrappedHandler)

    // Cleanup: unregister handler
    return () => {
      registry.toolResultHandlers.delete(wrappedHandler)
    }
  }, [registry])
}

/**
 * Register a handler for system events.
 * The handler receives the event and can decide internally whether to act.
 *
 * @param handler - Function to call for each system event
 *
 * @example
 * Handle specific event type:
 * useSystemEventHandler((event) => {
 *   if (event.type === 'task_updated') {
 *     refetchTask()
 *   }
 * })
 *
 * @example
 * Handle multiple event types:
 * useSystemEventHandler((event) => {
 *   if (event.type === 'task_updated' || event.type === 'conversation_updated') {
 *     console.log('Entity updated')
 *   }
 * })
 *
 * @example
 * Filter by entity ID:
 * useSystemEventHandler((event) => {
 *   if (event.type === 'task_updated' && event.data.task_id === myTaskId) {
 *     const { updated_fields } = event.data
 *     if ('status' in updated_fields) {
 *       setStatus(updated_fields.status)
 *     }
 *   }
 * })
 */
export function useSystemEventHandler(handler: SystemEventHandler): void {
  const registry = useEventHandlerRegistry()
  const handlerRef = useRef(handler)

  // Update ref when handler changes
  useEffect(() => {
    handlerRef.current = handler
  }, [handler])

  useEffect(() => {
    // Create wrapper that uses current handler
    const wrappedHandler: SystemEventHandler = (...args) => handlerRef.current(...args)

    // Register handler
    registry.systemEventHandlers.add(wrappedHandler)

    // Cleanup: unregister handler
    return () => {
      registry.systemEventHandlers.delete(wrappedHandler)
    }
  }, [registry])
}

/**
 * Register a handler for stream completion.
 * The handler is called when a conversation stream finishes processing.
 *
 * @param handler - Function to call when stream completes
 *
 * @example
 * Refresh diff view when stream completes:
 * useStreamCompleteHandler(() => {
 *   if (task?.status === 'implementing') {
 *     refreshDiff()
 *   }
 * })
 */
export function useStreamCompleteHandler(handler: StreamCompleteHandler): void {
  const registry = useEventHandlerRegistry()
  const handlerRef = useRef(handler)

  // Update ref when handler changes
  useEffect(() => {
    handlerRef.current = handler
  }, [handler])

  useEffect(() => {
    // Create wrapper that uses current handler
    const wrappedHandler: StreamCompleteHandler = () => handlerRef.current()

    // Register handler
    registry.streamCompleteHandlers.add(wrappedHandler)

    // Cleanup: unregister handler
    return () => {
      registry.streamCompleteHandlers.delete(wrappedHandler)
    }
  }, [registry])
}

/**
 * Invoke all registered stream complete handlers.
 * Called by the stream store when a stream finishes.
 *
 * @internal
 */
export async function invokeStreamCompleteHandlers(
  registry: EventHandlerRegistry
): Promise<void> {
  const handlers = Array.from(registry.streamCompleteHandlers)

  if (handlers.length === 0) return

  // Call all handlers (use allSettled to prevent one failure from stopping others)
  const results = await Promise.allSettled(handlers.map(handler => handler()))

  // Log any handler failures for debugging
  results.forEach((result, index) => {
    if (result.status === 'rejected') {
      console.error(`Stream complete handler ${index} failed:`, result.reason)
    }
  })
}

/**
 * Process a conversation event and call registered handlers.
 * This is called by the stream processor for each event.
 *
 * @internal
 */
export async function invokeEventHandlers(
  event: ConversationEvent,
  registry: EventHandlerRegistry,
  toolCallMap: Map<string, string>
): Promise<void> {
  // Handle tool calls
  if (event.event_type === 'tool_call') {
    const handlers = Array.from(registry.toolCallHandlers)
    const results = await Promise.allSettled(handlers.map(handler => handler(event.tool_name, event)))
    results.forEach((result, index) => {
      if (result.status === 'rejected') {
        console.error(`Tool call handler ${index} failed for tool "${event.tool_name}":`, result.reason)
      }
    })
  }

  // Handle tool results
  if (event.event_type === 'tool_result') {
    const toolName = toolCallMap.get(event.tool_call_id)
    if (!toolName) return

    const handlers = Array.from(registry.toolResultHandlers)

    // Call all handlers with toolName and result (use allSettled to prevent one failure from stopping others)
    const results = await Promise.allSettled(handlers.map(handler => handler(toolName, event)))

    // Log any handler failures for debugging
    results.forEach((result, index) => {
      if (result.status === 'rejected') {
        console.error(`Tool result handler ${index} failed for tool "${toolName}":`, result.reason)
      }
    })
  }

  // Handle system events
  if (event.event_type === 'system') {
    const handlers = Array.from(registry.systemEventHandlers)

    // Call all handlers (use allSettled to prevent one failure from stopping others)
    const results = await Promise.allSettled(handlers.map(handler => handler(event)))

    // Log any handler failures for debugging
    results.forEach((result, index) => {
      if (result.status === 'rejected') {
        console.error(`System event handler ${index} failed for event type "${event.type}":`, result.reason)
      }
    })
  }
}
