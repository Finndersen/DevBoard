import { create } from 'zustand'
import { immer } from 'zustand/middleware/immer'
import type { ConversationEvent, ToolApprovalRequest, ToolCallRequest } from '../lib/api'
import { apiClient } from '../lib/api'
import { processConversationStream } from '../lib/streamProcessor'
import type { EventHandlerRegistry } from '../hooks/useConversationEventHandlers'
import { invokeStreamCompleteHandlers } from '../hooks/useConversationEventHandlers'

/**
 * State for an active conversation stream.
 */
export interface StreamState {
  /** Mutable reference to conversation ID - allows closures to see updates after migration */
  conversationIdRef: { current: number }
  messages: ConversationEvent[]
  isStreaming: boolean
  error: Error | null
  abortController: AbortController
  startedAt: number
  pendingToolRequests: ToolCallRequest[]
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
 * Store state containing all active conversation streams.
 */
interface ConversationStreamState {
  activeStreams: Map<number, StreamState>
}

/**
 * Store actions for managing conversation streams.
 */
interface ConversationStreamActions {
  /**
   * Start streaming conversation events.
   * The stream runs independently of component lifecycle.
   *
   * @param conversationId - The conversation to stream
   * @param stream - The event stream to process
   * @param eventHandlerRegistry - Optional registry for invoking event handlers
   * @param initialMessages - Optional initial messages to include (e.g., user message)
   */
  startStream: (
    conversationId: number,
    stream: AsyncGenerator<ConversationEvent>,
    eventHandlerRegistry?: EventHandlerRegistry,
    initialMessages?: ConversationEvent[]
  ) => Promise<void>

