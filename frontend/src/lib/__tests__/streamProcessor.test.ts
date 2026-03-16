// @vitest-environment node
import { describe, it, expect, vi } from 'vitest'
import { processConversationStream } from '../streamProcessor'
import type { ConversationEvent, ToolCallRequest } from '../api'
import { invokeEventHandlers } from '../../hooks/useConversationEventHandlers'
import type { EventHandlerRegistry } from '../../hooks/useConversationEventHandlers'

vi.mock('../../hooks/useConversationEventHandlers', () => ({
  invokeEventHandlers: vi.fn(),
}))

// Helper to create async generator from array
async function* createStream<T>(items: T[]): AsyncGenerator<T> {
  for (const item of items) {
    yield item
  }
}

describe('processConversationStream', () => {
  it('should process all events and return tool requests', async () => {
    const events: ConversationEvent[] = [
      { event_type: 'message', role: 'user', text_content: 'Hello', timestamp: '2024-01-01T00:00:00Z' },
      { event_type: 'tool_call', tool_call_id: 'tc1', tool_name: 'test_tool', tool_args: null, timestamp: '2024-01-01T00:00:01Z' },
      { event_type: 'tool_call_request', tool_call_id: 'tcr1', tool_name: 'approval_tool', tool_args: null, timestamp: '2024-01-01T00:00:02Z' },
      { event_type: 'message', role: 'agent', text_content: 'Response', timestamp: '2024-01-01T00:00:03Z' }
    ]

    const onEvent = vi.fn()
    const result = await processConversationStream({
      stream: createStream(events),
      onEvent
    })

    // Should return 1 tool request
    expect(result.toolRequests).toHaveLength(1)
    expect(result.toolRequests[0].tool_call_id).toBe('tcr1')

    // Should process all events
    expect(result.eventCount).toBe(4)

    // Should call onEvent for all 4 events + 1 synthesized error ToolResult for the unmatched tool_call
    expect(onEvent).toHaveBeenCalledTimes(5)
  })

  it('should invoke onFirstEvent callback once on first event', async () => {
    const events: ConversationEvent[] = [
      { event_type: 'message', role: 'user', text_content: 'Hello', timestamp: '2024-01-01T00:00:00Z' },
      { event_type: 'message', role: 'agent', text_content: 'Hi', timestamp: '2024-01-01T00:00:01Z' }
    ]

    const onFirstEvent = vi.fn()
    const onEvent = vi.fn()

    await processConversationStream({
      stream: createStream(events),
      onFirstEvent,
      onEvent
    })

    // Should call onFirstEvent exactly once
    expect(onFirstEvent).toHaveBeenCalledTimes(1)
    // Should still call onEvent for all non-tool-request events
    expect(onEvent).toHaveBeenCalledTimes(2)
  })

  it('should not invoke onFirstEvent if not provided', async () => {
    const events: ConversationEvent[] = [
      { event_type: 'message', role: 'user', text_content: 'Hello', timestamp: '2024-01-01T00:00:00Z' }
    ]

    const onEvent = vi.fn()

    const result = await processConversationStream({
      stream: createStream(events),
      onEvent
    })

    // Should process event normally without error
    expect(result.eventCount).toBe(1)
    expect(onEvent).toHaveBeenCalledTimes(1)
  })

  it('should handle stream with only tool requests', async () => {
    const events: ConversationEvent[] = [
      { event_type: 'tool_call_request', tool_call_id: 'tcr1', tool_name: 'tool1', tool_args: null, timestamp: '2024-01-01T00:00:00Z' },
      { event_type: 'tool_call_request', tool_call_id: 'tcr2', tool_name: 'tool2', tool_args: { arg: 'value' }, timestamp: '2024-01-01T00:00:01Z' }
    ]

    const onEvent = vi.fn()
    const result = await processConversationStream({
      stream: createStream(events),
      onEvent
    })

    // Should capture all tool requests
    expect(result.toolRequests).toHaveLength(2)
    expect(result.eventCount).toBe(2)

    // Should call onEvent for tool requests (for deduplication handling)
    expect(onEvent).toHaveBeenCalledTimes(2)
  })

  it('should handle empty stream', async () => {
    const events: ConversationEvent[] = []

    const onFirstEvent = vi.fn()
    const onEvent = vi.fn()

    const result = await processConversationStream({
      stream: createStream(events),
      onFirstEvent,
      onEvent
    })

    expect(result.toolRequests).toHaveLength(0)
    expect(result.eventCount).toBe(0)
    expect(onFirstEvent).not.toHaveBeenCalled()
    expect(onEvent).not.toHaveBeenCalled()
  })

  it('should support async callbacks', async () => {
    const events: ConversationEvent[] = [
      { event_type: 'message', role: 'user', text_content: 'Hello', timestamp: '2024-01-01T00:00:00Z' }
    ]

    const onFirstEvent = vi.fn(async () => {
      await new Promise(resolve => setTimeout(resolve, 10))
    })

    const onEvent = vi.fn(async () => {
      await new Promise(resolve => setTimeout(resolve, 10))
    })

    await processConversationStream({
      stream: createStream(events),
      onFirstEvent,
      onEvent
    })

    expect(onFirstEvent).toHaveBeenCalledTimes(1)
    expect(onEvent).toHaveBeenCalledTimes(1)
  })

  it('should preserve tool request properties', async () => {
    const toolRequest: ToolCallRequest = {
      event_type: 'tool_call_request',
      tool_call_id: 'tcr123',
      tool_name: 'document_edit',
      tool_args: { path: '/test.md', content: 'new content' },
      timestamp: '2024-01-01T00:00:00Z'
    }

    const events: ConversationEvent[] = [toolRequest]

    const onEvent = vi.fn()
    const result = await processConversationStream({
      stream: createStream(events),
      onEvent
    })

    expect(result.toolRequests).toHaveLength(1)
    expect(result.toolRequests[0]).toEqual(toolRequest)
  })

  it('should call onEvent with correct event data', async () => {
    const messageEvent: ConversationEvent = {
      event_type: 'message',
      role: 'agent',
      text_content: 'Test message',
      timestamp: '2024-01-01T00:00:00Z'
    }

    const events: ConversationEvent[] = [messageEvent]

    const onEvent = vi.fn()

    await processConversationStream({
      stream: createStream(events),
      onEvent
    })

    expect(onEvent).toHaveBeenCalledWith(messageEvent)
  })

  it('should handle stream errors gracefully', async () => {
    async function* errorStream(): AsyncGenerator<ConversationEvent> {
      yield { event_type: 'message', role: 'user', text_content: 'Hello', timestamp: '2024-01-01T00:00:00Z' }
      throw new Error('Stream error')
    }

    const onEvent = vi.fn()

    await expect(
      processConversationStream({
        stream: errorStream(),
        onEvent
      })
    ).rejects.toThrow('Stream error')
  })

  it('should synthesize error ToolResult for tool calls without matching results when stream ends normally', async () => {
    const events: ConversationEvent[] = [
      { event_type: 'message', role: 'user', text_content: 'Hello', timestamp: '2024-01-01T00:00:00Z' },
      { event_type: 'tool_call', tool_call_id: 'tc1', tool_name: 'investigate_codebase', tool_args: null, timestamp: '2024-01-01T00:00:01Z' },
    ]

    const onEvent = vi.fn()
    await processConversationStream({
      stream: createStream(events),
      onEvent,
    })

    // onEvent called for 2 real events + 1 synthesized ToolResult
    expect(onEvent).toHaveBeenCalledTimes(3)
    const synthesized = onEvent.mock.calls[2][0]
    expect(synthesized).toMatchObject({
      event_type: 'tool_result',
      tool_call_id: 'tc1',
      result_content: 'Tool execution was interrupted.',
      is_error: true,
    })
  })

  it('should synthesize error ToolResult when stream ends with stream_error', async () => {
    const events: ConversationEvent[] = [
      { event_type: 'tool_call', tool_call_id: 'tc1', tool_name: 'run_code', tool_args: null, timestamp: '2024-01-01T00:00:00Z' },
      { event_type: 'system', type: 'stream_error', data: { message: 'Server error' }, timestamp: '2024-01-01T00:00:01Z' },
    ]

    const onEvent = vi.fn()

    await expect(
      processConversationStream({
        stream: createStream(events),
        onEvent,
      })
    ).rejects.toThrow('Server error')

    // 2 real events + 1 synthesized in finally block
    expect(onEvent).toHaveBeenCalledTimes(3)
    const synthesized = onEvent.mock.calls[2][0]
    expect(synthesized).toMatchObject({
      event_type: 'tool_result',
      tool_call_id: 'tc1',
      is_error: true,
    })
  })

  it('should not synthesize results for tool calls that already have results', async () => {
    const events: ConversationEvent[] = [
      { event_type: 'tool_call', tool_call_id: 'tc1', tool_name: 'read_file', tool_args: null, timestamp: '2024-01-01T00:00:00Z' },
      { event_type: 'tool_result', tool_call_id: 'tc1', result_content: 'file contents', is_error: false, timestamp: '2024-01-01T00:00:01Z' },
      { event_type: 'message', role: 'agent', text_content: 'Done', timestamp: '2024-01-01T00:00:02Z' },
    ]

    const onEvent = vi.fn()
    await processConversationStream({
      stream: createStream(events),
      onEvent,
    })

    // Only 3 real events, no synthesized results
    expect(onEvent).toHaveBeenCalledTimes(3)
    // Verify no synthesized tool_result was added
    const toolResults = onEvent.mock.calls
      .map(call => call[0])
      .filter((e: ConversationEvent) => e.event_type === 'tool_result')
    expect(toolResults).toHaveLength(1)
    expect(toolResults[0].is_error).toBe(false)
  })

  it('should call getEventHandlerRegistry getter per-event for tool calls, tool results and system events', async () => {
    const mockedInvokeEventHandlers = vi.mocked(invokeEventHandlers)
    mockedInvokeEventHandlers.mockReset()

    const events: ConversationEvent[] = [
      { event_type: 'tool_call', tool_call_id: 'tc1', tool_name: 'read_file', tool_args: null, timestamp: '2024-01-01T00:00:00Z' },
      { event_type: 'tool_result', tool_call_id: 'tc1', result_content: 'file contents', is_error: false, timestamp: '2024-01-01T00:00:01Z' },
      { event_type: 'system', type: 'status', data: { message: 'Processing' }, timestamp: '2024-01-01T00:00:02Z' },
    ]

    const mockRegistry: EventHandlerRegistry = {
      toolCallHandlers: new Set(),
      toolResultHandlers: new Set(),
      systemEventHandlers: new Set(),
      streamCompleteHandlers: new Set(),
    }

    const getEventHandlerRegistry = vi.fn(() => mockRegistry)
    const onEvent = vi.fn()

    await processConversationStream({
      stream: createStream(events),
      onEvent,
      getEventHandlerRegistry,
    })

    // Getter called once per tool_call + once per tool_result + once per system event = 3 times
    expect(getEventHandlerRegistry).toHaveBeenCalledTimes(3)

    // invokeEventHandlers called with the registry for each qualifying event
    expect(mockedInvokeEventHandlers).toHaveBeenCalledTimes(3)
    expect(mockedInvokeEventHandlers).toHaveBeenCalledWith(
      expect.objectContaining({ event_type: 'tool_call', tool_call_id: 'tc1' }),
      mockRegistry,
      expect.any(Map),
    )
    expect(mockedInvokeEventHandlers).toHaveBeenCalledWith(
      expect.objectContaining({ event_type: 'tool_result', tool_call_id: 'tc1' }),
      mockRegistry,
      expect.any(Map),
    )
    expect(mockedInvokeEventHandlers).toHaveBeenCalledWith(
      expect.objectContaining({ event_type: 'system', type: 'status' }),
      mockRegistry,
      expect.any(Map),
    )
  })

  it('should handle getEventHandlerRegistry returning undefined initially then a registry later', async () => {
    const mockedInvokeEventHandlers = vi.mocked(invokeEventHandlers)
    mockedInvokeEventHandlers.mockReset()

    const events: ConversationEvent[] = [
      { event_type: 'tool_call', tool_call_id: 'tc1', tool_name: 'read_file', tool_args: null, timestamp: '2024-01-01T00:00:00Z' },
      { event_type: 'tool_result', tool_call_id: 'tc1', result_content: 'first result', is_error: false, timestamp: '2024-01-01T00:00:01Z' },
      { event_type: 'tool_call', tool_call_id: 'tc2', tool_name: 'write_file', tool_args: null, timestamp: '2024-01-01T00:00:02Z' },
      { event_type: 'tool_result', tool_call_id: 'tc2', result_content: 'second result', is_error: false, timestamp: '2024-01-01T00:00:03Z' },
    ]

    const mockRegistry: EventHandlerRegistry = {
      toolCallHandlers: new Set(),
      toolResultHandlers: new Set(),
      systemEventHandlers: new Set(),
      streamCompleteHandlers: new Set(),
    }

    const getEventHandlerRegistry = vi.fn()
      .mockReturnValueOnce(undefined) // tc1 tool_call
      .mockReturnValueOnce(undefined) // tc1 tool_result
      .mockReturnValueOnce(mockRegistry) // tc2 tool_call
      .mockReturnValueOnce(mockRegistry) // tc2 tool_result

    const onEvent = vi.fn()

    await processConversationStream({
      stream: createStream(events),
      onEvent,
      getEventHandlerRegistry,
    })

    // Getter called for both tool_call + tool_result events = 4 times
    expect(getEventHandlerRegistry).toHaveBeenCalledTimes(4)

    // invokeEventHandlers called twice (tc2 tool_call and tc2 tool_result), since first two returned undefined
    expect(mockedInvokeEventHandlers).toHaveBeenCalledTimes(2)
    expect(mockedInvokeEventHandlers).toHaveBeenCalledWith(
      expect.objectContaining({ event_type: 'tool_call', tool_call_id: 'tc2' }),
      mockRegistry,
      expect.any(Map),
    )
    expect(mockedInvokeEventHandlers).toHaveBeenCalledWith(
      expect.objectContaining({ event_type: 'tool_result', tool_call_id: 'tc2' }),
      mockRegistry,
      expect.any(Map),
    )
  })
})
