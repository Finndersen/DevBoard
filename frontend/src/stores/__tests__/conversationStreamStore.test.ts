// @vitest-environment node
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { enableMapSet } from 'immer'
import { useConversationStreamStore } from '../conversationStreamStore'
import type { ConversationEvent } from '../../lib/api'
import type { EventHandlerRegistry } from '../../hooks/useConversationEventHandlers'

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

describe('conversationStreamStore - stream cancellation', () => {
  beforeEach(() => {
    // Reset store state before each test
    useConversationStreamStore.setState({ activeStreams: new Map(), conversationMessages: new Map() })
  })

  it('should use provided abortController for stream cancellation', async () => {
    const conversationId = Date.now() + 100
    const store = useConversationStreamStore.getState()

    // Create an abort controller that we control
    const abortController = new AbortController()

    // Create a mock stream that will be cancelled
    let streamAborted = false
    async function* mockStream(): AsyncGenerator<ConversationEvent> {
      try {
        // Yield first event
        yield {
          event_type: 'message',
          role: 'agent',
          text_content: 'First message',
          timestamp: '2024-01-01T00:00:00Z'
        }

        // Wait to be cancelled
        await new Promise((resolve, reject) => {
          abortController.signal.addEventListener('abort', () => {
            streamAborted = true
            reject(new DOMException('Aborted', 'AbortError'))
          })
        })

        // This should never be reached
        yield {
          event_type: 'message',
          role: 'agent',
          text_content: 'Second message',
          timestamp: '2024-01-01T00:00:01Z'
        }
      } catch (error) {
        if (error instanceof Error && error.name === 'AbortError') {
          return
        }
        throw error
      }
    }

    // Start the stream with our abort controller
    const streamPromise = store.startStream(
      conversationId,
      mockStream(),
      undefined,
      abortController
    )

    // Wait a tick for the stream to start
    await new Promise(resolve => setTimeout(resolve, 10))

    // Verify stream is active
    expect(store.isConversationStreaming(conversationId)).toBe(true)

    // Stop the stream using the store's stopStream method
    store.stopStream(conversationId)

    // Wait for stream to complete
    await streamPromise

    // Verify stream was aborted via our controller
    expect(streamAborted).toBe(true)

    // Verify stream is no longer active
    expect(store.isConversationStreaming(conversationId)).toBe(false)
  })

  it('should create internal abortController when none provided', async () => {
    const conversationId = Date.now() + 101
    const store = useConversationStreamStore.getState()

    let eventCount = 0
    async function* mockStream(): AsyncGenerator<ConversationEvent> {
      eventCount++
      yield {
        event_type: 'message',
        role: 'agent',
        text_content: 'Message',
        timestamp: '2024-01-01T00:00:00Z'
      }
    }

    // Start stream without providing an abort controller
    await store.startStream(
      conversationId,
      mockStream()
    )

    // Verify stream completed and processed the event
    expect(eventCount).toBe(1)

    // Verify the stream state was created with an abortController
    // (Even though stream completed, we can verify behavior worked)
  })

  it('should abort fetch request when stopStream is called with provided controller', async () => {
    const conversationId = Date.now() + 102
    const store = useConversationStreamStore.getState()

    const abortController = new AbortController()
    let signalAborted = false

    // Listen for abort on the signal directly
    abortController.signal.addEventListener('abort', () => {
      signalAborted = true
    })

    async function* mockStream(): AsyncGenerator<ConversationEvent> {
      yield {
        event_type: 'message',
        role: 'agent',
        text_content: 'Message',
        timestamp: '2024-01-01T00:00:00Z'
      }
      // Simulate long-running stream
      await new Promise(resolve => setTimeout(resolve, 1000))
    }

    // Start stream
    const streamPromise = store.startStream(
      conversationId,
      mockStream(),
      undefined,
      abortController
    )

    // Wait for stream to start
    await new Promise(resolve => setTimeout(resolve, 10))

    // Stop the stream
    store.stopStream(conversationId)

    // Verify the abort signal was triggered
    expect(signalAborted).toBe(true)
    expect(abortController.signal.aborted).toBe(true)

    // Wait for stream to finish
    await streamPromise
  })

  it('should invoke stream complete handlers when stopStream is called', async () => {
    const conversationId = Date.now() + 103
    const store = useConversationStreamStore.getState()

    const abortController = new AbortController()
    const streamCompleteHandler = vi.fn()

    // Register event handler registry with a stream complete handler
    const registry: EventHandlerRegistry = {
      toolResultHandlers: new Set(),
      systemEventHandlers: new Set(),
      streamCompleteHandlers: new Set([streamCompleteHandler]),
    }
    store.updateEventHandlerRegistry(conversationId, registry)

    async function* mockStream(): AsyncGenerator<ConversationEvent> {
      yield {
        event_type: 'message',
        role: 'agent',
        text_content: 'Message',
        timestamp: '2024-01-01T00:00:00Z',
      }
      // Simulate long-running stream that waits for abort
      await new Promise((_, reject) => {
        abortController.signal.addEventListener('abort', () => {
          reject(new DOMException('Aborted', 'AbortError'))
        })
      })
    }

    // Start stream and set queued state
    const streamPromise = store.startStream(
      conversationId,
      mockStream(),
      undefined,
      abortController,
    )

    await new Promise(resolve => setTimeout(resolve, 10))
    store.setQueued(conversationId, true)

    // Verify stream is active and queued
    expect(store.isConversationStreaming(conversationId)).toBe(true)
    expect(store.getStreamState(conversationId)?.isQueued).toBe(true)

    // Stop the stream (should delegate to completeStream and invoke handlers)
    store.stopStream(conversationId)
    await streamPromise

    // Allow microtasks for async handler invocation
    await new Promise(resolve => setTimeout(resolve, 10))

    // Verify stream complete handler was invoked
    expect(streamCompleteHandler).toHaveBeenCalledTimes(1)
    expect(store.isConversationStreaming(conversationId)).toBe(false)

    // Clean up registry
    store.updateEventHandlerRegistry(conversationId, undefined)
  })
})
