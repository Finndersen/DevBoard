import { createContext, useContext, useEffect, useRef } from 'react'
import type { ConversationEvent, ToolResult, SystemEvent, SystemEventType } from '../lib/api'

/**
 * Handler function for tool results.
 * Called when a tool execution completes.
 */
export type ToolResultHandler = (result: ToolResult) => void | Promise<void>

/**
 * Matcher function for tool results.
 * Returns true if this handler should be invoked for the given tool.
 */
export type ToolResultMatcher = (toolName: string, result: ToolResult) => boolean

/**
 * Options for tool result handler registration.
 */
export interface ToolResultHandlerOptions {
  /** If true, handler will be called for error results as well. Default: false */
  includeErrors?: boolean
}

/**
 * Handler function for system events.
 * Called when a system event is received.
 */
export type SystemEventHandler = (event: SystemEvent) => void | Promise<void>

/**
 * Matcher function for system events.
 * Returns true if this handler should be invoked for the given event.
 */
export type SystemEventMatcher = (event: SystemEvent) => boolean

/**
 * Handler function for stream completion.
 * Called when a conversation stream finishes processing.
 */
export type StreamCompleteHandler = () => void | Promise<void>

interface ToolResultHandlerEntry {
  handler: ToolResultHandler
  includeErrors: boolean
}

interface EventHandlerRegistry {
  toolResultHandlers: Map<ToolResultMatcher, Set<ToolResultHandlerEntry>>
  systemEventHandlers: Map<SystemEventMatcher, Set<SystemEventHandler>>
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
 * Register a handler for tool call results.
 * The handler is called when the matcher returns true for a tool result.
 * Error results (is_error=true) are automatically skipped.
 *
 * @param matcher - Function that returns true if handler should be called
 * @param handler - Function to call when tool result matches
 *
 * @example
 * Handle specific tool:
 * useToolResultHandler(
 *   (name) => name === 'mcp__devboard_tools__edit_specification',
 *   (result) => refetchSpecification()
 * )
 *
 * @example
 * Handle multiple tools:
 * useToolResultHandler(
 *   (name) => ['edit_specification', 'set_specification_content'].some(t => name.includes(t)),
 *   (result) => refetchSpecification()
 * )
 *
 * @example
 * Handle with pattern matching:
 * useToolResultHandler(
 *   (name) => name.startsWith('mcp__devboard_tools__edit_'),
 *   (result) => refetchAllDocuments()
 * )
 *
 * @example
 * Access result data (errors are automatically skipped):
 * useToolResultHandler(
 *   (name) => name.includes('edit_') || name.includes('set_'),
 *   (result) => console.log('Document modified:', result.result_content)
 * )
 *
 * @example
 * Handle both success and error results:
 * useToolResultHandler(
 *   (name) => name.includes('rebase_task_branch'),
 *   (result) => refreshGitStatus(),
 *   { includeErrors: true }
 * )
 */
export function useToolResultHandler(
  matcher: ToolResultMatcher,
  handler: ToolResultHandler,
  options?: ToolResultHandlerOptions
): void {
  const registry = useEventHandlerRegistry()
  const handlerRef = useRef(handler)
  const includeErrors = options?.includeErrors ?? false

  // Update ref when handler changes
  useEffect(() => {
    handlerRef.current = handler
  }, [handler])

  useEffect(() => {
    // Create entry with wrapped handler and options
    const entry: ToolResultHandlerEntry = {
      handler: (...args) => handlerRef.current(...args),
      includeErrors
    }

    // Register handler
    if (!registry.toolResultHandlers.has(matcher)) {
      registry.toolResultHandlers.set(matcher, new Set())
    }
    registry.toolResultHandlers.get(matcher)!.add(entry)

    // Cleanup: unregister handler
    return () => {
      const entries = registry.toolResultHandlers.get(matcher)
      if (entries) {
        entries.delete(entry)
        if (entries.size === 0) {
          registry.toolResultHandlers.delete(matcher)
        }
      }
    }
  }, [registry, matcher, includeErrors])
}

/**
 * Register a handler for system events.
 * The handler is called when the matcher returns true for a system event.
 *
 * @param matcher - Function that returns true if handler should be called
 * @param handler - Function to call when system event matches
 *
 * @example
 * Handle specific event type:
 * useSystemEventHandler(
 *   (event) => event.type === 'task_updated',
 *   (event) => refetchTask()
 * )
 *
 * @example
 * Handle multiple event types:
 * useSystemEventHandler(
 *   (event) => ['task_updated', 'conversation_updated'].includes(event.type),
 *   (event) => console.log('Entity updated')
 * )
 *
 * @example
 * Handle all events:
 * useSystemEventHandler(
 *   () => true,
 *   (event) => console.log('System event:', event)
 * )
 *
 * @example
 * Filter by entity ID:
 * useSystemEventHandler(
 *   (event) => event.type === 'task_updated' && event.data.task_id === myTaskId,
 *   (event) => {
 *     const { updated_fields } = event.data
 *     if ('status' in updated_fields) {
 *       setStatus(updated_fields.status)
 *     }
 *   }
 * )
 */
export function useSystemEventHandler(matcher: SystemEventMatcher, handler: SystemEventHandler): void {
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
    if (!registry.systemEventHandlers.has(matcher)) {
      registry.systemEventHandlers.set(matcher, new Set())
    }
    registry.systemEventHandlers.get(matcher)!.add(wrappedHandler)

    // Cleanup: unregister handler
    return () => {
      const handlers = registry.systemEventHandlers.get(matcher)
      if (handlers) {
        handlers.delete(wrappedHandler)
        if (handlers.size === 0) {
          registry.systemEventHandlers.delete(matcher)
        }
      }
    }
  }, [registry, matcher])
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
  // Handle tool results
  if (event.event_type === 'tool_result') {
    const toolName = toolCallMap.get(event.tool_call_id)
    if (!toolName) return

    const isError = event.is_error

    // Find matching handlers (filter by includeErrors when result is an error)
    const matchingHandlers: ToolResultHandler[] = []
    for (const [matcher, entries] of registry.toolResultHandlers.entries()) {
      if (matcher(toolName, event)) {
        for (const entry of entries) {
          // Skip error results unless handler explicitly wants them
          if (isError && !entry.includeErrors) continue
          matchingHandlers.push(entry.handler)
        }
      }
    }

    // Call all matching handlers (use allSettled to prevent one failure from stopping others)
    const results = await Promise.allSettled(matchingHandlers.map(handler => handler(event)))

    // Log any handler failures for debugging
    results.forEach((result, index) => {
      if (result.status === 'rejected') {
        console.error(`Tool result handler ${index} failed for tool "${toolName}":`, result.reason)
      }
    })
  }

  // Handle system events
  if (event.event_type === 'system') {
    // Find matching handlers
    const matchingHandlers: SystemEventHandler[] = []
    for (const [matcher, handlers] of registry.systemEventHandlers.entries()) {
      if (matcher(event)) {
        matchingHandlers.push(...Array.from(handlers))
      }
    }

    // Call all matching handlers (use allSettled to prevent one failure from stopping others)
    const results = await Promise.allSettled(matchingHandlers.map(handler => handler(event)))

    // Log any handler failures for debugging
    results.forEach((result, index) => {
      if (result.status === 'rejected') {
        console.error(`System event handler ${index} failed for event type "${event.type}":`, result.reason)
      }
    })
  }
}
