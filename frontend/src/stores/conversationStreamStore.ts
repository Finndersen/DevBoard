import { create } from 'zustand'
import { immer } from 'zustand/middleware/immer'
import type { ConversationEvent, ToolApprovalRequest, ToolCallRequest, ToolCall, SystemEvent } from '../lib/api'
import { apiClient } from '../lib/api'
import { processConversationStream } from '../lib/streamProcessor'
import { createWebSocketEventStream } from '../lib/websocketStream'
import type { EventHandlerRegistry } from '../hooks/useConversationEventHandlers'
import { invokeStreamCompleteHandlers } from '../hooks/useConversationEventHandlers'
import { useNotificationStore } from './notificationStore'

/**
 * State for an active conversation stream (streaming concerns only).
 */
export interface StreamState {
  isStreaming: boolean
  error: Error | null
  startedAt?: number
  pendingToolRequests: ToolCallRequest[]
  isQueued: boolean
}

/**
 * Conversation messages storage (separate from streaming state).
 */
export interface ConversationMessagesState {
  messages: ConversationEvent[]
}

/**
 * Separate map for event handler registries (not in Zustand state).
 * Kept outside the store because:
 * 1. It contains functions (not serializable)
 * 2. It needs to be mutable (Immer freezes objects)
 * 3. It doesn't need to be reactive state
 */
const eventHandlerRegistries = new Map<number, EventHandlerRegistry>()

/**
 * Separate map for conversation ID refs (not in Zustand state).
 * Kept outside the store because refs need to be mutable for closures
 * in processConversationStream to see updates after migration.
 * Immer freezes objects in state, making refs read-only.
 */
const conversationIdRefs = new Map<number, { current: number }>()

/**
 * Stream lifecycle callbacks (not in Zustand state).
 * Fired on 'active' (stream started/reconnected) and 'complete' (stream finished) events.
 * Used by ConversationsPanel to refetch the conversation list at the right moments.
 */
type StreamLifecycleEvent = 'active' | 'complete'
type StreamLifecycleCallback = (conversationId: number, event: StreamLifecycleEvent) => void
const streamLifecycleCallbacks = new Set<StreamLifecycleCallback>()

function notifyStreamLifecycle(conversationId: number, event: StreamLifecycleEvent) {
  for (const cb of streamLifecycleCallbacks) {
    try {
      cb(conversationId, event)
    } catch (err) {
      console.error('[StreamStore] lifecycle callback error:', err)
    }
  }
}

/**
 * Store state containing streaming state and conversation messages.
 */
interface ConversationStreamState {
  /** Streaming state (transient - cleared when stream ends) */
  activeStreams: Map<number, StreamState>
  /** Conversation messages (persistent during session) */
  conversationMessages: Map<number, ConversationMessagesState>
}

/**
 * Store actions for managing conversation streams.
 */
interface ConversationStreamActions {
  /**
   * Start streaming conversation events.
   * The stream runs independently of component lifecycle.
   * Messages are preserved - streaming only affects streaming state.
   *
   * Note: Event handler registry must be registered separately via updateEventHandlerRegistry()
   * before starting the stream. The registry is looked up from the internal map.
   *
   * @param conversationId - The conversation to stream
   * @param stream - The event stream to process
   * @param onFirstEvent - Optional callback invoked once when first event is received
   */
  startStream: (
    conversationId: number,
    stream: AsyncGenerator<ConversationEvent>,
    onFirstEvent?: () => void | Promise<void>,
  ) => Promise<void>

  /**
   * Stop an active stream by requesting a graceful interrupt from the server.
   * The stream will wind down naturally and emit execution_completed with status interrupted.
   *
   * @param conversationId - The conversation to stop streaming
   */
  stopStream: (conversationId: number) => void

  /**
   * Complete a stream naturally (when it finishes).
   * Marks the stream as no longer active and schedules cleanup.
   *
   * @param conversationId - The conversation that finished streaming
   */
  completeStream: (conversationId: number) => void

