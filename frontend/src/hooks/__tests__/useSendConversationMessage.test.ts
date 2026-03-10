import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useSendConversationMessage } from '../useSendConversationMessage'

// Mock dependencies
vi.mock('../../lib/api', () => ({
  apiClient: {
    streamConversationMessage: vi.fn()
  }
}))

vi.mock('../../stores/conversationStreamStore', () => ({
  useConversationStreamStore: vi.fn()
}))

vi.mock('../../contexts/PendingMessagesContext', () => ({
  usePendingMessages: vi.fn()
}))

vi.mock('../../utils/approvalKeys', () => ({
  createConversationPendingKey: vi.fn((id: number) => `conversation-${id}`)
}))

import { apiClient } from '../../lib/api'
import { useConversationStreamStore } from '../../stores/conversationStreamStore'
import { usePendingMessages } from '../../contexts/PendingMessagesContext'

describe('useSendConversationMessage', () => {
  const conversationId = 42
  const pendingKey = `conversation-${conversationId}`
  const pendingMessageId = 'msg_123'

  const mockAddPendingMessage = vi.fn().mockReturnValue(pendingMessageId)
  const mockUpdateMessageStatus = vi.fn()
  const mockRemoveMessage = vi.fn()
  const mockStartStream = vi.fn()
  const mockAddEvent = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()

    vi.mocked(usePendingMessages).mockReturnValue({
      addPendingMessage: mockAddPendingMessage,
      updateMessageStatus: mockUpdateMessageStatus,
      removeMessage: mockRemoveMessage,
      state: { messages: {} },
      clearConversationMessages: vi.fn(),
      getPendingMessages: vi.fn(),
      hasPendingMessages: vi.fn(),
      retryMessage: vi.fn()
    })

    vi.mocked(useConversationStreamStore).mockImplementation((selector: (state: { startStream: typeof mockStartStream; addEvent: typeof mockAddEvent }) => unknown) =>
      selector({ startStream: mockStartStream, addEvent: mockAddEvent })
    )
  })

  it('sets status to sent, starts stream, and removes pending message on first event', async () => {
    const mockStream = {} as AsyncGenerator<never>
    vi.mocked(apiClient.streamConversationMessage).mockReturnValue(mockStream)

    let capturedOnFirstEvent: (() => void) | undefined
    mockStartStream.mockImplementation(async (_id: number, _stream: unknown, onFirstEvent: () => void) => {
      capturedOnFirstEvent = onFirstEvent
      onFirstEvent()
    })

    const { result } = renderHook(() => useSendConversationMessage({ conversationId }))

    await act(async () => {
      await result.current.sendMessage('Hello')
    })

    expect(mockAddPendingMessage).toHaveBeenCalledWith(pendingKey, {
      conversationId,
      text_content: 'Hello'
    })
    expect(mockUpdateMessageStatus).toHaveBeenCalledWith(pendingKey, pendingMessageId, 'sent')
    expect(mockAddEvent).toHaveBeenCalledWith(conversationId, expect.objectContaining({
      event_type: 'message',
      role: 'user',
      text_content: 'Hello'
    }))
    expect(mockRemoveMessage).toHaveBeenCalledWith(pendingKey, pendingMessageId)
    // Should NOT mark as failed since first event fired
    expect(mockUpdateMessageStatus).not.toHaveBeenCalledWith(pendingKey, pendingMessageId, 'failed', expect.anything())
  })

  it('marks message as failed when startStream throws (e.g. network error)', async () => {
    const mockStream = {} as AsyncGenerator<never>
    vi.mocked(apiClient.streamConversationMessage).mockReturnValue(mockStream)
    mockStartStream.mockRejectedValue(new Error('Stream failed'))

    const { result } = renderHook(() => useSendConversationMessage({ conversationId }))

    await act(async () => {
      await result.current.sendMessage('Hello')
    })

    expect(mockUpdateMessageStatus).toHaveBeenCalledWith(pendingKey, pendingMessageId, 'failed', 'Stream failed')
  })

  it('marks message as failed with connection error message for TypeError "Failed to fetch"', async () => {
    const mockStream = {} as AsyncGenerator<never>
    vi.mocked(apiClient.streamConversationMessage).mockReturnValue(mockStream)
    mockStartStream.mockRejectedValue(new TypeError('Failed to fetch'))

    const { result } = renderHook(() => useSendConversationMessage({ conversationId }))

    await act(async () => {
      await result.current.sendMessage('Hello')
    })

    expect(mockUpdateMessageStatus).toHaveBeenCalledWith(
      pendingKey,
      pendingMessageId,
      'failed',
      'Unable to connect to server. Please check if the backend is running.'
    )
  })

  it('marks message as failed when stream completes with no events (zero-event stream)', async () => {
    const mockStream = {} as AsyncGenerator<never>
    vi.mocked(apiClient.streamConversationMessage).mockReturnValue(mockStream)

    // startStream resolves normally but never calls onFirstEvent
    mockStartStream.mockImplementation(async () => {
      // No events, no onFirstEvent call
    })

    const { result } = renderHook(() => useSendConversationMessage({ conversationId }))

    await act(async () => {
      await result.current.sendMessage('Hello')
    })

    expect(mockUpdateMessageStatus).toHaveBeenCalledWith(
      pendingKey,
      pendingMessageId,
      'failed',
      'No response received. Please try again.'
    )
    expect(mockRemoveMessage).not.toHaveBeenCalled()
  })

  it('uses existing pending message ID for retry flow', async () => {
    const existingId = 'msg_existing'
    const mockStream = {} as AsyncGenerator<never>
    vi.mocked(apiClient.streamConversationMessage).mockReturnValue(mockStream)
    mockStartStream.mockImplementation(async (_id: number, _stream: unknown, onFirstEvent: () => void) => {
      onFirstEvent()
    })

    const { result } = renderHook(() => useSendConversationMessage({ conversationId }))

    await act(async () => {
      await result.current.sendMessage('Retry message', existingId)
    })

    // Should not create a new pending message
    expect(mockAddPendingMessage).not.toHaveBeenCalled()
    expect(mockUpdateMessageStatus).toHaveBeenCalledWith(pendingKey, existingId, 'sent')
    expect(mockRemoveMessage).toHaveBeenCalledWith(pendingKey, existingId)
  })
})
