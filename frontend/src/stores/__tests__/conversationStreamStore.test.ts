// @vitest-environment node
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { enableMapSet } from 'immer'
import { useConversationStreamStore } from '../conversationStreamStore'
import type { ConversationEvent } from '../../lib/api'
import { apiClient } from '../../lib/api'

vi.mock('../../lib/api', () => ({
  apiClient: {
    sendConversationMessage: vi.fn().mockResolvedValue(undefined),
    interruptConversation: vi.fn().mockResolvedValue(undefined),
  },
}))

// Enable Immer MapSet plugin for handling Map/Set in the store
enableMapSet()

/** Helper to read messages from the conversation messages map */
function getMessages(conversationId: number): ConversationEvent[] {
  return useConversationStreamStore.getState().conversationMessages.get(conversationId)?.messages ?? []
}

describe('conversationStreamStore - addEvent deduplication', () => {
  beforeEach(() => {
    useConversationStreamStore.setState({ activeStreams: new Map(), conversationMessages: new Map() })
  })

  it('should remove duplicate ToolCall when ToolCallRequest arrives', () => {
    const conversationId = 1

    const store = useConversationStreamStore.getState()

    // Add initial ToolCall event
    const toolCall: ConversationEvent = {
      event_type: 'tool_call',
      tool_call_id: 'call-123',
      tool_name: 'test_tool',
      tool_args: { param: 'value' },
      timestamp: '2024-01-01T00:00:00Z'
    }
    store.addEvent(conversationId, toolCall)

    // Verify ToolCall was added
    expect(getMessages(conversationId)).toHaveLength(1)
    expect(getMessages(conversationId)[0]).toEqual(toolCall)

    // Add ToolCallRequest with same tool_call_id
    const toolCallRequest: ConversationEvent = {
      event_type: 'tool_call_request',
      tool_call_id: 'call-123',
      tool_name: 'test_tool',
      tool_args: { param: 'value' },
      timestamp: '2024-01-01T00:00:01Z'
    }
    store.addEvent(conversationId, toolCallRequest)

    // Verify: ToolCall was removed, ToolCallRequest was not added
    expect(getMessages(conversationId)).toHaveLength(0)
  })

  it('should not add ToolCallRequest to messages', () => {
    const conversationId = 2

    const store = useConversationStreamStore.getState()

    // Add ToolCallRequest without prior ToolCall
    const toolCallRequest: ConversationEvent = {
      event_type: 'tool_call_request',
      tool_call_id: 'call-456',
      tool_name: 'another_tool',
      tool_args: null,
      timestamp: '2024-01-01T00:00:00Z'
    }
    store.addEvent(conversationId, toolCallRequest)

    // Verify: ToolCallRequest was not added to messages
    expect(getMessages(conversationId)).toHaveLength(0)
  })

  it('should preserve other messages when removing duplicate ToolCall', () => {
    const conversationId = 3

    const store = useConversationStreamStore.getState()

    // Add various events
    const message1: ConversationEvent = {
      event_type: 'message',
      role: 'user',
      text_content: 'Hello',
      timestamp: '2024-01-01T00:00:00Z'
    }
    store.addEvent(conversationId, message1)

    const toolCall: ConversationEvent = {
      event_type: 'tool_call',
      tool_call_id: 'call-789',
      tool_name: 'test_tool',
      tool_args: null,
      timestamp: '2024-01-01T00:00:01Z'
    }
    store.addEvent(conversationId, toolCall)

    const message2: ConversationEvent = {
      event_type: 'message',
      role: 'agent',
      text_content: 'Response',
      timestamp: '2024-01-01T00:00:02Z'
    }
    store.addEvent(conversationId, message2)

    // Verify initial state: 3 messages
    expect(getMessages(conversationId)).toHaveLength(3)

    // Add ToolCallRequest to trigger deduplication
    const toolCallRequest: ConversationEvent = {
      event_type: 'tool_call_request',
      tool_call_id: 'call-789',
      tool_name: 'test_tool',
      tool_args: null,
      timestamp: '2024-01-01T00:00:03Z'
    }
    store.addEvent(conversationId, toolCallRequest)

    // Verify: ToolCall removed, other messages preserved
    const messages = getMessages(conversationId)
    expect(messages).toHaveLength(2)
    expect(messages[0]).toEqual(message1)
    expect(messages[1]).toEqual(message2)
  })

  it('should add normal events without deduplication', () => {
    const conversationId = 4

    const store = useConversationStreamStore.getState()

    // Add various normal events
    const events: ConversationEvent[] = [
      { event_type: 'message', role: 'user', text_content: 'Hello', timestamp: '2024-01-01T00:00:00Z' },
      { event_type: 'tool_call', tool_call_id: 'tc1', tool_name: 'tool1', tool_args: null, timestamp: '2024-01-01T00:00:01Z' },
      { event_type: 'tool_result', tool_call_id: 'tc1', tool_name: 'tool1', result: 'success', timestamp: '2024-01-01T00:00:02Z' },
      { event_type: 'message', role: 'agent', text_content: 'Done', timestamp: '2024-01-01T00:00:03Z' }
    ]

    events.forEach(event => store.addEvent(conversationId, event))

    // Verify all events were added normally
    const messages = getMessages(conversationId)
    expect(messages).toHaveLength(4)
    expect(messages).toEqual(events)
  })

  it('should handle multiple ToolCalls with different IDs', () => {
    const conversationId = 5

    const store = useConversationStreamStore.getState()

    // Add two ToolCalls with different IDs
    const toolCall1: ConversationEvent = {
      event_type: 'tool_call',
      tool_call_id: 'call-1',
      tool_name: 'tool1',
      tool_args: null,
      timestamp: '2024-01-01T00:00:00Z'
    }
    store.addEvent(conversationId, toolCall1)

    const toolCall2: ConversationEvent = {
      event_type: 'tool_call',
      tool_call_id: 'call-2',
      tool_name: 'tool2',
      tool_args: null,
      timestamp: '2024-01-01T00:00:01Z'
    }
    store.addEvent(conversationId, toolCall2)

    // Add ToolCallRequest for call-1
    const toolCallRequest1: ConversationEvent = {
      event_type: 'tool_call_request',
      tool_call_id: 'call-1',
      tool_name: 'tool1',
      tool_args: null,
      timestamp: '2024-01-01T00:00:02Z'
    }
    store.addEvent(conversationId, toolCallRequest1)

    // Verify: Only toolCall1 was removed, toolCall2 remains
    const messages = getMessages(conversationId)
    expect(messages).toHaveLength(1)
    expect(messages[0]).toEqual(toolCall2)
  })
})

