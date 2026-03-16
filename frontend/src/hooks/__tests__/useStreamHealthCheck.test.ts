import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook } from '@testing-library/react'
import { enableMapSet } from 'immer'
import { useStreamHealthCheck } from '../useStreamHealthCheck'
import { apiClient } from '../../lib/api'
import { useConversationStreamStore } from '../../stores/conversationStreamStore'

enableMapSet()

vi.mock('../../lib/api', () => ({
  apiClient: {
    getActiveExecutions: vi.fn(),
  },
}))

const mockGetActiveExecutions = vi.mocked(apiClient.getActiveExecutions)

describe('useStreamHealthCheck', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.clearAllMocks()

    // Reset store state
    const store = useConversationStreamStore.getState()
    for (const id of store.getAllStreamingConversations()) {
      store.completeStream(id)
    }
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('reconnects orphaned backend executions', async () => {
    mockGetActiveExecutions.mockResolvedValue({
      executions: [
        {
          conversation_id: 42,
          status: 'running',
          started_at: '2026-01-01T00:00:00Z',
          parent_entity_type: 'project',
          agent_role: 'project_qa',
          task_id: null,
          task_title: null,
        },
      ],
    })

    const reconnectSpy = vi.spyOn(useConversationStreamStore.getState(), 'reconnectStream')
      .mockResolvedValue(undefined)

    renderHook(() => useStreamHealthCheck())

    // Advance past initial delay
    await vi.advanceTimersByTimeAsync(15_000)

    expect(mockGetActiveExecutions).toHaveBeenCalledTimes(1)
    expect(reconnectSpy).toHaveBeenCalledWith(42)

    reconnectSpy.mockRestore()
  })

  it('completes stale frontend streams with no backend execution', async () => {
    mockGetActiveExecutions.mockResolvedValue({ executions: [] })

    // Set up a frontend stream with no backend execution
    useConversationStreamStore.setState((state) => {
      state.activeStreams.set(99, {
        isStreaming: true,
        error: null,
        startedAt: Date.now(),
        pendingToolRequests: [],
        isQueued: false,
      })
    })

    const completeSpy = vi.spyOn(useConversationStreamStore.getState(), 'completeStream')

    renderHook(() => useStreamHealthCheck())

    await vi.advanceTimersByTimeAsync(15_000)

    expect(completeSpy).toHaveBeenCalledWith(99)

    completeSpy.mockRestore()
  })

  it('does nothing when frontend and backend are in sync', async () => {
    mockGetActiveExecutions.mockResolvedValue({
      executions: [
        {
          conversation_id: 10,
          status: 'running',
          started_at: '2026-01-01T00:00:00Z',
          parent_entity_type: 'project',
          agent_role: 'project_qa',
          task_id: null,
          task_title: null,
        },
      ],
    })

    // Set up matching frontend stream
    useConversationStreamStore.setState((state) => {
      state.activeStreams.set(10, {
        isStreaming: true,
        error: null,
        startedAt: Date.now(),
        pendingToolRequests: [],
        isQueued: false,
      })
    })

    const reconnectSpy = vi.spyOn(useConversationStreamStore.getState(), 'reconnectStream')
      .mockResolvedValue(undefined)
    const completeSpy = vi.spyOn(useConversationStreamStore.getState(), 'completeStream')

    renderHook(() => useStreamHealthCheck())

    await vi.advanceTimersByTimeAsync(15_000)

    expect(reconnectSpy).not.toHaveBeenCalled()
    expect(completeSpy).not.toHaveBeenCalled()

    reconnectSpy.mockRestore()
    completeSpy.mockRestore()
  })

  it('handles API errors gracefully and continues polling', async () => {
    mockGetActiveExecutions
      .mockRejectedValueOnce(new Error('Network error'))
      .mockResolvedValueOnce({ executions: [] })

    renderHook(() => useStreamHealthCheck())

    // First check fails
    await vi.advanceTimersByTimeAsync(15_000)
    expect(mockGetActiveExecutions).toHaveBeenCalledTimes(1)

    // Second check succeeds on next interval
    await vi.advanceTimersByTimeAsync(15_000)
    expect(mockGetActiveExecutions).toHaveBeenCalledTimes(2)
  })

  it('skips polling when both frontend and backend were idle in last check', async () => {
    // First check: backend returns empty (lastBackendHadExecutions → false)
    mockGetActiveExecutions.mockResolvedValue({ executions: [] })

    renderHook(() => useStreamHealthCheck())

    await vi.advanceTimersByTimeAsync(15_000)
    expect(mockGetActiveExecutions).toHaveBeenCalledTimes(1)

    // Second interval: frontend still empty, last backend check was empty → skip
    await vi.advanceTimersByTimeAsync(15_000)
    expect(mockGetActiveExecutions).toHaveBeenCalledTimes(1)
  })

  it('resumes polling when frontend has active streams after an idle period', async () => {
    // First check: both idle
    mockGetActiveExecutions.mockResolvedValue({ executions: [] })

    const { rerender } = renderHook(() => useStreamHealthCheck())

    await vi.advanceTimersByTimeAsync(15_000)
    expect(mockGetActiveExecutions).toHaveBeenCalledTimes(1)

    // Add a frontend stream mid-session
    useConversationStreamStore.setState((state) => {
      state.activeStreams.set(55, {
        isStreaming: true,
        error: null,
        startedAt: Date.now(),
        pendingToolRequests: [],
        isQueued: false,
      })
    })
    rerender()

    // Next interval: frontend has a stream → poll runs
    await vi.advanceTimersByTimeAsync(15_000)
    expect(mockGetActiveExecutions).toHaveBeenCalledTimes(2)
  })

  it('cleans up timers on unmount', () => {
    const { unmount } = renderHook(() => useStreamHealthCheck())

    unmount()

    // Advancing timers should not trigger any API calls
    mockGetActiveExecutions.mockResolvedValue({ executions: [] })
    vi.advanceTimersByTime(30_000)

    expect(mockGetActiveExecutions).not.toHaveBeenCalled()
  })
})
