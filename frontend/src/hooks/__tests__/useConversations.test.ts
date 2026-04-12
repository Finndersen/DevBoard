import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, waitFor, act } from '@testing-library/react'
import { enableMapSet } from 'immer'
import { useConversationStreamStore } from '../../stores/conversationStreamStore'

enableMapSet()

// Mock apiClient
vi.mock('../../lib/api', () => ({
  apiClient: {
    getConversations: vi.fn(),
    sendConversationMessage: vi.fn().mockResolvedValue(undefined),
    interruptConversation: vi.fn().mockResolvedValue(undefined),
  },
}))

// Mock Zustand stores
vi.mock('../../stores/uiStore', () => ({
  useUIStore: vi.fn(() => 0),
}))

describe('useConversations', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    useConversationStreamStore.setState({ activeStreams: new Map(), conversationMessages: new Map() })
  })

  it('triggers a follow-up fetch when a second lifecycle event arrives during an in-flight fetch', async () => {
    const { apiClient } = await import('../../lib/api')
    const { useConversations } = await import('../useConversations')

    let resolveFirst: (val: unknown) => void
    let resolveSecond: (val: unknown) => void

    const firstResult = [{ id: 1 }]
    const secondResult = [{ id: 1 }, { id: 2 }]

    const getConversationsMock = vi.mocked(apiClient.getConversations)
    getConversationsMock
      .mockImplementationOnce(() => new Promise(resolve => { resolveFirst = resolve }))
      .mockImplementationOnce(() => new Promise(resolve => { resolveSecond = resolve }))
      .mockResolvedValue([])

    const { result } = renderHook(() => useConversations())

    // First fetch triggered on mount — still in-flight
    await vi.waitFor(() => expect(getConversationsMock).toHaveBeenCalledTimes(1))

    // Fire two lifecycle 'active' events while the first fetch is in-flight
    act(() => {
      // Simulate via triggering active lifecycle through the store
      // We use the store's internal lifecycle directly
      const store = useConversationStreamStore.getState()
      // Trigger a stream lifecycle event to simulate what agent_run_started does
      store.reconnectStream(999) // This fires notifyStreamLifecycle(999, 'active')
    })

    // Still only one in-flight fetch (pendingRefetchRef should be set)
    expect(getConversationsMock).toHaveBeenCalledTimes(1)

    // Resolve the first fetch
    act(() => { resolveFirst!(firstResult) })

    // After first fetch resolves, the pending refetch should trigger automatically
    await waitFor(() => expect(getConversationsMock).toHaveBeenCalledTimes(2))

    // Resolve the second fetch
    act(() => { resolveSecond!(secondResult) })

    await waitFor(() => expect(result.current.data).toEqual(secondResult))
  })
})
