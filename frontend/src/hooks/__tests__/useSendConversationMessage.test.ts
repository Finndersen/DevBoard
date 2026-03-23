import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useSendConversationMessage } from '../useSendConversationMessage'

vi.mock('../../stores/conversationStreamStore', () => ({
  useConversationStreamStore: vi.fn()
}))

vi.mock('../../contexts/PendingMessagesContext', () => ({
  usePendingMessages: vi.fn()
}))

vi.mock('../../utils/approvalKeys', () => ({
  createConversationPendingKey: vi.fn((id: number) => `conversation-${id}`)
}))

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
    let capturedOnFirstEvent: (() => void) | undefined
    mockStartStream.mockImplementation(async (_id: number, _message: string, onFirstEvent: () => void) => {
      capturedOnFirstEvent = onFirstEvent
      onFirstEvent()
    })

    const { result } = renderHook(() => useSendConversationMessage({ conversationId }))

    await act(async () => {
      await result.current.sendMessage('Hello')
    })

    expect(mockStartStream).toHaveBeenCalledWith(
      conversationId,
      'Hello',
      expect.any(Function),
      expect.any(Function),
    )
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
    expect(mockUpdateMessageStatus).not.toHaveBeenCalledWith(pendingKey, pendingMessageId, 'failed', expect.anything())
    expect(capturedOnFirstEvent).toBeDefined()
  })

  it('marks message as failed when startStream throws (e.g. network error)', async () => {
    mockStartStream.mockRejectedValue(new Error('POST failed'))

    const { result } = renderHook(() => useSendConversationMessage({ conversationId }))

    await act(async () => {
      await result.current.sendMessage('Hello')
    })

    expect(mockUpdateMessageStatus).toHaveBeenCalledWith(pendingKey, pendingMessageId, 'failed', 'POST failed')
  })

  it('marks message as failed with connection error message for TypeError "Failed to fetch"', async () => {
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

  it('marks message as failed via onError when execution fails before first event', async () => {
    let capturedOnError: ((error: Error) => void) | undefined
    mockStartStream.mockImplementation(async (_id: number, _message: string, _onFirstEvent: () => void, onError: (error: Error) => void) => {
      capturedOnError = onError
      // POST succeeded but execution will fail later — onError is called asynchronously by the store
    })

    const { result } = renderHook(() => useSendConversationMessage({ conversationId }))

    await act(async () => {
      await result.current.sendMessage('Hello')
    })

    // Simulate the store calling onError when execution fails
    act(() => {
      capturedOnError?.(new Error('Agent execution failed'))
    })

    expect(mockUpdateMessageStatus).toHaveBeenCalledWith(
      pendingKey,
      pendingMessageId,
      'failed',
      'Agent execution failed'
    )
    expect(mockRemoveMessage).not.toHaveBeenCalled()
  })

  it('uses existing pending message ID for retry flow', async () => {
    const existingId = 'msg_existing'
    mockStartStream.mockImplementation(async (_id: number, _message: string, onFirstEvent: () => void) => {
      onFirstEvent()
    })

    const { result } = renderHook(() => useSendConversationMessage({ conversationId }))

    await act(async () => {
      await result.current.sendMessage('Retry message', existingId)
    })

    expect(mockAddPendingMessage).not.toHaveBeenCalled()
    expect(mockUpdateMessageStatus).toHaveBeenCalledWith(pendingKey, existingId, 'sent')
    expect(mockRemoveMessage).toHaveBeenCalledWith(pendingKey, existingId)
  })
})