describe('conversationStreamStore - thinking event duration calculation', () => {
  beforeEach(() => {
    useConversationStreamStore.setState({ activeStreams: new Map(), conversationMessages: new Map() })
  })

  it('calculates duration_seconds from previous event timestamp when backend sends null', () => {
    const conversationId = 10
    const store = useConversationStreamStore.getState()

    const previousEvent: ConversationEvent = {
      event_type: 'message',
      role: 'agent',
      text_content: 'Hello',
      timestamp: '2024-01-01T10:00:00.000Z',
    }
    store.addEvent(conversationId, previousEvent)

    const thinkingEvent: ConversationEvent = {
      event_type: 'thinking',
      duration_seconds: null,
      thinking_text: null,
      timestamp: '2024-01-01T10:00:05.000Z',
    }
    store.addEvent(conversationId, thinkingEvent)

    const messages = getMessages(conversationId)
    expect(messages).toHaveLength(2)
    const stored = messages[1] as { duration_seconds: number | null }
    expect(stored.duration_seconds).toBeCloseTo(5.0)
  })

  it('overwrites backend-provided duration_seconds with frontend-calculated value', () => {
    const conversationId = 11
    const store = useConversationStreamStore.getState()

    const previousEvent: ConversationEvent = {
      event_type: 'message',
      role: 'agent',
      text_content: 'Hello',
      timestamp: '2024-01-01T10:00:00.000Z',
    }
    store.addEvent(conversationId, previousEvent)

    const thinkingEvent: ConversationEvent = {
      event_type: 'thinking',
      duration_seconds: 99.9,
      thinking_text: null,
      timestamp: '2024-01-01T10:00:03.500Z',
    }
    store.addEvent(conversationId, thinkingEvent)

    const messages = getMessages(conversationId)
    const stored = messages[1] as { duration_seconds: number | null }
    expect(stored.duration_seconds).toBeCloseTo(3.5)
  })

  it('leaves duration_seconds as null when there is no previous event', () => {
    const conversationId = 12
    const store = useConversationStreamStore.getState()

    const thinkingEvent: ConversationEvent = {
      event_type: 'thinking',
      duration_seconds: null,
      thinking_text: null,
      timestamp: '2024-01-01T10:00:00.000Z',
    }
    store.addEvent(conversationId, thinkingEvent)

    const messages = getMessages(conversationId)
    const stored = messages[0] as { duration_seconds: number | null }
    expect(stored.duration_seconds).toBeNull()
  })
})

