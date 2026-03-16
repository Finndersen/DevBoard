import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { useConversationHistory } from '../hooks/useConversationHistory'
import { apiClient } from '../../../lib/api'
import type { ConversationEvent } from '../../../lib/api'

vi.mock('../../../lib/api', () => ({
  apiClient: {
    getConversationMessages: vi.fn(),
  },
}))

const mockGetMessages = vi.mocked(apiClient.getConversationMessages)

const makeTextEvent = (text: string): ConversationEvent => ({
  event_type: 'message',
  role: 'agent',
  text_content: text,
  timestamp: new Date().toISOString(),
} as ConversationEvent)

describe('useConversationHistory', () => {
  const setStoreMessages = vi.fn()
  const setApprovals = vi.fn()
  const approvalKey = 'test-key'

  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('fetches history when messages are empty on mount', async () => {
    const serverMessages = [makeTextEvent('hello')]
    mockGetMessages.mockResolvedValue(serverMessages)

    renderHook(() =>
      useConversationHistory(1, [], setStoreMessages, setApprovals, approvalKey),
    )

    await waitFor(() => {
      expect(mockGetMessages).toHaveBeenCalledWith(1)
    })

    await waitFor(() => {
      expect(setStoreMessages).toHaveBeenCalledWith(1, serverMessages)
    })
  })

  it('does not fetch when messages already exist', () => {
    const existingMessages = [makeTextEvent('existing')]

    renderHook(() =>
      useConversationHistory(1, existingMessages, setStoreMessages, setApprovals, approvalKey),
    )

    expect(mockGetMessages).not.toHaveBeenCalled()
  })

  it('re-fetches when messages become empty (simulating HMR store clear)', async () => {
    const serverMessages = [makeTextEvent('hello')]
    mockGetMessages.mockResolvedValue(serverMessages)

    // Initial render with messages present — no fetch
    const { rerender } = renderHook(
      ({ messages }) =>
        useConversationHistory(1, messages, setStoreMessages, setApprovals, approvalKey),
      { initialProps: { messages: [makeTextEvent('existing')] } },
    )

    expect(mockGetMessages).not.toHaveBeenCalled()

    // Simulate HMR store clear: same conversationId, but messages now empty
    rerender({ messages: [] })

    await waitFor(() => {
      expect(mockGetMessages).toHaveBeenCalledWith(1)
    })

    await waitFor(() => {
      expect(setStoreMessages).toHaveBeenCalledWith(1, serverMessages)
    })
  })

  it('does not double-fetch on StrictMode double-render', async () => {
    mockGetMessages.mockResolvedValue([])

    // Render twice rapidly with empty messages (simulating StrictMode)
    const { rerender } = renderHook(
      ({ messages }) =>
        useConversationHistory(1, messages, setStoreMessages, setApprovals, approvalKey),
      { initialProps: { messages: [] as ConversationEvent[] } },
    )

    // Re-render with same props (StrictMode behavior)
    rerender({ messages: [] as ConversationEvent[] })

    await waitFor(() => {
      expect(mockGetMessages).toHaveBeenCalledTimes(1)
    })
  })

  it('sets fetchHistoryError on API failure', async () => {
    mockGetMessages.mockRejectedValue(new Error('Server error'))

    const { result } = renderHook(() =>
      useConversationHistory(1, [], setStoreMessages, setApprovals, approvalKey),
    )

    await waitFor(() => {
      expect(result.current.fetchHistoryError).toBe(
        'Failed to load conversation history: Server error',
      )
    })
  })
})
