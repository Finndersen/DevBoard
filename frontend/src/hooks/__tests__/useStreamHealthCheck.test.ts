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

    const store = useConversationStreamStore.getState()
    for (const id of store.getAllStreamingConversations()) {
      store.completeStream(id)
    }
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('sets error on stale frontend streams with no backend execution', async () => {
    mockGetActiveExecutions.mockResolvedValue({ executions: [] })

    useConversationStreamStore.setState((state) => {
      state.activeStreams.set(99, {
        isStreaming: true,
        error: null,
        startedAt: Date.now(),
        pendingToolRequests: [],
        isQueued: false,
      })
    })

    const setErrorSpy = vi.spyOn(useConversationStreamStore.getState(), 'setError')

    renderHook(() => useStreamHealthCheck())

    await vi.advanceTimersByTimeAsync(15_000)

    expect(setErrorSpy).toHaveBeenCalledWith(99, expect.any(Error))

    setErrorSpy.mockRestore()
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

    useConversationStreamStore.setState((state) => {
      state.activeStreams.set(10, {
        isStreaming: true,
        error: null,
        startedAt: Date.now(),
        pendingToolRequests: [],
        isQueued: false,
      })
    })

    const setErrorSpy = vi.spyOn(useConversationStreamStore.getState(), 'setError')

    renderHook(() => useStreamHealthCheck())

    await vi.advanceTimersByTimeAsync(15_000)

    expect(setErrorSpy).not.toHaveBeenCalled()

    setErrorSpy.mockRestore()
  })

  it('handles API errors gracefully and continues polling', async () => {
    mockGetActiveExecutions
      .mockRejectedValueOnce(new Error('Network error'))
      .mockResolvedValueOnce({ executions: [] })

    renderHook(() => useStreamHealthCheck())

    await vi.advanceTimersByTimeAsync(15_000)
    expect(mockGetActiveExecutions).toHaveBeenCalledTimes(1)

    await vi.advanceTimersByTimeAsync(15_000)
    expect(mockGetActiveExecutions).toHaveBeenCalledTimes(2)
  })

  it('skips polling when both frontend and backend were idle in last check', async () => {
    mockGetActiveExecutions.mockResolvedValue({ executions: [] })

    renderHook(() => useStreamHealthCheck())

    await vi.advanceTimersByTimeAsync(15_000)
    expect(mockGetActiveExecutions).toHaveBeenCalledTimes(1)

    await vi.advanceTimersByTimeAsync(15_000)
    expect(mockGetActiveExecutions).toHaveBeenCalledTimes(1)
  })

  it('resumes polling when frontend has active streams after an idle period', async () => {
    mockGetActiveExecutions.mockResolvedValue({ executions: [] })

    const { rerender } = renderHook(() => useStreamHealthCheck())

    await vi.advanceTimersByTimeAsync(15_000)
    expect(mockGetActiveExecutions).toHaveBeenCalledTimes(1)

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

    await vi.advanceTimersByTimeAsync(15_000)
    expect(mockGetActiveExecutions).toHaveBeenCalledTimes(2)
  })

  it('cleans up timers on unmount', () => {
    const { unmount } = renderHook(() => useStreamHealthCheck())

    unmount()

    mockGetActiveExecutions.mockResolvedValue({ executions: [] })
    vi.advanceTimersByTime(30_000)

    expect(mockGetActiveExecutions).not.toHaveBeenCalled()
  })
})