describe('conversationStreamStore - handleWebSocketEvent', () => {
  const conversationId = 100


  beforeEach(() => {
    useConversationStreamStore.setState({ activeStreams: new Map(), conversationMessages: new Map() })
    // Set up an active stream so events are processed
    useConversationStreamStore.setState((state) => {
      state.activeStreams.set(conversationId, {
        isStreaming: true,
        error: null,
        startedAt: Date.now(),
        pendingToolRequests: [],
        isQueued: false,
      })
    })
  })

  it('routes normal events to addEvent', () => {
    const store = useConversationStreamStore.getState()
    const event: ConversationEvent = {
      event_type: 'message',
      role: 'agent',
      text_content: 'Hello',
      timestamp: '2024-01-01T00:00:00Z',
    }

    store.handleWebSocketEvent(conversationId, event)

    expect(getMessages(conversationId)).toEqual([event])
  })

  it('handles execution_complete with status "failed" → setError', () => {
    const store = useConversationStreamStore.getState()

    store.handleWebSocketEvent(conversationId, {
      event_type: 'execution_complete',
      status: 'failed',
      error: 'Something went wrong',
    } as unknown as ConversationEvent)

    const streamState = store.getStreamState(conversationId)
    expect(streamState?.isStreaming).toBe(false)
    expect(streamState?.error).toBeInstanceOf(Error)
    expect(streamState?.error?.message).toBe('Something went wrong')
  })

  it('handles execution_complete with status "completed" → completeStream', () => {
    const store = useConversationStreamStore.getState()

    store.handleWebSocketEvent(conversationId, {
      event_type: 'execution_complete',
      status: 'completed',
    } as unknown as ConversationEvent)

    const streamState = store.getStreamState(conversationId)
    expect(streamState?.isStreaming).toBe(false)
    expect(streamState?.error).toBeNull()
  })

  it('handles stream_error system event → setError', () => {
    const store = useConversationStreamStore.getState()

    store.handleWebSocketEvent(conversationId, {
      event_type: 'system',
      type: 'stream_error',
      data: { message: 'Stream broke' },
      timestamp: '2024-01-01T00:00:00Z',
    } as unknown as ConversationEvent)

    const streamState = store.getStreamState(conversationId)
    expect(streamState?.isStreaming).toBe(false)
    expect(streamState?.error).toBeInstanceOf(Error)
    expect(streamState?.error?.message).toBe('Stream broke')
  })

  it('handles tool_call_request → adds to pendingToolRequests', () => {
    const store = useConversationStreamStore.getState()
    const toolCallRequest: ConversationEvent = {
      event_type: 'tool_call_request',
      tool_call_id: 'req-1',
      tool_name: 'my_tool',
      tool_args: { key: 'val' },
      timestamp: '2024-01-01T00:00:00Z',
    }

    store.handleWebSocketEvent(conversationId, toolCallRequest)

    const streamState = store.getStreamState(conversationId)
    expect(streamState?.pendingToolRequests).toHaveLength(1)
    expect(streamState?.pendingToolRequests[0]).toMatchObject({
      event_type: 'tool_call_request',
      tool_call_id: 'req-1',
      tool_name: 'my_tool',
    })
  })

  it('invokes onFirstEvent callback on the first event', () => {
    const store = useConversationStreamStore.getState()
    const onFirstEvent = vi.fn()

    // Register the callback via startStream's side-effect path by directly
    // using the internal callback map exposed through startStream
    // We call startStream to register the callback then intercept
    vi.mocked(apiClient.sendConversationMessage).mockResolvedValue(undefined)

    // Use startStream to register the onFirstEvent callback
    store.startStream(conversationId, 'test', onFirstEvent, undefined)

    const event: ConversationEvent = {
      event_type: 'message',
      role: 'agent',
      text_content: 'First!',
      timestamp: '2024-01-01T00:00:00Z',
    }

    store.handleWebSocketEvent(conversationId, event)

    expect(onFirstEvent).toHaveBeenCalledTimes(1)

    // Second event should NOT call onFirstEvent again
    store.handleWebSocketEvent(conversationId, { ...event, text_content: 'Second!' })
    expect(onFirstEvent).toHaveBeenCalledTimes(1)
  })

  it('auto-initialises stream state when event arrives before startStream sets state', () => {
    // Remove the active stream to simulate the race condition
    useConversationStreamStore.setState((state) => {
      state.activeStreams.delete(conversationId)
    })

    const store = useConversationStreamStore.getState()
    const event: ConversationEvent = {
      event_type: 'message',
      role: 'agent',
      text_content: 'Arrived early',
      timestamp: '2024-01-01T00:00:00Z',
    }

    store.handleWebSocketEvent(conversationId, event)

    expect(store.isConversationStreaming(conversationId)).toBe(true)
    expect(getMessages(conversationId)).toEqual([event])
  })
})

