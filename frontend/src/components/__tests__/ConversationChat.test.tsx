import { describe, it, expect, beforeEach, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { enableMapSet } from 'immer'
import { http, HttpResponse } from 'msw'
import { server } from '../../test/setup'
import { render } from '../../test/utils'
import ConversationChat, { type ConversationChatHandle } from '../chat/ConversationChat'
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

  it('renders chat interface with messages area', async () => {
    render(<ConversationChat conversationId={mockConversationId} />)

    await waitFor(() => {
      expect(screen.getByText(/start a conversation/i)).toBeInTheDocument()
    })
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

  it('exposes input state and methods via ref handle', async () => {
    const ref = { current: null as ConversationChatHandle | null }

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

    render(<ConversationChat ref={ref} conversationId={mockConversationId} />)

    await waitFor(() => {
      expect(ref.current).toBeTruthy()
    })

    // Test that ref exposes the expected interface
    expect(ref.current.inputMessage).toBe('')
    expect(typeof ref.current.setInputMessage).toBe('function')
    expect(typeof ref.current.handleSendMessage).toBe('function')
    expect(typeof ref.current.sendMessage).toBe('function')
    expect(typeof ref.current.isQueued).toBe('boolean')
    expect(typeof ref.current.stopStream).toBe('function')

    // Test setting input message
    ref.current.setInputMessage('Test message')

    await waitFor(() => {
      expect(ref.current.inputMessage).toBe('Test message')
    })

    // Test sending message via ref
    ref.current.handleSendMessage()

    // Check that the message appears
    await waitFor(() => {
      expect(screen.getByText('AI response to: New question')).toBeInTheDocument()
    }, { timeout: 3000 })
  })

  it('sends message via ref sendMessage method', async () => {
    const ref = { current: null as ConversationChatHandle | null }

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

    render(<ConversationChat ref={ref} conversationId={mockConversationId} />)

    await waitFor(() => {
      expect(ref.current).toBeTruthy()
    })

    ref.current.sendMessage('Test message')

    await waitFor(() => {
      const messages = screen.getAllByText(/Test message|AI response/)
      expect(messages.length).toBeGreaterThan(0)
    })
  })

  it('handles multi-line messages via ref interface', async () => {
    const ref = { current: null as ConversationChatHandle | null }

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

    render(<ConversationChat ref={ref} conversationId={mockConversationId} />)

    await waitFor(() => {
      expect(ref.current).toBeTruthy()
    })

    // Set multi-line message via ref
    const multilineMessage = 'Line 1\nLine 2\nLine 3'
    ref.current.setInputMessage(multilineMessage)

    await waitFor(() => {
      expect(ref.current.inputMessage).toBe(multilineMessage)
    })

    // Send message via ref
    ref.current.handleSendMessage()

    // Should clear the input after sending
    await waitFor(() => {
      expect(ref.current.inputMessage).toBe('')
    })

    // Should receive response
    await waitFor(() => {
      expect(screen.getByText(/Got: Line 1.*Line 2.*Line 3/s)).toBeInTheDocument()
    }, { timeout: 3000 })
  })

  it('prevents sending empty messages via ref', async () => {
    const ref = { current: null as ConversationChatHandle | null }

    render(<ConversationChat ref={ref} conversationId={mockConversationId} />)

    await waitFor(() => {
      expect(ref.current).toBeTruthy()
    })

    // Get initial message count
    await waitFor(() => {
      expect(screen.getByText(/start a conversation/i)).toBeInTheDocument()
    })

    const initialContent = screen.getByText(/start a conversation/i)
    expect(initialContent).toBeInTheDocument()

    // Try to send empty message via ref
    ref.current.sendMessage('')
    ref.current.sendMessage('   ') // whitespace only

    // Empty state should still be shown (no new messages)
    expect(screen.getByText(/start a conversation/i)).toBeInTheDocument()
  })

  it('exposes streaming state via ref handle', async () => {
    const ref = { current: null as ConversationChatHandle | null }

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

    render(<ConversationChat ref={ref} conversationId={mockConversationId} />)

    await waitFor(() => {
      expect(ref.current).toBeTruthy()
    })

    // Send message via ref
    ref.current.sendMessage('Test message')

    // Should show user message immediately
    await waitFor(() => {
      const messages = screen.getAllByText(/Test message|AI response/)
      expect(messages.length).toBeGreaterThan(0)
    })

    // Wait for response
    await waitFor(() => {
      expect(screen.getByText('AI response')).toBeInTheDocument()
    }, { timeout: 3000 })

    // Test stopStream method is available
    expect(typeof ref.current.stopStream).toBe('function')
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

  it('handles API error when sending message via ref', async () => {
    const ref = { current: null as ConversationChatHandle | null }
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})

    server.use(
      http.post('*/api/conversations/1/messages', () => {
        return new HttpResponse(null, { status: 500 })
      })
    )

    render(<ConversationChat ref={ref} conversationId={mockConversationId} />)

    await waitFor(() => {
      expect(ref.current).toBeTruthy()
    })

    ref.current.sendMessage('Test message')

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

  it('auto-scrolls to bottom when new messages are added via ref', async () => {
    const ref = { current: null as ConversationChatHandle | null }

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

    render(<ConversationChat ref={ref} conversationId={mockConversationId} />)

    await waitFor(() => {
      expect(ref.current).toBeTruthy()
    })

    ref.current.sendMessage('New message')

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

  it('handles tool approval workflow for document editing via ref', async () => {
    const ref = { current: null as ConversationChatHandle | null }
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

    render(<ConversationChat ref={ref} conversationId={mockConversationId} />)

    await waitFor(() => {
      expect(ref.current).toBeTruthy()
    })

    ref.current.sendMessage('Please update the project specification')

    // Should show pending approval
    await waitFor(() => {
      expect(screen.getByText(/Tool.*Awaiting Approval/i)).toBeInTheDocument()
      expect(screen.getByText('Updating project specification')).toBeInTheDocument()
    })

    // Find and click approve button
    const approveButton = screen.getByRole('button', { name: /approve/i })
    await user.click(approveButton)

    // Should show success response
    await waitFor(() => {
      expect(screen.getByText('Successfully updated the project specification.')).toBeInTheDocument()
    })
  })

  it('queues messages while tool approval is pending via ref', async () => {
    const ref = { current: null as ConversationChatHandle | null }

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

    render(<ConversationChat ref={ref} conversationId={mockConversationId} />)

    await waitFor(() => {
      expect(ref.current).toBeTruthy()
    })

    ref.current.sendMessage('Test message')

    // Wait for approval to appear
    await waitFor(() => {
      expect(screen.getByText(/Tool.*Awaiting Approval/i)).toBeInTheDocument()
    })

    // Send a follow-up message while approval is pending
    ref.current.sendMessage('Queued follow-up')

    // The queued text is held in the internal ref; verify via isQueued store flag
    await waitFor(() => {
      const streamState = useConversationStreamStore.getState().activeStreams.get(mockConversationId)
      expect(streamState?.isQueued).toBe(true)
    })

    // Verify that the message was queued rather than sent immediately
    // (the message should be in the input field, not displayed as a new message)
    const messages = screen.queryAllByText(/Queued follow-up/)
    expect(messages).toHaveLength(0) // Message should not appear as sent
  })

  it('handles empty chat history gracefully', async () => {
    server.use(
      http.get('*/api/conversations/1/messages', () => {
        return HttpResponse.json({ messages: [], context_usage: null })
      })
    )

    render(<ConversationChat conversationId={mockConversationId} />)

    await waitFor(() => {
      expect(screen.getByText(/start a conversation/i)).toBeInTheDocument()
    })
  })

  it('accepts custom empty state message', async () => {
    server.use(
      http.get('*/api/conversations/1/messages', () => {
        return HttpResponse.json({ messages: [], context_usage: null })
      })
    )

    render(
      <ConversationChat
        conversationId={mockConversationId}
        emptyStateMessage="Custom empty state"
      />
    )

    await waitFor(() => {
      expect(screen.getByText(/custom empty state/i)).toBeInTheDocument()
    })
  })

  it('handles multiple messages without key collisions via ref', async () => {
    const ref = { current: null as ConversationChatHandle | null }

    render(<ConversationChat ref={ref} conversationId={mockConversationId} />)

    await waitFor(() => {
      expect(ref.current).toBeTruthy()
    })

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
    ref.current.sendMessage('First message')

    // Wait for first AI response to appear
    await waitFor(() => {
      expect(screen.getByText('First AI response')).toBeInTheDocument()
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

    // Send second message
    ref.current.sendMessage('Second message')

    // Wait for second AI response to appear
    await waitFor(() => {
      expect(screen.getByText('Second AI response')).toBeInTheDocument()
    }, { timeout: 3000 })

    // Verify both AI responses are rendered (no duplicate key issues)
    expect(screen.getByText('First AI response')).toBeInTheDocument()
    expect(screen.getByText('Second AI response')).toBeInTheDocument()
  })

  it('converts pending message to confirmed message on first streamed event via ref', async () => {
    const ref = { current: null as ConversationChatHandle | null }

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

    render(<ConversationChat ref={ref} conversationId={mockConversationId} />)

    await waitFor(() => {
      expect(ref.current).toBeTruthy()
    })

    ref.current.sendMessage('Test message conversion')

    // Wait for the response and verify no duplicate pending messages
    await waitFor(() => {
      expect(screen.getByText('AI response after first event')).toBeInTheDocument()
    }, { timeout: 3000 })

    // Verify the user message appears exactly once (as confirmed message, not pending)
    const userMessages = screen.getAllByText('Test message conversion')
    expect(userMessages).toHaveLength(1)
  })

  it('does not show duplicate user message during streaming via ref', async () => {
    const ref = { current: null as ConversationChatHandle | null }

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

    render(<ConversationChat ref={ref} conversationId={mockConversationId} />)

    await waitFor(() => {
      expect(ref.current).toBeTruthy()
    })

    const messageText = 'User query for streaming test'
    ref.current.sendMessage(messageText)

    // Wait for all responses to appear
    await waitFor(() => {
      expect(screen.getByText('Streaming response part 2')).toBeInTheDocument()
    }, { timeout: 3000 })

    // Verify user message appears only once
    const userMessages = screen.queryAllByText(messageText)
    expect(userMessages).toHaveLength(1)
  })

  it('handles tool approval with pending message conversion via ref', async () => {
    const ref = { current: null as ConversationChatHandle | null }
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

    render(<ConversationChat ref={ref} conversationId={mockConversationId} />)

    await waitFor(() => {
      expect(ref.current).toBeTruthy()
    })

    ref.current.sendMessage('Please edit the document')

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

    // Verify the tool execution message is displayed
    expect(screen.getByText('Tool execution complete')).toBeInTheDocument()
  })

  it('passes event handler registry and invokes SystemEvent handlers via ref', async () => {
    const ref = { current: null as ConversationChatHandle | null }

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

    render(<ConversationChat ref={ref} conversationId={mockConversationId} />)

    await waitFor(() => {
      expect(ref.current).toBeTruthy()
    })

    ref.current.sendMessage('Update the task status')

    // Wait for agent response (SystemEvent should be handled in background)
    await waitFor(() => {
      expect(screen.getByText('Task has been updated')).toBeInTheDocument()
    }, { timeout: 3000 })

    // Verify system event did not appear as a message in chat (should be filtered)
    expect(screen.queryByText(/task_updated/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/implementation_plan_id/i)).not.toBeInTheDocument()
  })
})