  /**
   * Add an event to a conversation's message list.
   *
   * @param conversationId - The conversation to add the event to
   * @param event - The event to add
   */
  addEvent: (conversationId: number, event: ConversationEvent) => void

  /**
   * Set messages for a conversation (e.g., from fetched history).
   * Creates stream state if it doesn't exist.
   *
   * @param conversationId - The conversation to set messages for
   * @param messages - The messages to set
   */
  setMessages: (conversationId: number, messages: ConversationEvent[]) => void

  /**
   * Set error state for a stream.
   *
   * @param conversationId - The conversation that encountered an error
   * @param error - The error that occurred
   */
  setError: (conversationId: number, error: Error) => void

  /**
   * Get the stream state for a specific conversation.
   *
   * @param conversationId - The conversation to get state for
   * @returns The stream state, or undefined if not streaming
   */
  getStreamState: (conversationId: number) => StreamState | undefined

  /**
   * Check if a conversation is currently streaming.
   *
   * @param conversationId - The conversation to check
   * @returns True if the conversation is actively streaming
   */
  isConversationStreaming: (conversationId: number) => boolean

  /**
   * Get a list of all conversation IDs that are currently streaming.
   *
   * @returns Array of conversation IDs that have active streams
   */
  getAllStreamingConversations: () => number[]

  /**
   * Approve tools and continue the conversation stream.
   * This starts a new stream with the approval decisions.
   * Messages are preserved automatically.
   *
   * Note: Event handler registry is looked up from the internal map (registered via updateEventHandlerRegistry).
   *
   * @param conversationId - The conversation to continue
   * @param approvals - The tool approval decisions
   */
  approveTools: (
    conversationId: number,
    approvals: Record<string, { approved: boolean; feedback?: string }>
  ) => Promise<void>

  /**
   * Clear messages for a conversation.
   * Used when refreshing conversation history.
   *
   * @param conversationId - The conversation to clear
   */
  clearMessages: (conversationId: number) => void

  /**
   * Clear pending tool requests for a conversation.
   *
   * @param conversationId - The conversation to clear tool requests for
   */
  clearPendingToolRequests: (conversationId: number) => void

  /**
   * Set the queued state for a conversation.
   * When true, indicates a message is queued to be sent after the current stream completes.
   *
   * @param conversationId - The conversation to set queue state for
   * @param queued - Whether a message is queued
   */
  setQueued: (conversationId: number, queued: boolean) => void

  /**
   * Update the event handler registry for an active stream.
   * This allows event handlers to work after navigation when the component remounts.
   *
   * @param conversationId - The conversation to update
   * @param eventHandlerRegistry - The new event handler registry
   */
  updateEventHandlerRegistry: (conversationId: number, eventHandlerRegistry: EventHandlerRegistry | undefined) => void

  /**
   * Migrate an active stream to a new conversation ID.
   * Used when workflow actions create/replace conversations mid-stream.
   *
   * @param oldConversationId - The current conversation ID
   * @param newConversationId - The new conversation ID to migrate to
   */
  migrateStream: (oldConversationId: number, newConversationId: number) => void

  /**
   * Reconnect to an active execution by opening a WebSocket without posting a new message.
   * Used when navigating back to a conversation that has a running execution.
   *
   * @param conversationId - The conversation with an active execution
   */
  reconnectStream: (conversationId: number) => Promise<void>

  /**
   * Register a callback to be invoked on stream lifecycle events ('active' and 'complete').
   * Returns an unsubscribe function.
   */
  registerStreamLifecycleCallback: (cb: StreamLifecycleCallback) => () => void
}

type ConversationStreamStore = ConversationStreamState & ConversationStreamActions

