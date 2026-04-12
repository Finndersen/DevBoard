import { describe, it, expect, beforeEach, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { enableMapSet } from 'immer'
import { http, HttpResponse } from 'msw'
import { server } from '../../test/setup'
import { render } from '../../test/utils'
import ConversationChat from '../chat/ConversationChat'
import { useConversationStreamStore } from '../../stores/conversationStreamStore'
import { useApprovalsStore } from '../../stores/approvalsStore'
import type { ConversationEvent } from '../../lib/api'

enableMapSet()

vi.mock('../../contexts/ViewContext', () => ({
  useViewContext: () => ({ viewId: 'test-view', viewType: 'task', entityId: '1' })
}))

// Inject events into the store's push handler, simulating WebSocket messages
function injectWsEvents(conversationId: number, events: ConversationEvent[]): void {
  const store = useConversationStreamStore.getState()
  for (const event of events) {
    store.handleWebSocketEvent(conversationId, event)
  }
  // execution_complete terminates the stream
  store.handleWebSocketEvent(conversationId, {
    event_type: 'agent_run_completed',
    status: 'completed',
    error: null,
    timestamp: new Date().toISOString(),
    conversation_id: conversationId,
  } as unknown as ConversationEvent)
}

describe('ConversationChat', () => {
  const mockConversationId = 1

  // Default message history for tests that expect a populated chat
  const defaultChatHistory = [
    {
      event_type: 'message',
      text_content: 'What is the status?',
      role: 'user',
      timestamp: '2024-01-01T10:00:00Z',
    },
    {
      event_type: 'message',
      text_content: 'The project is progressing well.',
      role: 'agent',
      timestamp: '2024-01-01T10:01:00Z',
    },
  ]

  beforeEach(() => {
    vi.clearAllMocks()

    // Clear any localStorage state that might interfere
    localStorage.clear()

    // Clear the conversationStreamStore between tests to prevent state pollution
    // Replace the Map entirely to ensure complete cleanup
    useConversationStreamStore.setState({ activeStreams: new Map(), conversationMessages: new Map() })

    // Clear the approvalsStore between tests
    useApprovalsStore.setState({ approvals: {} })

    // Mock scrollIntoView which is not available in jsdom
    Element.prototype.scrollIntoView = vi.fn()

    // Reset server handlers to defaults for each test
    server.resetHandlers()

    // Setup default handlers
    // Individual tests can override these with server.use() if they need specific data
    server.use(
      http.get('*/api/conversations/1/messages', () => {
        return HttpResponse.json({ messages: [], context_usage: null })
      }),
      http.get('*/api/executions/active', () => {
        return HttpResponse.json({ executions: [] })
      }),
      http.post('*/api/conversations/1/messages', () => {
        return HttpResponse.json({ conversation_id: 1 })
      })
    )
  })

  it('renders chat interface with input and messages area', async () => {
    render(<ConversationChat conversationId={mockConversationId} />)

    await waitFor(() => {
      expect(screen.getByPlaceholderText(/ask a question/i)).toBeInTheDocument()
    })

    expect(screen.getByRole('button', { name: /send message/i })).toBeInTheDocument()
  })

  it('loads and displays chat history on mount', async () => {
    server.use(
      http.get('*/api/conversations/1/messages', () => {
        return HttpResponse.json({ messages: defaultChatHistory, context_usage: null })
      })
    )

    render(<ConversationChat conversationId={mockConversationId} />)

    await waitFor(() => {
      expect(screen.getByText('What is the status?')).toBeInTheDocument()
      expect(screen.getByText('The project is progressing well.')).toBeInTheDocument()
    })
  })

  it('displays messages with correct user/assistant styling', async () => {
    server.use(
      http.get('*/api/conversations/1/messages', () => {
        return HttpResponse.json({ messages: defaultChatHistory, context_usage: null })
      })
    )

    render(<ConversationChat conversationId={mockConversationId} />)

    await waitFor(() => {
      expect(screen.getByText('What is the status?')).toBeInTheDocument()
    })

    // Check that user messages have correct styling (subtle full-width background)
    const userMessageText = screen.getByText('What is the status?')
    const userContainer = userMessageText.closest('.bg-gray-100')
    expect(userContainer).toBeInTheDocument()

    // Check that assistant messages render without background
    const assistantMessageText = screen.getByText('The project is progressing well.')
    expect(assistantMessageText).toBeInTheDocument()
  })

  it('sends new message when form is submitted', async () => {
    const user = userEvent.setup()

    server.use(
      http.post('*/api/conversations/1/messages', () => {
        setTimeout(() => injectWsEvents(mockConversationId, [
          {
            event_type: 'message',
            text_content: 'AI response to: New question',
            role: 'agent',
            timestamp: new Date().toISOString()
          }
        ]), 0)
        return HttpResponse.json({ conversation_id: 1 })
      })
    )

    render(<ConversationChat conversationId={mockConversationId} />)

    await waitFor(() => {
      expect(screen.getByPlaceholderText(/ask a question/i)).toBeInTheDocument()
    })

    const input = screen.getByPlaceholderText(/ask a question/i)
    const sendButton = screen.getByRole('button', { name: /send message/i })

    await user.type(input, 'New question')
    await user.click(sendButton)

    // Input should be cleared immediately
    expect(input).toHaveValue('')

    // Check that the message appears somewhere - either as pending or confirmed
    await waitFor(() => {
      const messages = screen.getAllByText(/New question|AI response to: New question/)
      expect(messages.length).toBeGreaterThan(0)
    }, { timeout: 3000 })

    // Should show AI response after API call
    await waitFor(() => {
      expect(screen.getByText('AI response to: New question')).toBeInTheDocument()
    }, { timeout: 3000 })
  })

  it('sends message on Enter key press', async () => {
    const user = userEvent.setup()

    server.use(
      http.post('*/api/conversations/1/messages', () => {
        setTimeout(() => injectWsEvents(mockConversationId, [
          {
            event_type: 'message',
            text_content: 'AI response',
            role: 'agent',
            timestamp: new Date().toISOString()
          }
        ]), 0)
        return HttpResponse.json({ conversation_id: 1 })
      })
    )

    render(<ConversationChat conversationId={mockConversationId} />)

    await waitFor(() => {
      expect(screen.getByPlaceholderText(/ask a question/i)).toBeInTheDocument()
    })

    const input = screen.getByPlaceholderText(/ask a question/i)

    await user.type(input, 'Test message{enter}')

    await waitFor(() => {
      const messages = screen.getAllByText(/Test message|AI response/)
      expect(messages.length).toBeGreaterThan(0)
    })
  })

  it('allows multi-line input with Shift+Enter but submits on Enter', async () => {
    const user = userEvent.setup()

    server.use(
      http.post('*/api/conversations/1/messages', () => {
        setTimeout(() => injectWsEvents(mockConversationId, [
          {
            event_type: 'message',
            text_content: 'Got: Line 1\nLine 2\nLine 3',
            role: 'agent',
            timestamp: new Date().toISOString()
          }
        ]), 0)
        return HttpResponse.json({ conversation_id: 1 })
      })
    )

    render(<ConversationChat conversationId={mockConversationId} />)

    await waitFor(() => {
      expect(screen.getByPlaceholderText(/ask a question/i)).toBeInTheDocument()
    })

    const textarea = screen.getByPlaceholderText(/ask a question/i)

    // Type multi-line message with Shift+Enter
    await user.type(textarea, 'Line 1{Shift>}{Enter}{/Shift}Line 2{Shift>}{Enter}{/Shift}Line 3')

    // Verify multi-line content is in textarea
    expect(textarea).toHaveValue('Line 1\nLine 2\nLine 3')

    // Press Enter without Shift to submit
    await user.type(textarea, '{Enter}')

    // Should clear the input immediately
    expect(textarea).toHaveValue('')

    // Should send multi-line message and get response
    await waitFor(() => {
      expect(screen.getByText(/Got: Line 1.*Line 2.*Line 3/s)).toBeInTheDocument()
    }, { timeout: 3000 })
  })

  it('prevents sending empty messages', async () => {
    const user = userEvent.setup()

    render(<ConversationChat conversationId={mockConversationId} />)

    await waitFor(() => {
      expect(screen.getByPlaceholderText(/ask a question/i)).toBeInTheDocument()
    })

    const sendButton = screen.getByRole('button', { name: /send message/i })

    // Button should be disabled when input is empty
    expect(sendButton).toBeDisabled()

    // Try to click disabled button - should not work
    await user.click(sendButton)

    // No new messages should be added (empty state message should still be shown)
    expect(screen.getByText(/start a conversation/i)).toBeInTheDocument()
  })

  it('shows loading state while sending message', async () => {
    const user = userEvent.setup()

    server.use(
      http.post('*/api/conversations/1/messages', async () => {
        await new Promise(resolve => setTimeout(resolve, 200))
        setTimeout(() => injectWsEvents(mockConversationId, [
          {
            event_type: 'message',
            text_content: 'AI response',
            role: 'agent',
            timestamp: new Date().toISOString()
          }
        ]), 0)
        return HttpResponse.json({ conversation_id: 1 })
      })
    )

    render(<ConversationChat conversationId={mockConversationId} />)

    await waitFor(() => {
      expect(screen.getByPlaceholderText(/ask a question/i)).toBeInTheDocument()
    })

    const input = screen.getByPlaceholderText(/ask a question/i)
    const sendButton = screen.getByRole('button', { name: /send message/i })

    await user.type(input, 'Test message')
    await user.click(sendButton)

    // Stop button should appear during streaming (replaces send button)
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /stop streaming/i })).toBeInTheDocument()
    })

    // Should show user message immediately (may be in pending state)
    await waitFor(() => {
      const messages = screen.getAllByText(/Test message|AI response/)
      expect(messages.length).toBeGreaterThan(0)
    })

    // Wait for response and send button to reappear
    await waitFor(() => {
      expect(screen.getByText('AI response')).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /send message/i })).toBeInTheDocument()
    }, { timeout: 3000 })
  })

  it('handles API error when loading history', async () => {
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})

    server.use(
      http.get('*/api/conversations/1/messages', () => {
        return new HttpResponse(null, { status: 500 })
      })
    )

    render(<ConversationChat conversationId={mockConversationId} />)

    // History fetch errors are logged to console
    await waitFor(() => {
      expect(consoleSpy).toHaveBeenCalledWith('Failed to fetch chat history:', expect.any(Error))
    })

    consoleSpy.mockRestore()
  })

  it('handles API error when sending message', async () => {
    const user = userEvent.setup()
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})

    server.use(
      http.post('*/api/conversations/1/messages', () => {
        return new HttpResponse(null, { status: 500 })
      })
    )

    render(<ConversationChat conversationId={mockConversationId} />)

    await waitFor(() => {
      expect(screen.getByPlaceholderText(/ask a question/i)).toBeInTheDocument()
    })

    const input = screen.getByPlaceholderText(/ask a question/i)
    const sendButton = screen.getByRole('button', { name: /send message/i })

    await user.type(input, 'Test message')
    await user.click(sendButton)

    // Error should be logged
    await waitFor(() => {
      expect(consoleSpy).toHaveBeenCalled()
    })

    consoleSpy.mockRestore()
  })

  it('renders messages from history correctly', async () => {
    const testDate = '2024-01-01T15:30:00Z'

    server.use(
      http.get('*/api/conversations/1/messages', () => {
        return HttpResponse.json({ messages: [
          {
            event_type: 'message',
            text_content: 'Test message from history',
            role: 'user',
            timestamp: testDate,
          },
        ], context_usage: null })
      })
    )

    render(<ConversationChat conversationId={mockConversationId} />)

    // Verify message from history is rendered
    await waitFor(() => {
      expect(screen.getByText('Test message from history')).toBeInTheDocument()
    })
  })

  it('auto-scrolls to bottom when new messages are added', async () => {
    const user = userEvent.setup()

    // Mock scrollTop property on HTMLElement
    const mockScrollTop = vi.fn()
    Object.defineProperty(HTMLElement.prototype, 'scrollTop', {
      set: mockScrollTop,
      get: () => 0,
      configurable: true
    })

    // Mock scrollHeight property
    Object.defineProperty(HTMLElement.prototype, 'scrollHeight', {
      get: () => 1000,
      configurable: true
    })

    server.use(
      http.post('*/api/conversations/1/messages', () => {
        setTimeout(() => injectWsEvents(mockConversationId, [
          {
            event_type: 'message',
            text_content: 'AI response',
            role: 'agent',
            timestamp: new Date().toISOString()
          }
        ]), 0)
        return HttpResponse.json({ conversation_id: 1 })
      })
    )

    render(<ConversationChat conversationId={mockConversationId} />)

    await waitFor(() => {
      expect(screen.getByPlaceholderText(/ask a question/i)).toBeInTheDocument()
    })

    const input = screen.getByPlaceholderText(/ask a question/i)

    await user.type(input, 'New message')
    await user.click(screen.getByRole('button', { name: /send/i }))

    await waitFor(() => {
      expect(screen.getByText('AI response')).toBeInTheDocument()
    })

    // Should set scrollTop to scrollHeight to auto-scroll to bottom
    expect(mockScrollTop).toHaveBeenCalledWith(1000)
  })

  it('displays messages in chronological order', async () => {
    const messages = [
      {
        event_type: 'message',
        text_content: 'First message',
        role: 'user' as const,
        timestamp: '2024-01-01T10:00:00Z',
      },
      {
        event_type: 'message',
        text_content: 'Second message',
        role: 'agent' as const,
        timestamp: '2024-01-01T10:01:00Z',
      },
      {
        event_type: 'message',
        text_content: 'Third message',
        role: 'user' as const,
        timestamp: '2024-01-01T10:02:00Z',
      },
    ]

    server.use(
      http.get('*/api/conversations/1/messages', () => {
        return HttpResponse.json({ messages, context_usage: null })
      })
    )

    render(<ConversationChat conversationId={mockConversationId} />)

    await waitFor(() => {
      expect(screen.getByText('First message')).toBeInTheDocument()
    })

    const messageElements = screen.getAllByText(/message/)
    expect(messageElements[0]).toHaveTextContent('First message')
    expect(messageElements[1]).toHaveTextContent('Second message')
    expect(messageElements[2]).toHaveTextContent('Third message')
  })

  it('handles tool approval workflow for document editing', async () => {
    const user = userEvent.setup()

    server.use(
      http.post('*/api/conversations/1/messages', () => {
        setTimeout(() => injectWsEvents(mockConversationId, [
          {
            event_type: 'tool_call_request',
            tool_call_id: 'edit_123',
            tool_name: 'edit_project_specification',
            tool_args: {
              edits: [
                { find: 'old text', replace: 'new text' }
              ],
              reasoning: 'Updating project specification'
            }
          } as unknown as ConversationEvent
        ]), 0)
        return HttpResponse.json({ conversation_id: 1 })
      }),
      http.post('*/api/conversations/1/approve-tools', () => {
        setTimeout(() => injectWsEvents(mockConversationId, [
          {
            event_type: 'message',
            text_content: 'Successfully updated the project specification.',
            role: 'agent',
            timestamp: new Date().toISOString()
          }
        ]), 0)
        return HttpResponse.json({ conversation_id: 1 })
      })
    )

    render(<ConversationChat conversationId={mockConversationId} />)

    await waitFor(() => {
      expect(screen.getByPlaceholderText(/ask a question/i)).toBeInTheDocument()
    })

    const input = screen.getByPlaceholderText(/ask a question/i)
    const sendButton = screen.getByRole('button', { name: /send message/i })

    await user.type(input, 'Please update the project specification')
    await user.click(sendButton)

    // Should show pending approval
    await waitFor(() => {
      expect(screen.getByText(/Tool.*Awaiting Approval/i)).toBeInTheDocument()
      expect(screen.getByText('Updating project specification')).toBeInTheDocument()
    })

    // Input is always enabled (users can queue messages while waiting)
    expect(input).not.toBeDisabled()

    // Find and click approve button
    const approveButton = screen.getByRole('button', { name: /approve/i })
    await user.click(approveButton)

    // Should show success response
    await waitFor(() => {
      expect(screen.getByText('Successfully updated the project specification.')).toBeInTheDocument()
    })

    // Input should be enabled again (wait for pending message to be cleared)
    await waitFor(() => {
      expect(input).not.toBeDisabled()
    })
  })

  it('queues messages while tool approval is pending', async () => {
    const user = userEvent.setup()

    server.use(
      http.post('*/api/conversations/1/messages', () => {
        setTimeout(() => injectWsEvents(mockConversationId, [
          {
            event_type: 'tool_call_request',
            tool_call_id: 'edit_123',
            tool_name: 'edit_project_specification',
            tool_args: { edits: [], reasoning: 'Test' }
          } as unknown as ConversationEvent
        ]), 0)
        return HttpResponse.json({ conversation_id: 1 })
      })
    )

    render(<ConversationChat conversationId={mockConversationId} />)

    await waitFor(() => {
      expect(screen.getByPlaceholderText(/ask a question/i)).toBeInTheDocument()
    })

    const input = screen.getByPlaceholderText(/ask a question/i)

    await user.type(input, 'Test message')
    await user.click(screen.getByRole('button', { name: /send message/i }))

    // Wait for approval to appear
    await waitFor(() => {
      expect(screen.getByText(/Tool.*Awaiting Approval/i)).toBeInTheDocument()
    })

    // Input is always enabled (users can type and queue messages)
    expect(input).not.toBeDisabled()

    // Type a new message while approval is pending
    await user.type(input, 'Queued follow-up')
    await user.click(screen.getByRole('button', { name: /send message/i }))

    // Should show queued indicator
    await waitFor(() => {
      expect(screen.getByText(/queued/i)).toBeInTheDocument()
    })
  })

  it('handles empty chat history gracefully', async () => {
    server.use(
      http.get('*/api/conversations/1/messages', () => {
        return HttpResponse.json({ messages: [], context_usage: null })
      })
    )

    render(<ConversationChat conversationId={mockConversationId} />)

    await waitFor(() => {
      expect(screen.getByPlaceholderText(/ask a question/i)).toBeInTheDocument()
    })

    // Should show empty state
    expect(screen.getByText(/start a conversation/i)).toBeInTheDocument()
  })

  it('accepts custom placeholder and empty state message', async () => {
    server.use(
      http.get('*/api/conversations/1/messages', () => {
        return HttpResponse.json({ messages: [], context_usage: null })
      })
    )

    render(
      <ConversationChat
        conversationId={mockConversationId}
        placeholder="Custom placeholder text"
        emptyStateMessage="Custom empty state"
      />
    )

    await waitFor(() => {
      expect(screen.getByPlaceholderText(/custom placeholder text/i)).toBeInTheDocument()
    })

    expect(screen.getByText(/custom empty state/i)).toBeInTheDocument()
  })

  it('handles multiple messages without key collisions', async () => {
    const user = userEvent.setup()

    render(<ConversationChat conversationId={mockConversationId} />)

    await waitFor(() => {
      expect(screen.getByPlaceholderText(/ask a question/i)).toBeInTheDocument()
    })

    const input = screen.getByPlaceholderText(/ask a question/i)

    // Override handler for first message send
    server.use(
      http.post('*/api/conversations/1/messages', () => {
        setTimeout(() => injectWsEvents(mockConversationId, [
          {
            event_type: 'message',
            text_content: 'First AI response',
            role: 'agent',
            timestamp: new Date().toISOString()
          }
        ]), 0)
        return HttpResponse.json({ conversation_id: 1 })
      })
    )

    // Send first message
    await user.type(input, 'First message')
    await user.click(screen.getByRole('button', { name: /send/i }))

    // Wait for first AI response to appear
    await waitFor(() => {
      expect(screen.getByText('First AI response')).toBeInTheDocument()
    }, { timeout: 3000 })

    // Wait for input to be enabled again before sending second message
    await waitFor(() => {
      expect(input).not.toBeDisabled()
    }, { timeout: 3000 })

    // Override handler for second message send
    server.use(
      http.post('*/api/conversations/1/messages', () => {
        setTimeout(() => injectWsEvents(mockConversationId, [
          {
            event_type: 'message',
            text_content: 'Second AI response',
            role: 'agent',
            timestamp: new Date().toISOString()
          }
        ]), 0)
        return HttpResponse.json({ conversation_id: 1 })
      })
    )

    // Send second message - can only send after first completes
    await user.type(input, 'Second message')
    await user.click(screen.getByRole('button', { name: /send/i }))

    // Wait for second AI response to appear
    await waitFor(() => {
      expect(screen.getByText('Second AI response')).toBeInTheDocument()
    }, { timeout: 3000 })

    // Verify both AI responses are rendered (no duplicate key issues)
    expect(screen.getByText('First AI response')).toBeInTheDocument()
    expect(screen.getByText('Second AI response')).toBeInTheDocument()
  })

  it('converts pending message to confirmed message on first streamed event', async () => {
    const user = userEvent.setup()

    server.use(
      http.post('*/api/conversations/1/messages', () => {
        setTimeout(() => injectWsEvents(mockConversationId, [
          {
            event_type: 'message',
            text_content: 'AI response after first event',
            role: 'agent',
            timestamp: new Date().toISOString()
          }
        ]), 0)
        return HttpResponse.json({ conversation_id: 1 })
      })
    )

    render(<ConversationChat conversationId={mockConversationId} />)

    await waitFor(() => {
      expect(screen.getByPlaceholderText(/ask a question/i)).toBeInTheDocument()
    })

    const input = screen.getByPlaceholderText(/ask a question/i)
    const sendButton = screen.getByRole('button', { name: /send message/i })

    await user.type(input, 'Test message conversion')
    await user.click(sendButton)

    // Wait for the response and verify no duplicate pending messages
    await waitFor(() => {
      expect(screen.getByText('AI response after first event')).toBeInTheDocument()
    }, { timeout: 3000 })

    // Verify the user message appears exactly once (as confirmed message, not pending)
    const userMessages = screen.getAllByText('Test message conversion')
    expect(userMessages).toHaveLength(1)
  })

  it('does not show duplicate user message during streaming', async () => {
    const user = userEvent.setup()

    server.use(
      http.post('*/api/conversations/1/messages', () => {
        setTimeout(() => injectWsEvents(mockConversationId, [
          {
            event_type: 'message',
            text_content: 'Streaming response part 1',
            role: 'agent',
            timestamp: new Date().toISOString()
          },
          {
            event_type: 'message',
            text_content: 'Streaming response part 2',
            role: 'agent',
            timestamp: new Date().toISOString()
          }
        ]), 0)
        return HttpResponse.json({ conversation_id: 1 })
      })
    )

    render(<ConversationChat conversationId={mockConversationId} />)

    await waitFor(() => {
      expect(screen.getByPlaceholderText(/ask a question/i)).toBeInTheDocument()
    })

    const input = screen.getByPlaceholderText(/ask a question/i)
    const sendButton = screen.getByRole('button', { name: /send message/i })

    const messageText = 'User query for streaming test'
    await user.type(input, messageText)
    await user.click(sendButton)

    // Wait for all responses to appear
    await waitFor(() => {
      expect(screen.getByText('Streaming response part 2')).toBeInTheDocument()
    }, { timeout: 3000 })

    // Verify user message appears only once
    const userMessages = screen.queryAllByText(messageText)
    expect(userMessages).toHaveLength(1)
  })

  it('handles tool approval with pending message conversion', async () => {
    const user = userEvent.setup()

    server.use(
      http.post('*/api/conversations/1/messages', () => {
        setTimeout(() => injectWsEvents(mockConversationId, [
          {
            event_type: 'tool_call_request',
            tool_call_id: 'test_tool_1',
            tool_name: 'edit_document',
            tool_args: { content: 'new' }
          } as unknown as ConversationEvent
        ]), 0)
        return HttpResponse.json({ conversation_id: 1 })
      }),
      http.post('*/api/conversations/1/approve-tools', () => {
        setTimeout(() => injectWsEvents(mockConversationId, [
          {
            event_type: 'message',
            text_content: 'Tool execution complete',
            role: 'agent',
            timestamp: new Date().toISOString()
          }
        ]), 0)
        return HttpResponse.json({ conversation_id: 1 })
      })
    )

    render(<ConversationChat conversationId={mockConversationId} />)

    await waitFor(() => {
      expect(screen.getByPlaceholderText(/ask a question/i)).toBeInTheDocument()
    })

    const input = screen.getByPlaceholderText(/ask a question/i)
    const sendButton = screen.getByRole('button', { name: /send message/i })

    await user.type(input, 'Please edit the document')
    await user.click(sendButton)

    // Wait for tool approval to appear
    await waitFor(() => {
      expect(screen.getByText(/Tool.*Awaiting Approval/i)).toBeInTheDocument()
    })

    // Click approve button
    const approveButton = screen.getByRole('button', { name: /approve/i })
    await user.click(approveButton)

    // Wait for approval response
    await waitFor(() => {
      expect(screen.getByText('Tool execution complete')).toBeInTheDocument()
    }, { timeout: 3000 })

    // Verify the input is enabled again (pending message has been cleared)
    const finalInput = screen.getByPlaceholderText(/ask a question/i)
    expect(finalInput).not.toBeDisabled()

    // Verify the tool execution message is displayed
    expect(screen.getByText('Tool execution complete')).toBeInTheDocument()
  })

  it('passes event handler registry and invokes SystemEvent handlers', async () => {
    const user = userEvent.setup()

    server.use(
      http.post('*/api/conversations/1/messages', () => {
        setTimeout(() => injectWsEvents(mockConversationId, [
          {
            event_type: 'system',
            type: 'task_updated',
            data: {
              task_id: 123,
              updated_fields: {
                status: 'planning',
                conversation_id: 1,
                implementation_plan_id: 456
              }
            },
            timestamp: new Date().toISOString()
          } as unknown as ConversationEvent,
          {
            event_type: 'message',
            text_content: 'Task has been updated',
            role: 'agent',
            timestamp: new Date().toISOString()
          }
        ]), 0)
        return HttpResponse.json({ conversation_id: 1 })
      })
    )

    render(<ConversationChat conversationId={mockConversationId} />)

    await waitFor(() => {
      expect(screen.getByPlaceholderText(/ask a question/i)).toBeInTheDocument()
    })

    const input = screen.getByPlaceholderText(/ask a question/i)
    const sendButton = screen.getByRole('button', { name: /send message/i })

    await user.type(input, 'Update the task status')
    await user.click(sendButton)

    // Wait for agent response (SystemEvent should be handled in background)
    await waitFor(() => {
      expect(screen.getByText('Task has been updated')).toBeInTheDocument()
    }, { timeout: 3000 })

    // Verify system event did not appear as a message in chat (should be filtered)
    expect(screen.queryByText(/task_updated/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/implementation_plan_id/i)).not.toBeInTheDocument()
  })
})
