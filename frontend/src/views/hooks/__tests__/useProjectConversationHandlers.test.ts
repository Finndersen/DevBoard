import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import React from 'react'
import { EventHandlerProvider } from '../../../hooks/useConversationEventHandlers'
import type { EventHandlerRegistry } from '../../../hooks/useConversationEventHandlers'
import { useProjectConversationHandlers } from '../useProjectConversationHandlers'
import { useConversationStreamStore } from '../../../stores/conversationStreamStore'
import type { ToolResult } from '../../../lib/api'

function createRegistry(): EventHandlerRegistry {
  return {
    toolCallHandlers: new Set(),
    toolResultHandlers: new Set(),
    systemEventHandlers: new Set(),
    streamCompleteHandlers: new Set(),
  }
}

function createWrapper(registry: EventHandlerRegistry) {
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return React.createElement(EventHandlerProvider, { value: registry }, children)
  }
}

function makeToolResult(content: string): ToolResult {
  return {
    event_type: 'tool_result',
    tool_call_id: 'call-123',
    result_content: content,
    is_error: false,
    timestamp: new Date().toISOString(),
  }
}

describe('useProjectConversationHandlers', () => {
  let registry: EventHandlerRegistry
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  let mockMigrateStream: any
  let originalMigrateStream: (oldConversationId: number, newConversationId: number) => void

  beforeEach(() => {
    registry = createRegistry()
    mockMigrateStream = vi.fn()
    originalMigrateStream = useConversationStreamStore.getState().migrateStream
    useConversationStreamStore.setState({ migrateStream: mockMigrateStream })
  })

  afterEach(() => {
    useConversationStreamStore.setState({ migrateStream: originalMigrateStream })
  })

  async function invokeToolResultHandlers(registry: EventHandlerRegistry, toolName: string, result: ToolResult) {
    const handlers = Array.from(registry.toolResultHandlers)
    await Promise.all(handlers.map(h => h(toolName, result)))
  }

  it('calls migrateStream, setActiveConversationId, updateConversationUrl, and invalidateConversations on refocus', async () => {
    const setActiveConversationId = vi.fn()
    const updateConversationUrl = vi.fn()
    const invalidateConversations = vi.fn()

    renderHook(() => useProjectConversationHandlers({
      activeConversationId: 10,
      setActiveConversationId,
      updateConversationUrl,
      invalidateConversations,
    }), { wrapper: createWrapper(registry) })

    await act(async () => {
      await invokeToolResultHandlers(registry, 'refocus_conversation', makeToolResult('REFOCUSED conversation_id=42'))
    })

    expect(mockMigrateStream).toHaveBeenCalledWith(10, 42)
    expect(setActiveConversationId).toHaveBeenCalledWith(42)
    expect(updateConversationUrl).toHaveBeenCalledWith(42)
    expect(invalidateConversations).toHaveBeenCalled()
  })

  it('does not call migrateStream when activeConversationId is null', async () => {
    const setActiveConversationId = vi.fn()
    const updateConversationUrl = vi.fn()
    const invalidateConversations = vi.fn()

    renderHook(() => useProjectConversationHandlers({
      activeConversationId: null,
      setActiveConversationId,
      updateConversationUrl,
      invalidateConversations,
    }), { wrapper: createWrapper(registry) })

    await act(async () => {
      await invokeToolResultHandlers(registry, 'refocus_conversation', makeToolResult('REFOCUSED conversation_id=42'))
    })

    expect(mockMigrateStream).not.toHaveBeenCalled()
    expect(setActiveConversationId).toHaveBeenCalledWith(42)
    expect(updateConversationUrl).toHaveBeenCalledWith(42)
    expect(invalidateConversations).toHaveBeenCalled()
  })

  it('ignores other tool names', async () => {
    const setActiveConversationId = vi.fn()
    const updateConversationUrl = vi.fn()
    const invalidateConversations = vi.fn()

    renderHook(() => useProjectConversationHandlers({
      activeConversationId: 10,
      setActiveConversationId,
      updateConversationUrl,
      invalidateConversations,
    }), { wrapper: createWrapper(registry) })

    await act(async () => {
      await invokeToolResultHandlers(registry, 'branch_conversation', makeToolResult('{"conversation_id": 99}'))
    })

    expect(mockMigrateStream).not.toHaveBeenCalled()
    expect(setActiveConversationId).not.toHaveBeenCalled()
    expect(updateConversationUrl).not.toHaveBeenCalled()
    expect(invalidateConversations).not.toHaveBeenCalled()
  })

  it('ignores malformed refocus result content', async () => {
    const setActiveConversationId = vi.fn()
    const updateConversationUrl = vi.fn()
    const invalidateConversations = vi.fn()

    renderHook(() => useProjectConversationHandlers({
      activeConversationId: 10,
      setActiveConversationId,
      updateConversationUrl,
      invalidateConversations,
    }), { wrapper: createWrapper(registry) })

    await act(async () => {
      await invokeToolResultHandlers(registry, 'refocus_conversation', makeToolResult('some unexpected output'))
    })

    expect(mockMigrateStream).not.toHaveBeenCalled()
    expect(setActiveConversationId).not.toHaveBeenCalled()
    expect(updateConversationUrl).not.toHaveBeenCalled()
    expect(invalidateConversations).not.toHaveBeenCalled()
  })
})
