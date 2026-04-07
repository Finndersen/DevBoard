import { create } from 'zustand'
import { immer } from 'zustand/middleware/immer'
import type { ConversationEvent, ContextUsage, ExecutionCompleteEvent, ToolApprovalRequest, ToolCallRequest, ToolCall, ToolResult, SystemEvent } from '../lib/api'
import { apiClient } from '../lib/api'
import type { EventHandlerRegistry } from '../hooks/useConversationEventHandlers'
import { invokeStreamCompleteHandlers, invokeEventHandlers } from '../hooks/useConversationEventHandlers'
import { useNotificationStore } from './notificationStore'

export interface StreamState {
  isStreaming: boolean
  error: Error | null
  startedAt?: number
  lastEventAt?: number
  pendingToolRequests: ToolCallRequest[]
  isQueued: boolean
}

export interface ConversationMessagesState {
  messages: ConversationEvent[]
  historyLoaded: boolean
  contextUsage?: ContextUsage | null
}

// External mutable maps (outside Zustand because Immer freezes objects or they contain functions)
const eventHandlerRegistries = new Map<number, EventHandlerRegistry>()
const conversationIdRefs = new Map<number, { current: number }>()
const onFirstEventCallbacks = new Map<number, () => void>()
const onErrorCallbacks = new Map<number, (error: Error) => void>()
const conversationToolCallMaps = new Map<number, Map<string, string>>() // tool_call_id -> tool_name
const conversationCompletedToolCalls = new Map<number, Set<string>>()

export const reconnectingConversations = new Set<number>()

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

function initToolTracking(conversationId: number) {
  conversationToolCallMaps.set(conversationId, new Map())
  conversationCompletedToolCalls.set(conversationId, new Set())
}

function cleanupConversationMaps(conversationId: number) {
  onFirstEventCallbacks.delete(conversationId)
  onErrorCallbacks.delete(conversationId)
  conversationToolCallMaps.delete(conversationId)
  conversationCompletedToolCalls.delete(conversationId)
}

interface ConversationStreamState {
  activeStreams: Map<number, StreamState>
  conversationMessages: Map<number, ConversationMessagesState>
}

interface ConversationStreamActions {
  handleWebSocketEvent: (conversationId: number, rawEvent: ConversationEvent) => void
  startStream: (
    conversationId: number,
    message: string,
    onFirstEvent?: () => void | Promise<void>,
    onError?: (error: Error) => void,
  ) => Promise<void>
  stopStream: (conversationId: number) => void
  completeStream: (conversationId: number) => void
  addEvent: (conversationId: number, event: ConversationEvent) => void
  setMessages: (conversationId: number, messages: ConversationEvent[], contextUsage?: ContextUsage | null) => void
  setError: (conversationId: number, error: Error) => void
  getStreamState: (conversationId: number) => StreamState | undefined
  isConversationStreaming: (conversationId: number) => boolean
  getAllStreamingConversations: () => number[]
  approveTools: (
    conversationId: number,
    approvals: Record<string, { approved: boolean; feedback?: string }>
  ) => Promise<void>
  isHistoryLoaded: (conversationId: number) => boolean
  clearMessages: (conversationId: number) => void
  clearPendingToolRequests: (conversationId: number) => void
  setQueued: (conversationId: number, queued: boolean) => void
  updateEventHandlerRegistry: (conversationId: number, eventHandlerRegistry: EventHandlerRegistry | undefined) => void
  migrateStream: (oldConversationId: number, newConversationId: number) => void
  reconnectStream: (conversationId: number) => Promise<void>
  registerStreamLifecycleCallback: (cb: StreamLifecycleCallback) => () => void
}

type ConversationStreamStore = ConversationStreamState & ConversationStreamActions

