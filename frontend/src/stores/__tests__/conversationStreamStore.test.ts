import { describe, it, expect, beforeEach } from 'vitest'
import { enableMapSet } from 'immer'
import { useConversationStreamStore } from '../conversationStreamStore'
import type { ConversationEvent } from '../../lib/api'

// Enable Immer MapSet plugin for handling Map/Set in the store
enableMapSet()

describe('conversationStreamStore - addEvent deduplication', () => {
  it('should remove duplicate ToolCall when ToolCallRequest arrives', () => {
    const conversationId = Date.now() // Use unique ID for each test

    // Initialize stream state using Zustand's setState
    useConversationStreamStore.setState((state) => {
      state.activeStreams.set(conversationId, {
        conversationId,
        messages: [],
        isStreaming: true,
        error: null,
        abortController: new AbortController(),
        startedAt: Date.now(),
        pendingToolRequests: []
      })
    })

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
    let streamState = store.getStreamState(conversationId)
    expect(streamState?.messages).toHaveLength(1)
    expect(streamState?.messages[0]).toEqual(toolCall)

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
    streamState = store.getStreamState(conversationId)
    expect(streamState?.messages).toHaveLength(0)
  })

  it('should not add ToolCallRequest to messages', () => {
    const conversationId = Date.now() + 1 // Use unique ID for each test

    // Initialize stream state using Zustand's setState
    useConversationStreamStore.setState((state) => {
      state.activeStreams.set(conversationId, {
        conversationId,
        messages: [],
        isStreaming: true,
        error: null,
        abortController: new AbortController(),
        startedAt: Date.now(),
        pendingToolRequests: []
      })
    })

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
    const streamState = store.getStreamState(conversationId)
    expect(streamState?.messages).toHaveLength(0)
  })

  it('should preserve other messages when removing duplicate ToolCall', () => {
    const conversationId = Date.now() + 2 // Use unique ID for each test

    // Initialize stream state using Zustand's setState
    useConversationStreamStore.setState((state) => {
      state.activeStreams.set(conversationId, {
        conversationId,
        messages: [],
        isStreaming: true,
        error: null,
        abortController: new AbortController(),
        startedAt: Date.now(),
        pendingToolRequests: []
      })
    })

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
    let streamState = store.getStreamState(conversationId)
    expect(streamState?.messages).toHaveLength(3)

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
    streamState = store.getStreamState(conversationId)
    expect(streamState?.messages).toHaveLength(2)
    expect(streamState?.messages[0]).toEqual(message1)
    expect(streamState?.messages[1]).toEqual(message2)
  })

  it('should add normal events without deduplication', () => {
    const conversationId = Date.now() + 3 // Use unique ID for each test

    // Initialize stream state using Zustand's setState
    useConversationStreamStore.setState((state) => {
      state.activeStreams.set(conversationId, {
        conversationId,
        messages: [],
        isStreaming: true,
        error: null,
        abortController: new AbortController(),
        startedAt: Date.now(),
        pendingToolRequests: []
      })
    })

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
    const streamState = store.getStreamState(conversationId)
    expect(streamState?.messages).toHaveLength(4)
    expect(streamState?.messages).toEqual(events)
  })

  it('should handle multiple ToolCalls with different IDs', () => {
    const conversationId = Date.now() + 4 // Use unique ID for each test

    // Initialize stream state using Zustand's setState
    useConversationStreamStore.setState((state) => {
      state.activeStreams.set(conversationId, {
        conversationId,
        messages: [],
        isStreaming: true,
        error: null,
        abortController: new AbortController(),
        startedAt: Date.now(),
        pendingToolRequests: []
      })
    })

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
    const streamState = store.getStreamState(conversationId)
    expect(streamState?.messages).toHaveLength(1)
    expect(streamState?.messages[0]).toEqual(toolCall2)
  })
})