  /**
   * Stop (abort) an active stream.
   * This cancels the fetch request and stops processing events.
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
   *
   * @param conversationId - The conversation to continue
   * @param approvals - The tool approval decisions
   * @param eventHandlerRegistry - Optional registry for invoking event handlers
   * @param initialMessages - Optional initial messages to preserve (e.g., from history)
   */
  approveTools: (
    conversationId: number,
    approvals: Record<string, { approved: boolean; feedback?: string }>,
    eventHandlerRegistry?: EventHandlerRegistry,
    initialMessages?: ConversationEvent[]
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
 * // Create a stream and start processing
 * const stream = apiClient.streamConversationMessage(conversationId, { message: "Hello" })
 * await startStream(conversationId, stream, eventHandlerRegistry)
 * ```
 */
export const useConversationStreamStore = create<ConversationStreamStore>()(
  immer((set, get) => ({
    // Initial state
    activeStreams: new Map(),

    // Actions
    startStream: async (conversationId, stream, eventHandlerRegistry, initialMessages) => {
      // Create abort controller for this stream
      const abortController = new AbortController()

      // Create mutable ref for conversation ID - allows closures to see updates after migration
      const conversationIdRef = { current: conversationId }

      // Store event handler registry in separate map (not in Zustand state)
      if (eventHandlerRegistry) {
        eventHandlerRegistries.set(conversationId, eventHandlerRegistry)
      }

      // Initialize stream state with any initial messages (e.g., user message)
      set((draft) => {
        draft.activeStreams.set(conversationId, {
          conversationIdRef,
          messages: initialMessages ?? [],
          isStreaming: true,
          error: null,
          abortController,
          startedAt: Date.now(),
          pendingToolRequests: []
        })
      })

      console.log('[StreamStore] Stream started:', {
        conversationId,
        initialMessageCount: initialMessages?.length ?? 0
      })

      try {
        // Process the provided stream events and collect tool requests
        // Use conversationIdRef.current so closures see the current ID (may change during migration)
        const { toolRequests } = await processConversationStream({
          stream,
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
        // Handle stream errors (ignore abort errors)
        if (error instanceof Error && error.name !== 'AbortError') {
          console.error('Stream error:', error)
          get().setError(conversationIdRef.current, error)
        }
      }
    },

    stopStream: (conversationId) => {
      const stream = get().activeStreams.get(conversationId)
      if (stream) {
        // Abort the fetch request
        stream.abortController.abort()

        // Mark as not streaming
        set((draft) => {
          const streamState = draft.activeStreams.get(conversationId)
          if (streamState) {
            streamState.isStreaming = false
          }
        })
      }
    },

    completeStream: (conversationId) => {
      const stream = get().activeStreams.get(conversationId)
      console.log('[StreamStore] Stream completed:', {
        conversationId,
        messageCount: stream?.messages.length ?? 0
      })

      set((draft) => {
        const draftStream = draft.activeStreams.get(conversationId)
        if (draftStream) {
          draftStream.isStreaming = false
        }
      })

      // Invoke stream complete handlers if registry exists
      const registry = eventHandlerRegistries.get(conversationId)
      if (registry) {
        invokeStreamCompleteHandlers(registry).catch((error) => {
          console.error('Failed to invoke stream complete handlers:', error)
        })
      }

      // Schedule cleanup after a delay (keep messages available for a bit)
      // But don't clean up if there are pending tool requests - they need to persist
      setTimeout(() => {
        const stream = get().activeStreams.get(conversationId)
        // Only delete if no pending tool requests
        if (!stream?.pendingToolRequests || stream.pendingToolRequests.length === 0) {
          set((draft) => {
            draft.activeStreams.delete(conversationId)
          })
          // Also clean up event handler registry
          eventHandlerRegistries.delete(conversationId)
        }
      }, 60000) // Clean up after 1 minute
    },

    addEvent: (conversationId, event) => {
      console.log('[StreamStore] addEvent called:', {
        conversationId,
        eventType: event.event_type
      })

      set((draft) => {
        const stream = draft.activeStreams.get(conversationId)
        if (stream) {
          // Special handling for ToolCallRequest: remove duplicate ToolCall
          // PydanticAI emits ToolCall first, then ToolCallRequest for the same tool_call_id
          // We want to remove the initial ToolCall and keep only the approval workflow
          if (event.event_type === 'tool_call_request') {
            // Find and remove previous ToolCall with same tool_call_id
            const index = stream.messages.findIndex(
              (msg) =>
                msg.event_type === 'tool_call' &&
                msg.tool_call_id === event.tool_call_id
            )
            if (index !== -1) {
              stream.messages.splice(index, 1)
            }
            // Don't add ToolCallRequest to messages - it stays in approval UI only
            return
          }

          // Add all other events to messages normally
          stream.messages.push(event)
        }
      })
    },

    setError: (conversationId, error) => {
      set((draft) => {
        const stream = draft.activeStreams.get(conversationId)
        if (stream) {
          stream.error = error
          stream.isStreaming = false
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

    approveTools: async (conversationId, approvals, eventHandlerRegistry, initialMessages) => {
      const existingStream = get().activeStreams.get(conversationId)

      // Get existing messages to preserve conversation history
      const existingMessages = existingStream?.messages ?? initialMessages ?? []

      // Reuse existing ref if available, otherwise create new one
      const conversationIdRef = existingStream?.conversationIdRef ?? { current: conversationId }

      // Store event handler registry in separate map (not in Zustand state)
      if (eventHandlerRegistry) {
        eventHandlerRegistries.set(conversationId, eventHandlerRegistry)
      }

      // Create new abort controller for the approval stream
      const abortController = new AbortController()

      // Create or update stream state for the approval
      set((draft) => {
        draft.activeStreams.set(conversationId, {
          conversationIdRef,
          messages: existingMessages,
          isStreaming: true,
          error: null,
          abortController,
          startedAt: Date.now(),
          pendingToolRequests: []
        })
      })

      try {
        // Send approval to backend and start new stream with abort signal
        const approvalStream = apiClient.streamApproveConversationTools(
          conversationIdRef.current,
          { approvals } as ToolApprovalRequest,
          abortController.signal
        )

        // Process stream events and collect any new tool requests
        // Use conversationIdRef.current so closures see the current ID (may change during migration)
        const { toolRequests } = await processConversationStream({
          stream: approvalStream,
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
        if (error instanceof Error && error.name !== 'AbortError') {
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
      setTimeout(() => {
        const stream = get().activeStreams.get(conversationId)
        if (stream && !stream.isStreaming && (!stream.pendingToolRequests || stream.pendingToolRequests.length === 0)) {
          set((draft) => {
            draft.activeStreams.delete(conversationId)
          })
          // Also clean up event handler registry
          eventHandlerRegistries.delete(conversationId)
        }
      }, 5000) // Clean up after 5 seconds
    },

    clearMessages: (conversationId) => {
      set((draft) => {
        const stream = draft.activeStreams.get(conversationId)
        if (stream) {
          stream.messages = []
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

      console.log('[StreamStore] migrateStream called:', {
        from: oldConversationId,
        to: newConversationId,
        streamFound: !!stream,
        messageCount: stream?.messages.length ?? 0,
        isStreaming: stream?.isStreaming ?? false
      })

      if (stream) {
        // IMPORTANT: Update the mutable ref BEFORE the Immer draft operation
        // This ensures the closure in processConversationStream sees the new ID immediately
        // Updating inside Immer's set() doesn't work because Immer proxies the object
        stream.conversationIdRef.current = newConversationId
        console.log('[StreamStore] Updated conversationIdRef.current to:', newConversationId)

        set((draft) => {
          const draftStream = draft.activeStreams.get(oldConversationId)
          if (draftStream) {
            // Remove from old conversation ID
            draft.activeStreams.delete(oldConversationId)
            // Add to new conversation ID
            draft.activeStreams.set(newConversationId, draftStream)
          }
        })

        // Migrate event handler registry as well
        const registry = eventHandlerRegistries.get(oldConversationId)
        if (registry) {
          eventHandlerRegistries.delete(oldConversationId)
          eventHandlerRegistries.set(newConversationId, registry)
        }

        console.log('[StreamStore] Stream migrated successfully')
      } else {
        console.warn('[StreamStore] No stream found to migrate')
      }
    }
  }))
)