/**
 * Zustand store for managing conversation streams.
 *
 * This store manages all active conversation streams independently of component
 * lifecycle. Streams continue running even when components unmount (e.g., during
 * navigation), allowing for background streaming.
 *
 * Key features:
 * - Multiple concurrent streams (one per conversation)
 * - Navigation-independent streaming
 * - Tool approval workflow with pause/resume
 * - Event handler integration for real-time updates
 * - Proper cleanup and error handling
 *
 * @example
 * ```typescript
 * const startStream = useConversationStreamStore(state => state.startStream)
 * const messages = useConversationStreamStore(
 *   state => state.getStreamState(conversationId)?.messages ?? []
 * )
 * const isStreaming = useConversationStreamStore(
 *   state => state.isConversationStreaming(conversationId)
 * )
 *
 * // Register event handlers first
 * updateEventHandlerRegistry(conversationId, eventHandlerRegistry)
 *
 * // Create a stream and start processing
 * const stream = apiClient.streamConversationMessage(conversationId, { message: "Hello" })
 * await startStream(conversationId, stream)
 * ```
 */
export const useConversationStreamStore = create<ConversationStreamStore>()(
  immer((set, get) => ({
    // Initial state
    activeStreams: new Map(),
    conversationMessages: new Map(),

    // Actions
    startStream: async (conversationId, stream, onFirstEvent) => {
      // Create mutable ref for conversation ID in external map (not in Zustand state)
      // Allows closures to see updates after migration (Immer freezes objects in state)
      const conversationIdRef = { current: conversationId }
      conversationIdRefs.set(conversationId, conversationIdRef)

      // Log before setting state to detect if we're overwriting an existing stream
      const existingStream = get().activeStreams.get(conversationId)
      const existingMessages = get().conversationMessages.get(conversationId)
      console.log('[StreamStore] startStream called:', {
        conversationId,
        hasExistingStream: !!existingStream,
        existingStreamIsStreaming: existingStream?.isStreaming,
        existingMessageCount: existingMessages?.messages?.length ?? 0,
        allActiveStreams: Array.from(get().activeStreams.keys())
      })

      // Initialize streaming state only (messages are separate and preserved)
      // Preserve existing isQueued so queued messages survive stream restarts (e.g., after tool approval)
      const existingIsQueued = get().activeStreams.get(conversationId)?.isQueued ?? false
      set((draft) => {
        draft.activeStreams.set(conversationId, {
          isStreaming: true,
          error: null,
          startedAt: Date.now(),
          pendingToolRequests: [],
          isQueued: existingIsQueued
        })
      })

      console.log('[StreamStore] Stream started:', {
        conversationId
      })

      try {
        // Wrap onFirstEvent to also notify lifecycle callbacks
        const wrappedOnFirstEvent = async () => {
          if (onFirstEvent) await onFirstEvent()
          notifyStreamLifecycle(conversationIdRef.current, 'active')
        }

        // Process the provided stream events and collect tool requests
        // Use conversationIdRef.current so closures see the current ID (may change during migration)
        const { toolRequests } = await processConversationStream({
          stream,
          onFirstEvent: wrappedOnFirstEvent,
          onEvent: (event) => {
            // Add event to store using ref.current (updated by migrateStream)
            get().addEvent(conversationIdRef.current, event)
          },
          eventHandlerRegistry: eventHandlerRegistries.get(conversationIdRef.current)
        })

        // Store tool requests if any
        if (toolRequests.length > 0) {
          set((draft) => {
            const streamState = draft.activeStreams.get(conversationIdRef.current)
            if (streamState) {
              streamState.pendingToolRequests = toolRequests
            }
          })
        }

        // Stream completed successfully
        get().completeStream(conversationIdRef.current)
      } catch (error) {
        if (error instanceof Error) {
          console.error('Stream error:', error)
          get().setError(conversationIdRef.current, error)
          // Re-throw so caller can handle (e.g., mark pending message as failed)
          throw error
        }
      }
    },

    stopStream: (conversationId) => {
      const stream = get().activeStreams.get(conversationId)
      if (stream?.isStreaming) {
        // Request graceful interrupt via HTTP — server will stop the agent and emit execution_completed
        // Optimistically mark as not streaming and clear queue (user stopped intentionally)
        set((draft) => {
          const streamState = draft.activeStreams.get(conversationId)
          if (streamState) {
            streamState.isStreaming = false
            streamState.isQueued = false
          }
        })

        // Request graceful interrupt via HTTP — server will stop the agent and emit execution_completed.
        // Revert optimistic update if the request fails so the user can retry.
        apiClient.interruptConversation(conversationId).catch((error) => {
          console.error('Failed to interrupt conversation:', error)
          set((draft) => {
            const streamState = draft.activeStreams.get(conversationId)
            if (streamState) {
              streamState.isStreaming = true
            }
          })
          useNotificationStore.getState().addNotification({
            type: 'system_error',
            priority: 'high',
            entityType: null,
            entityId: null,
            entityTitle: null,
            conversationId,
            message: 'Failed to stop agent. Please try again.',
            actions: [],
          })
        })
      }
    },

    completeStream: (conversationId) => {
      const stream = get().activeStreams.get(conversationId)
      const convMessages = get().conversationMessages.get(conversationId)
      console.log('[StreamStore] Stream completed:', {
        conversationId,
        messageCount: convMessages?.messages?.length ?? 0
      })

      set((draft) => {
        const draftStream = draft.activeStreams.get(conversationId)
        if (draftStream) {
          draftStream.isStreaming = false
        }
      })

      notifyStreamLifecycle(conversationId, 'complete')

      // Invoke stream complete handlers if registry exists
      const registry = eventHandlerRegistries.get(conversationId)
      if (registry) {
        invokeStreamCompleteHandlers(registry).catch((error) => {
          console.error('Failed to invoke stream complete handlers:', error)
        })
      }

      // Clean up streaming state if no pending tool requests
      // Messages are already copied to component local state, so we don't need to keep them here
      // Use a short delay to ensure React has completed its render cycle
      // Note: eventHandlerRegistries are NOT deleted here - they are managed by React component
      // lifecycle (useEffect cleanup on unmount). Deleting them here causes a race condition
      // where subsequent streams on the same conversation can't find their handlers.
      if (!stream?.pendingToolRequests || stream.pendingToolRequests.length === 0) {
        setTimeout(() => {
          // Re-check in case a new stream started on same conversation ID
          const currentStream = get().activeStreams.get(conversationId)
          if (currentStream && !currentStream.isStreaming) {
            set((draft) => {
              draft.activeStreams.delete(conversationId)
            })
            conversationIdRefs.delete(conversationId)
          }
        }, 100) // Short delay for React render cycle
      }
      // If there are pending tool requests, cleanup happens in clearPendingToolRequests
    },

    addEvent: (conversationId, event) => {
      // Check state before set() for logging
      const messagesBefore = get().conversationMessages.get(conversationId)
      console.log('[StreamStore] addEvent:', {
        conversationId,
        eventType: event.event_type,
        currentMessageCount: messagesBefore?.messages?.length ?? 0,
        ...(event.event_type === 'tool_call' && { toolName: (event as ToolCall).tool_name }),
        ...(event.event_type === 'system' && { systemType: (event as SystemEvent).type })
      })

      set((draft) => {
        // Get or create conversation messages
        let convMessages = draft.conversationMessages.get(conversationId)
        if (!convMessages) {
          convMessages = { messages: [] }
          draft.conversationMessages.set(conversationId, convMessages)
        }

        // Special handling for ToolCallRequest: remove duplicate ToolCall
        // PydanticAI emits ToolCall first, then ToolCallRequest for the same tool_call_id
        // We want to remove the initial ToolCall and keep only the approval workflow
        if (event.event_type === 'tool_call_request') {
          // Find and remove previous ToolCall with same tool_call_id
          const index = convMessages.messages.findIndex(
            (msg) =>
              msg.event_type === 'tool_call' &&
              msg.tool_call_id === event.tool_call_id
          )
          if (index !== -1) {
            convMessages.messages.splice(index, 1)
          }
          // Don't add ToolCallRequest to messages - it stays in approval UI only
          return
        }

        // Add all other events to messages normally
        convMessages.messages.push(event)
      })
    },

    setMessages: (conversationId, messages) => {
      set((draft) => {
        draft.conversationMessages.set(conversationId, { messages })
      })
    },

    setError: (conversationId, error) => {
      set((draft) => {
        const stream = draft.activeStreams.get(conversationId)
        if (stream) {
          stream.error = error
          stream.isStreaming = false
          stream.isQueued = false
        }
      })
    },

    getStreamState: (conversationId) => {
      return get().activeStreams.get(conversationId)
    },

    isConversationStreaming: (conversationId) => {
      const stream = get().activeStreams.get(conversationId)
      return stream?.isStreaming ?? false
    },

    getAllStreamingConversations: () => {
      const activeStreams = get().activeStreams
      const streamingConversations: number[] = []

      activeStreams.forEach((stream, conversationId) => {
        if (stream.isStreaming) {
          streamingConversations.push(conversationId)
        }
      })

      return streamingConversations
    },

    approveTools: async (conversationId, approvals) => {
      const existingStream = get().activeStreams.get(conversationId)

      // Reuse existing ref if available, otherwise create new one in external map
      let conversationIdRef = conversationIdRefs.get(conversationId)
      if (!conversationIdRef) {
        conversationIdRef = { current: conversationId }
        conversationIdRefs.set(conversationId, conversationIdRef)
      }

      // Create or update streaming state (messages are separate and preserved)
      // Preserve existing isQueued state - message should stay queued through approval workflow
      const existingIsQueued = existingStream?.isQueued ?? false
      set((draft) => {
        draft.activeStreams.set(conversationId, {
          isStreaming: true,
          error: null,
          startedAt: Date.now(),
          pendingToolRequests: [],
          isQueued: existingIsQueued
        })
      })

      try {
        // Send approval to backend and start WebSocket stream
        const approvalStream = apiClient.streamApproveConversationTools(
          conversationIdRef.current,
          { approvals } as ToolApprovalRequest,
        )

        // Process stream events and collect any new tool requests
        // Use conversationIdRef.current so closures see the current ID (may change during migration)
        const { toolRequests } = await processConversationStream({
          stream: approvalStream,
          onFirstEvent: () => notifyStreamLifecycle(conversationIdRef.current, 'active'),
          onEvent: (event) => {
            get().addEvent(conversationIdRef.current, event)
          },
          eventHandlerRegistry: eventHandlerRegistries.get(conversationIdRef.current)
        })

        // Store new tool requests if any
        if (toolRequests.length > 0) {
          set((draft) => {
            const streamState = draft.activeStreams.get(conversationIdRef.current)
            if (streamState) {
              streamState.pendingToolRequests = toolRequests
            }
          })
        }

        // Stream completed
        get().completeStream(conversationIdRef.current)
      } catch (error) {
        if (error instanceof Error) {
          console.error('Approval stream error:', error)
          get().setError(conversationIdRef.current, error)
        }
      }
    },

    clearPendingToolRequests: (conversationId) => {
      set((draft) => {
        const stream = draft.activeStreams.get(conversationId)
        if (stream) {
          stream.pendingToolRequests = []
        }
      })

      // Schedule cleanup if stream is completed (not actively streaming)
      // Use short delay consistent with completeStream
      // Note: eventHandlerRegistries are NOT deleted here - managed by React component lifecycle
      setTimeout(() => {
        const stream = get().activeStreams.get(conversationId)
        if (stream && !stream.isStreaming && (!stream.pendingToolRequests || stream.pendingToolRequests.length === 0)) {
          set((draft) => {
            draft.activeStreams.delete(conversationId)
          })
          conversationIdRefs.delete(conversationId)
        }
      }, 100) // Short delay for React render cycle
    },

    clearMessages: (conversationId) => {
      set((draft) => {
        draft.conversationMessages.delete(conversationId)
      })
    },

    setQueued: (conversationId, queued) => {
      set((draft) => {
        const stream = draft.activeStreams.get(conversationId)
        if (stream) {
          stream.isQueued = queued
        }
      })
    },

    updateEventHandlerRegistry: (conversationId, eventHandlerRegistry) => {
      // Update registry in external map (not in Zustand state)
      if (eventHandlerRegistry) {
        eventHandlerRegistries.set(conversationId, eventHandlerRegistry)
      } else {
        eventHandlerRegistries.delete(conversationId)
      }
    },

    migrateStream: (oldConversationId, newConversationId) => {
      const stream = get().activeStreams.get(oldConversationId)
      const messages = get().conversationMessages.get(oldConversationId)
      const conversationIdRef = conversationIdRefs.get(oldConversationId)

      console.log('[StreamStore] migrateStream called:', {
        from: oldConversationId,
        to: newConversationId,
        streamFound: !!stream,
        messagesFound: !!messages,
        refFound: !!conversationIdRef,
        messageCount: messages?.messages.length ?? 0,
        isStreaming: stream?.isStreaming ?? false,
        allActiveStreams: Array.from(get().activeStreams.keys())
      })

      if (conversationIdRef) {
        // Update the mutable ref - now works because ref is in external map (not frozen by Immer)
        // This ensures the closure in processConversationStream sees the new ID immediately
        conversationIdRef.current = newConversationId
        console.log('[StreamStore] Updated conversationIdRef.current to:', newConversationId)

        // Migrate ref to new conversation ID in external map
        conversationIdRefs.delete(oldConversationId)
        conversationIdRefs.set(newConversationId, conversationIdRef)
      }

      set((draft) => {
        // Migrate streaming state
        const draftStream = draft.activeStreams.get(oldConversationId)
        if (draftStream) {
          draft.activeStreams.delete(oldConversationId)
          draft.activeStreams.set(newConversationId, draftStream)
        }

        // Migrate conversation messages
        const draftMessages = draft.conversationMessages.get(oldConversationId)
        if (draftMessages) {
          draft.conversationMessages.delete(oldConversationId)
          draft.conversationMessages.set(newConversationId, draftMessages)
        }
      })

      // Migrate event handler registry as well
      const registry = eventHandlerRegistries.get(oldConversationId)
      if (registry) {
        eventHandlerRegistries.delete(oldConversationId)
        eventHandlerRegistries.set(newConversationId, registry)
      }

      console.log('[StreamStore] Stream migrated successfully, allActiveStreams:', Array.from(get().activeStreams.keys()))
    },

    registerStreamLifecycleCallback: (cb) => {
      streamLifecycleCallbacks.add(cb)
      return () => { streamLifecycleCallbacks.delete(cb) }
    },

    reconnectStream: async (conversationId) => {
      // Don't reconnect if already streaming
      if (get().isConversationStreaming(conversationId)) return

      console.log('[StreamStore] reconnectStream:', { conversationId })

      const conversationIdRef = { current: conversationId }
      conversationIdRefs.set(conversationId, conversationIdRef)

      set((draft) => {
        draft.activeStreams.set(conversationId, {
          isStreaming: true,
          error: null,
          startedAt: Date.now(),
          pendingToolRequests: [],
          isQueued: false,
        })
      })

      // Notify immediately — reconnections are for already-running executions
      // where last_activity_at is already current
      notifyStreamLifecycle(conversationId, 'active')

      try {
        const stream = createWebSocketEventStream(conversationId)

        const { toolRequests } = await processConversationStream({
          stream,
          onEvent: (event) => {
            get().addEvent(conversationIdRef.current, event)
          },
          eventHandlerRegistry: eventHandlerRegistries.get(conversationIdRef.current),
        })

        if (toolRequests.length > 0) {
          set((draft) => {
            const streamState = draft.activeStreams.get(conversationIdRef.current)
            if (streamState) {
              streamState.pendingToolRequests = toolRequests
            }
          })
        }

        get().completeStream(conversationIdRef.current)
      } catch (error) {
        if (error instanceof Error) {
          console.error('Reconnect stream error:', error)
          get().setError(conversationIdRef.current, error)
        }
      }
    },
  }))
)