describe('conversationStreamStore - startStream', () => {
  beforeEach(() => {
    useConversationStreamStore.setState({ activeStreams: new Map(), conversationMessages: new Map() })
    vi.clearAllMocks()
  })

  it('sends POST via apiClient and sets isStreaming: true', async () => {
    vi.mocked(apiClient.sendConversationMessage).mockResolvedValue(undefined)
    const conversationId = 300
    const store = useConversationStreamStore.getState()

    await store.startStream(conversationId, 'Hello world')

    expect(apiClient.sendConversationMessage).toHaveBeenCalledWith(conversationId, { message: 'Hello world' })
    // Stream state is set before the POST
    // After POST returns, state remains (events arrive via WS)
    expect(store.isConversationStreaming(conversationId)).toBe(true)
  })

  it('cleans up stream state if POST fails', async () => {
    const postError = new Error('Network error')
    vi.mocked(apiClient.sendConversationMessage).mockRejectedValue(postError)
    const conversationId = 301
    const store = useConversationStreamStore.getState()

    await expect(store.startStream(conversationId, 'Hello')).rejects.toThrow('Network error')

    expect(store.activeStreams.get(conversationId)).toBeUndefined()
  })
})

describe('conversationStreamStore - reconnectStream', () => {
  beforeEach(() => {
    useConversationStreamStore.setState({ activeStreams: new Map(), conversationMessages: new Map() })
  })

  it('sets isStreaming: true without making a WS connection', async () => {
    const conversationId = 400
    const store = useConversationStreamStore.getState()

    await store.reconnectStream(conversationId)

    expect(store.isConversationStreaming(conversationId)).toBe(true)
  })

  it('is a no-op when the conversation is already streaming', async () => {
    const conversationId = 401
    useConversationStreamStore.setState((state) => {
      state.activeStreams.set(conversationId, {
        isStreaming: true,
        error: null,
        startedAt: Date.now(),
        pendingToolRequests: [],
        isQueued: false,
      })
    })

    const store = useConversationStreamStore.getState()
    const addEventSpy = vi.spyOn(store, 'addEvent')

    await store.reconnectStream(conversationId)

    expect(addEventSpy).not.toHaveBeenCalled()
    addEventSpy.mockRestore()
  })
})
