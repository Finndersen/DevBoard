import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { useConversationHistory } from '../hooks/useConversationHistory'
import { apiClient } from '../../../lib/api'
import type { ConversationEvent, ConversationMessagesResponse } from '../../../lib/api'

vi.mock('../../../lib/api', () => ({
  apiClient: {
    getConversationMessages: vi.fn(),
  },
}))

const mockGetMessages = vi.mocked(apiClient.getConversationMessages)

function makeResponse(messages: ConversationEvent[]): ConversationMessagesResponse {
  return { messages, context_usage: null }
}

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

  it('fetches history when historyLoaded is false on mount', async () => {
    const serverMessages = [makeTextEvent('hello')]
    mockGetMessages.mockResolvedValue(makeResponse(serverMessages))

    renderHook(() =>
      useConversationHistory(1, [], false, setStoreMessages, setApprovals, approvalKey),
    )

    await waitFor(() => {
      expect(mockGetMessages).toHaveBeenCalledWith(1)
    })

    await waitFor(() => {
      expect(setStoreMessages).toHaveBeenCalledWith(1, serverMessages, null)
    })
  })

  it('skips fetch when historyLoaded is true', () => {
    const existingMessages = [makeTextEvent('existing')]

    renderHook(() =>
      useConversationHistory(1, existingMessages, true, setStoreMessages, setApprovals, approvalKey),
    )

    expect(mockGetMessages).not.toHaveBeenCalled()
  })

  it('fetches history when historyLoaded is false even if messages exist (background streaming case)', async () => {
    // Background streaming: messages accumulated via addEvent but historyLoaded = false
    const streamingMessages = [makeTextEvent('streaming event')]
    const serverMessages = [makeTextEvent('full history')]
    mockGetMessages.mockResolvedValue(makeResponse(serverMessages))

    renderHook(() =>
      useConversationHistory(1, streamingMessages, false, setStoreMessages, setApprovals, approvalKey),
    )

    await waitFor(() => {
      expect(mockGetMessages).toHaveBeenCalledWith(1)
    })

    await waitFor(() => {
      expect(setStoreMessages).toHaveBeenCalledWith(1, serverMessages, null)
    })
  })

  it('re-fetches when historyLoaded transitions from true to false (simulating HMR store clear)', async () => {
    const serverMessages = [makeTextEvent('hello')]
    mockGetMessages.mockResolvedValue(makeResponse(serverMessages))

    // Initial render with historyLoaded: true — no fetch
    const { rerender } = renderHook(
      ({ historyLoaded }) =>
        useConversationHistory(1, [], historyLoaded, setStoreMessages, setApprovals, approvalKey),
      { initialProps: { historyLoaded: true } },
    )

    expect(mockGetMessages).not.toHaveBeenCalled()

    // Simulate HMR store clear: same conversationId, but historyLoaded now false
    rerender({ historyLoaded: false })

    await waitFor(() => {
      expect(mockGetMessages).toHaveBeenCalledWith(1)
    })

    await waitFor(() => {
      expect(setStoreMessages).toHaveBeenCalledWith(1, serverMessages, null)
    })
  })

  it('does not double-fetch on StrictMode double-render', async () => {
    mockGetMessages.mockResolvedValue(makeResponse([]))

    // Render twice rapidly with historyLoaded: false (simulating StrictMode)
    const { rerender } = renderHook(
      ({ historyLoaded }) =>
        useConversationHistory(1, [], historyLoaded, setStoreMessages, setApprovals, approvalKey),
      { initialProps: { historyLoaded: false } },
    )

    // Re-render with same props (StrictMode behavior)
    rerender({ historyLoaded: false })

    await waitFor(() => {
      expect(mockGetMessages).toHaveBeenCalledTimes(1)
    })
  })

  it('sets fetchHistoryError on API failure', async () => {
    mockGetMessages.mockRejectedValue(new Error('Server error'))

    const { result } = renderHook(() =>
      useConversationHistory(1, [], false, setStoreMessages, setApprovals, approvalKey),
    )

    await waitFor(() => {
      expect(result.current.fetchHistoryError).toBe(
        'Failed to load conversation history: Server error',
      )
    })
  })
})