export const useConversationStreamStore = create<ConversationStreamStore>()(
  immer((set, get) => ({
    activeStreams: new Map(),
    conversationMessages: new Map(),

    handleWebSocketEvent: (conversationId, rawEvent) => {
      // execution_complete finalises the stream regardless of whether it is currently marked active
      if (rawEvent.event_type === 'execution_complete') {
        const completeEvent = rawEvent as unknown as ExecutionCompleteEvent
        if (completeEvent.status === 'failed') {
          const errorEvent: SystemEvent = {
            event_type: 'system',
            type: 'stream_error',
            data: {
              error_code: 'EXECUTION_FAILED',
              message: completeEvent.error || 'Agent execution failed',
            },
            timestamp: new Date().toISOString(),
          }
          get().addEvent(conversationId, errorEvent)
          get().setError(conversationId, new Error(completeEvent.error || 'Agent execution failed'))
        } else {
          // Synthesize error results for tool calls that never received a result
          const toolCallMap = conversationToolCallMaps.get(conversationId)
          const completedToolCalls = conversationCompletedToolCalls.get(conversationId)
          if (toolCallMap && completedToolCalls) {
            for (const [toolCallId] of toolCallMap) {
              if (!completedToolCalls.has(toolCallId)) {
                const synthesized: ToolResult = {
                  event_type: 'tool_result',
                  tool_call_id: toolCallId,
                  result_content: 'Tool execution was interrupted.',
                  is_error: true,
                  timestamp: new Date().toISOString(),
                }
                get().addEvent(conversationId, synthesized)
              }
            }
          }
          // Update contextUsage if provided in the event
          if (completeEvent.usage) {
            set((draft) => {
              const convMessages = draft.conversationMessages.get(conversationId)
              if (convMessages) {
                convMessages.contextUsage = completeEvent.usage
              }
            })
          }
          get().completeStream(conversationId)
        }
        return
      }

      // Auto-initialise stream state when an event arrives before bootstrap completes
      // (handles the race condition where the WS event arrives before startStream sets state)
      const stream = get().activeStreams.get(conversationId)
      if (!stream) {
        set((draft) => {
          draft.activeStreams.set(conversationId, {
            isStreaming: true,
            error: null,
            startedAt: Date.now(),
            lastEventAt: Date.now(),
            pendingToolRequests: [],
            isQueued: false,
          })
        })
        initToolTracking(conversationId)
      }

      if (!get().isConversationStreaming(conversationId)) return

      // Fire and remove the first-event callback
      const firstEventCb = onFirstEventCallbacks.get(conversationId)
      if (firstEventCb) {
        onFirstEventCallbacks.delete(conversationId)
        try {
          firstEventCb()
        } catch (err) {
          console.error('[StreamStore] onFirstEvent callback error:', err)
        }
      }

      set((draft) => {
        const s = draft.activeStreams.get(conversationId)
        if (s) s.lastEventAt = Date.now()
      })

      const event = rawEvent

      // Track tool calls so orphaned ones can be synthesised on execution_complete
      if (event.event_type === 'tool_call') {
        const toolCallMap = conversationToolCallMaps.get(conversationId)
        if (toolCallMap) {
          toolCallMap.set((event as ToolCall).tool_call_id, (event as ToolCall).tool_name)
        }
      }
      if (event.event_type === 'tool_result') {
        const completed = conversationCompletedToolCalls.get(conversationId)
        if (completed) {
          completed.add((event as ToolResult).tool_call_id)
        }
      }

      if (event.event_type === 'tool_call_request') {
        set((draft) => {
          const s = draft.activeStreams.get(conversationId)
          if (s) {
            s.pendingToolRequests = [...s.pendingToolRequests, event as ToolCallRequest]
          }
        })
        get().addEvent(conversationId, event)
        return
      }

      if (event.event_type === 'system' && (event as SystemEvent).type === 'stream_error') {
        const errorMessage = ((event as SystemEvent).data?.message as string) || 'An error occurred'
        get().addEvent(conversationId, event)
        get().setError(conversationId, new Error(errorMessage))
        return
      }

      if (event.event_type === 'tool_call' || event.event_type === 'tool_result' || event.event_type === 'system') {
        const registry = eventHandlerRegistries.get(conversationId)
        if (registry) {
          const toolCallMap = conversationToolCallMaps.get(conversationId) ?? new Map()
          invokeEventHandlers(event, registry, toolCallMap).catch(err => {
            console.error('[StreamStore] event handler error:', err)
          })
        }
      }

      get().addEvent(conversationId, event)
    },

    startStream: async (conversationId, message, onFirstEvent, onError) => {
      const conversationIdRef = { current: conversationId }
      conversationIdRefs.set(conversationId, conversationIdRef)

      const existingStream = get().activeStreams.get(conversationId)
      const existingMessages = get().conversationMessages.get(conversationId)
      console.log('[StreamStore] startStream called:', {
        conversationId,
        hasExistingStream: !!existingStream,
        existingStreamIsStreaming: existingStream?.isStreaming,
        existingMessageCount: existingMessages?.messages?.length ?? 0,
        allActiveStreams: Array.from(get().activeStreams.keys())
      })

      const existingIsQueued = get().activeStreams.get(conversationId)?.isQueued ?? false
      set((draft) => {
        draft.activeStreams.set(conversationId, {
          isStreaming: true,
          error: null,
          startedAt: Date.now(),
          lastEventAt: Date.now(),
          pendingToolRequests: [],
          isQueued: existingIsQueued,
        })
      })

      initToolTracking(conversationId)

      // Wrap first-event callback to also fire the lifecycle notification
      const wrappedFirstEvent = () => {
        if (onFirstEvent) {
          Promise.resolve(onFirstEvent()).catch(err => {
            console.error('[StreamStore] onFirstEvent error:', err)
          })
        }
        notifyStreamLifecycle(conversationIdRef.current, 'active')
      }
      onFirstEventCallbacks.set(conversationId, wrappedFirstEvent)

      if (onError) {
        onErrorCallbacks.set(conversationId, onError)
      }

      console.log('[StreamStore] Stream started:', { conversationId })

      try {
        await apiClient.sendConversationMessage(conversationIdRef.current, { message })
      } catch (error) {
        // POST failed — events will never arrive, so clean up immediately
        onFirstEventCallbacks.delete(conversationId)
        onErrorCallbacks.delete(conversationId)
        cleanupConversationMaps(conversationId)
        set((draft) => {
          draft.activeStreams.delete(conversationId)
        })
        conversationIdRefs.delete(conversationId)
        throw error
      }
      // Return immediately — events arrive via handleWebSocketEvent
    },

    stopStream: (conversationId) => {
      const stream = get().activeStreams.get(conversationId)
      if (stream?.isStreaming) {
        set((draft) => {
          const streamState = draft.activeStreams.get(conversationId)
          if (streamState) {
            streamState.isStreaming = false
            streamState.isQueued = false
          }
        })

        // Revert the optimistic update if the interrupt request fails
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

      const registry = eventHandlerRegistries.get(conversationId)
      if (registry) {
        invokeStreamCompleteHandlers(registry).catch((error) => {
          console.error('Failed to invoke stream complete handlers:', error)
        })
      }

      conversationToolCallMaps.delete(conversationId)
      conversationCompletedToolCalls.delete(conversationId)

      if (!stream?.pendingToolRequests || stream.pendingToolRequests.length === 0) {
        setTimeout(() => {
          const currentStream = get().activeStreams.get(conversationId)
          if (currentStream && !currentStream.isStreaming) {
            set((draft) => {
              draft.activeStreams.delete(conversationId)
            })
            conversationIdRefs.delete(conversationId)
          }
        }, 100)
      }
    },

    addEvent: (conversationId, event) => {
      const messagesBefore = get().conversationMessages.get(conversationId)
      console.log('[StreamStore] addEvent:', {
        conversationId,
        eventType: event.event_type,
        currentMessageCount: messagesBefore?.messages?.length ?? 0,
        ...(event.event_type === 'tool_call' && { toolName: (event as ToolCall).tool_name }),
        ...(event.event_type === 'system' && { systemType: (event as SystemEvent).type })
      })

      set((draft) => {
        let convMessages = draft.conversationMessages.get(conversationId)
        if (!convMessages) {
          convMessages = { messages: [], historyLoaded: false }
          draft.conversationMessages.set(conversationId, convMessages)
        }

        // PydanticAI emits a ToolCall before the ToolCallRequest for the same tool_call_id.
        // Remove the initial ToolCall so only the approval-workflow representation is kept.
        if (event.event_type === 'tool_call_request') {
          const index = convMessages.messages.findIndex(
            (msg) =>
              msg.event_type === 'tool_call' &&
              msg.tool_call_id === event.tool_call_id
          )
          if (index !== -1) {
            convMessages.messages.splice(index, 1)
          }
          return
        }

        // For thinking events, always calculate duration_seconds from previous event timestamp
        if (event.event_type === 'thinking') {
          const previousEvent = convMessages.messages.length > 0
            ? convMessages.messages[convMessages.messages.length - 1]
            : null
          if (previousEvent) {
            (event as { duration_seconds: number | null }).duration_seconds =
              (new Date(event.timestamp).getTime() - new Date(previousEvent.timestamp).getTime()) / 1000
          } else {
            (event as { duration_seconds: number | null }).duration_seconds = null
          }
        }


        convMessages.messages.push(event)
      })
    },

    setMessages: (conversationId, messages, contextUsage) => {
      set((draft) => {
        draft.conversationMessages.set(conversationId, { messages, historyLoaded: true, contextUsage })
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

      // If the first event never arrived the error callback is still registered
      const errorCb = onErrorCallbacks.get(conversationId)
      if (errorCb) {
        onErrorCallbacks.delete(conversationId)
        onFirstEventCallbacks.delete(conversationId)
        try {
          errorCb(error)
        } catch (err) {
          console.error('[StreamStore] onError callback error:', err)
        }
      }

      // Notify lifecycle so queued-message auto-send and other subscribers can react
      notifyStreamLifecycle(conversationId, 'complete')

      cleanupConversationMaps(conversationId)
    },

    getStreamState: (conversationId) => {
      return get().activeStreams.get(conversationId)
    },

    isConversationStreaming: (conversationId) => {
      const stream = get().activeStreams.get(conversationId)
      return stream?.isStreaming ?? false
    },

    getAllStreamingConversations: () => {
      const streamingConversations: number[] = []
      get().activeStreams.forEach((stream, conversationId) => {
        if (stream.isStreaming) {
          streamingConversations.push(conversationId)
        }
      })
      return streamingConversations
    },

    approveTools: async (conversationId, approvals) => {
      const existingStream = get().activeStreams.get(conversationId)

      let conversationIdRef = conversationIdRefs.get(conversationId)
      if (!conversationIdRef) {
        conversationIdRef = { current: conversationId }
        conversationIdRefs.set(conversationId, conversationIdRef)
      }

      const existingIsQueued = existingStream?.isQueued ?? false
      set((draft) => {
        draft.activeStreams.set(conversationId, {
          isStreaming: true,
          error: null,
          startedAt: Date.now(),
          lastEventAt: Date.now(),
          pendingToolRequests: [],
          isQueued: existingIsQueued,
        })
      })

      initToolTracking(conversationId)

      onFirstEventCallbacks.set(conversationId, () => {
        notifyStreamLifecycle(conversationIdRef!.current, 'active')
      })

      try {
        await apiClient.approveConversationTools(
          conversationIdRef.current,
          { approvals } as ToolApprovalRequest,
        )
      } catch (error) {
        onFirstEventCallbacks.delete(conversationId)
        cleanupConversationMaps(conversationId)
        if (error instanceof Error) {
          console.error('Approval POST error:', error)
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

      setTimeout(() => {
        const stream = get().activeStreams.get(conversationId)
        if (stream && !stream.isStreaming && (!stream.pendingToolRequests || stream.pendingToolRequests.length === 0)) {
          set((draft) => {
            draft.activeStreams.delete(conversationId)
          })
          conversationIdRefs.delete(conversationId)
        }
      }, 100)
    },

    isHistoryLoaded: (conversationId) => {
      return get().conversationMessages.get(conversationId)?.historyLoaded ?? false
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
        messageCount: messages?.messages.length ?? 0,
        isStreaming: stream?.isStreaming ?? false,
        allActiveStreams: Array.from(get().activeStreams.keys())
      })

      if (conversationIdRef) {
        conversationIdRef.current = newConversationId
        conversationIdRefs.delete(oldConversationId)
        conversationIdRefs.set(newConversationId, conversationIdRef)
      }

      set((draft) => {
        const draftStream = draft.activeStreams.get(oldConversationId)
        if (draftStream) {
          draft.activeStreams.delete(oldConversationId)
          draft.activeStreams.set(newConversationId, draftStream)
        }

        const draftMessages = draft.conversationMessages.get(oldConversationId)
        if (draftMessages) {
          draft.conversationMessages.delete(oldConversationId)
          draft.conversationMessages.set(newConversationId, draftMessages)
        }
      })

      const registry = eventHandlerRegistries.get(oldConversationId)
      if (registry) {
        eventHandlerRegistries.delete(oldConversationId)
        eventHandlerRegistries.set(newConversationId, registry)
      }

      const firstEventCb = onFirstEventCallbacks.get(oldConversationId)
      if (firstEventCb) {
        onFirstEventCallbacks.delete(oldConversationId)
        onFirstEventCallbacks.set(newConversationId, firstEventCb)
      }

      const errorCb = onErrorCallbacks.get(oldConversationId)
      if (errorCb) {
        onErrorCallbacks.delete(oldConversationId)
        onErrorCallbacks.set(newConversationId, errorCb)
      }

      const toolCallMap = conversationToolCallMaps.get(oldConversationId)
      if (toolCallMap) {
        conversationToolCallMaps.delete(oldConversationId)
        conversationToolCallMaps.set(newConversationId, toolCallMap)
      }

      const completedCalls = conversationCompletedToolCalls.get(oldConversationId)
      if (completedCalls) {
        conversationCompletedToolCalls.delete(oldConversationId)
        conversationCompletedToolCalls.set(newConversationId, completedCalls)
      }

      console.log('[StreamStore] Stream migrated successfully, allActiveStreams:', Array.from(get().activeStreams.keys()))
    },

    reconnectStream: async (conversationId) => {
      if (get().isConversationStreaming(conversationId)) return
      if (reconnectingConversations.has(conversationId)) return
      reconnectingConversations.add(conversationId)

      console.log('[StreamStore] reconnectStream:', { conversationId })

      const conversationIdRef = { current: conversationId }
      conversationIdRefs.set(conversationId, conversationIdRef)

      const existingIsQueued = get().activeStreams.get(conversationId)?.isQueued ?? false
      set((draft) => {
        draft.activeStreams.set(conversationId, {
          isStreaming: true,
          error: null,
          startedAt: Date.now(),
          lastEventAt: Date.now(),
          pendingToolRequests: [],
          isQueued: existingIsQueued,
        })
      })

      initToolTracking(conversationId)

      // Notify immediately — reconnections are for already-running executions
      notifyStreamLifecycle(conversationId, 'active')

      // WS is always open; events will route automatically via handleWebSocketEvent
      reconnectingConversations.delete(conversationId)
    },

    registerStreamLifecycleCallback: (cb) => {
      streamLifecycleCallbacks.add(cb)
      return () => { streamLifecycleCallbacks.delete(cb) }
    },
  }))
)
