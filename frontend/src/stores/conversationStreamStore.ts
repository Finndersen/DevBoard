import { create } from 'zustand'
import { immer } from 'zustand/middleware/immer'
import type { ConversationEvent, UserPrompt, ToolApprovalRequest, ToolCallRequest } from '../lib/api'
import { apiClient } from '../lib/api'
import { processConversationStream } from '../lib/streamProcessor'
import type { EventHandlerRegistry } from '../hooks/useConversationEventHandlers'

/**
 * State for an active conversation stream.
 */
export interface StreamState {
  conversationId: number
  messages: ConversationEvent[]
  isStreaming: boolean
  error: Error | null
  abortController: AbortController
  startedAt: number
  pendingToolRequests: ToolCallRequest[]
  eventHandlerRegistry?: EventHandlerRegistry
}

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
   * Start streaming a conversation message.
   * The stream runs independently of component lifecycle.
   *
   * @param conversationId - The conversation to stream
   * @param message - The user message to send
   * @param eventHandlerRegistry - Optional registry for invoking event handlers
   * @param initialMessages - Optional initial messages to include (e.g., user message)
   */
  startStream: (
    conversationId: number,
    message: string,
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
 * // Start streaming
 * await startStream(conversationId, "Hello", eventHandlerRegistry)
 * ```
 */
export const useConversationStreamStore = create<ConversationStreamStore>()(
  immer((set, get) => ({
    // Initial state
    activeStreams: new Map(),

    // Actions
    startStream: async (conversationId, message, eventHandlerRegistry, initialMessages) => {
      // Create abort controller for this stream
      const abortController = new AbortController()

      // Initialize stream state with any initial messages (e.g., user message)
      set((draft) => {
        draft.activeStreams.set(conversationId, {
          conversationId,
          messages: initialMessages ?? [],
          isStreaming: true,
          error: null,
          abortController,
          startedAt: Date.now(),
          pendingToolRequests: [],
          eventHandlerRegistry
        })
      })

      try {
        // Start streaming from API with abort signal
        const stream = apiClient.streamConversationMessage(
          conversationId,
          { message } as UserPrompt,
          abortController.signal
        )

        // Process stream events and collect tool requests
        // Use registry from store so it can be updated during streaming
        const { toolRequests } = await processConversationStream({
          stream,
          onEvent: (event) => {
            // Add event to store
            get().addEvent(conversationId, event)
          },
          eventHandlerRegistry: get().activeStreams.get(conversationId)?.eventHandlerRegistry
        })

        // Store tool requests if any
        if (toolRequests.length > 0) {
          set((draft) => {
            const streamState = draft.activeStreams.get(conversationId)
            if (streamState) {
              streamState.pendingToolRequests = toolRequests
            }
          })
        }

        // Stream completed successfully
        get().completeStream(conversationId)
      } catch (error) {
        // Handle stream errors (ignore abort errors)
        if (error instanceof Error && error.name !== 'AbortError') {
          console.error('Stream error:', error)
          get().setError(conversationId, error)
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
      set((draft) => {
        const stream = draft.activeStreams.get(conversationId)
        if (stream) {
          stream.isStreaming = false
        }
      })

      // Schedule cleanup after a delay (keep messages available for a bit)
      // But don't clean up if there are pending tool requests - they need to persist
      setTimeout(() => {
        const stream = get().activeStreams.get(conversationId)
        // Only delete if no pending tool requests
        if (!stream?.pendingToolRequests || stream.pendingToolRequests.length === 0) {
          set((draft) => {
            draft.activeStreams.delete(conversationId)
          })
        }
      }, 60000) // Clean up after 1 minute
    },

    addEvent: (conversationId, event) => {
      set((draft) => {
        const stream = draft.activeStreams.get(conversationId)
        if (stream) {
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

      // Create new abort controller for the approval stream
      const abortController = new AbortController()

      // Create or update stream state for the approval
      set((draft) => {
        draft.activeStreams.set(conversationId, {
          conversationId,
          messages: existingMessages,
          isStreaming: true,
          error: null,
          abortController,
          startedAt: Date.now(),
          pendingToolRequests: [],
          eventHandlerRegistry
        })
      })

      try {
        // Send approval to backend and start new stream with abort signal
        const approvalStream = apiClient.streamApproveConversationTools(
          conversationId,
          { approvals } as ToolApprovalRequest,
          abortController.signal
        )

        // Process stream events and collect any new tool requests
        // Use registry from store so it can be updated during streaming
        const { toolRequests } = await processConversationStream({
          stream: approvalStream,
          onEvent: (event) => {
            get().addEvent(conversationId, event)
          },
          eventHandlerRegistry: get().activeStreams.get(conversationId)?.eventHandlerRegistry
        })

        // Store new tool requests if any
        if (toolRequests.length > 0) {
          set((draft) => {
            const streamState = draft.activeStreams.get(conversationId)
            if (streamState) {
              streamState.pendingToolRequests = toolRequests
            }
          })
        }

        // Stream completed
        get().completeStream(conversationId)
      } catch (error) {
        if (error instanceof Error && error.name !== 'AbortError') {
          console.error('Approval stream error:', error)
          get().setError(conversationId, error)
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
      set((draft) => {
        const stream = draft.activeStreams.get(conversationId)
        if (stream) {
          stream.eventHandlerRegistry = eventHandlerRegistry
        }
      })
    }
  }))
)
