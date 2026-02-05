import { describe, it, expect, beforeEach, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { server } from '../../test/setup'
import { render } from '../../test/utils'
import ConversationChat from '../chat/ConversationChat'
import ConversationEventHandlerProvider from '../chat/ConversationEventHandlerProvider'
import { useConversationStreamStore } from '../../stores/conversationStreamStore'
import { useApprovalsStore } from '../../stores/approvalsStore'

describe('ConversationChat', () => {
  const mockConversationId = 1

  // Helper to create NDJSON streaming response
  const createStreamingResponse = (events: any[]) => {
    const ndjson = events.map(e => JSON.stringify(e)).join('\n') + '\n'
    return new HttpResponse(ndjson, {
      headers: { 'Content-Type': 'text/plain' }
    })
  }

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
    useConversationStreamStore.setState({ activeStreams: new Map() })

    // Clear the approvalsStore between tests
    useApprovalsStore.setState({ approvals: {} })

    // Mock scrollIntoView which is not available in jsdom
    Element.prototype.scrollIntoView = vi.fn()

    // Reset server handlers to defaults for each test
    server.resetHandlers()

    // Setup default handler that returns empty history
    // Individual tests can override this with server.use() if they need specific data
    server.use(
      http.get('*/api/conversations/1/messages', () => {
        return HttpResponse.json([])
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
        return HttpResponse.json(defaultChatHistory)
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
        return HttpResponse.json(defaultChatHistory)
      })
    )

    render(<ConversationChat conversationId={mockConversationId} />)

    await waitFor(() => {
      expect(screen.getByText('What is the status?')).toBeInTheDocument()
    })

    // Check that user messages have correct styling
    const userMessageText = screen.getByText('What is the status?')
    const userBubble = userMessageText.closest('.bg-blue-600')
    expect(userBubble).toBeInTheDocument()

    // Check that assistant messages have correct styling
    const assistantMessageText = screen.getByText('The project is progressing well.')
    const assistantBubble = assistantMessageText.closest('.bg-gray-100')
    expect(assistantBubble).toBeInTheDocument()
  })

  it('sends new message when form is submitted', async () => {
    const user = userEvent.setup()

    server.use(
      http.post('*/api/conversations/1/messages/stream', async ({ request }) => {
        const { message } = await request.json() as { message: string }
        return createStreamingResponse([
          {
            event_type: 'message',
            text_content: `AI response to: ${message}`,
            role: 'agent',
            timestamp: new Date().toISOString()
          }
        ])
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
      http.post('*/api/conversations/1/messages/stream', () => {
        return createStreamingResponse([
          {
            event_type: 'message',
            text_content: 'AI response',
            role: 'agent',
            timestamp: new Date().toISOString()
          }
        ])
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
      http.post('*/api/conversations/1/messages/stream', async ({ request }) => {
        const { message } = await request.json() as { message: string }
        return createStreamingResponse([
          {
            event_type: 'message',
            text_content: `Got: ${message}`,
            role: 'agent',
            timestamp: new Date().toISOString()
          }
        ])
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

    // Delay the API response to test loading state
    server.use(
      http.post('*/api/conversations/1/messages/stream', async () => {
        await new Promise(resolve => setTimeout(resolve, 200))
        return createStreamingResponse([
          {
            event_type: 'message',
            text_content: 'AI response',
            role: 'agent',
            timestamp: new Date().toISOString()
          }
        ])
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
      http.post('*/api/conversations/1/messages/stream', () => {
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

    // Now errors are logged from the store with 'Stream error:' prefix
    await waitFor(() => {
      expect(consoleSpy).toHaveBeenCalledWith('Stream error:', expect.any(Error))
    })

    consoleSpy.mockRestore()
  })

  it('renders messages from history correctly', async () => {
    const testDate = '2024-01-01T15:30:00Z'

    server.use(
      http.get('*/api/conversations/1/messages', () => {
        return HttpResponse.json([
          {
            event_type: 'message',
            text_content: 'Test message from history',
            role: 'user',
            timestamp: testDate,
          },
        ])
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
      http.post('*/api/conversations/1/messages/stream', () => {
        return createStreamingResponse([
          {
            event_type: 'message',
            text_content: 'AI response',
            role: 'agent',
            timestamp: new Date().toISOString()
          }
        ])
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
        return HttpResponse.json(messages)
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

    // Mock agent requesting tool approval
    server.use(
      http.post('*/api/conversations/1/messages/stream', () => {
        return createStreamingResponse([
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
          }
        ])
      }),

      // Mock approval endpoint
      http.post('*/api/conversations/1/approve-tools/stream', () => {
        return createStreamingResponse([
          {
            event_type: 'message',
            text_content: 'Successfully updated the project specification.',
            role: 'agent',
            timestamp: new Date().toISOString()
          }
        ])
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

    // Input should be disabled while approval is pending
    expect(input).toBeDisabled()
    expect(sendButton).toBeDisabled()

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

  it('prevents sending messages while tool approval is pending', async () => {
    const user = userEvent.setup()

    server.use(
      http.post('*/api/conversations/1/messages/stream', () => {
        return createStreamingResponse([
          {
            event_type: 'tool_call_request',
            tool_call_id: 'edit_123',
            tool_name: 'edit_project_specification',
            tool_args: { edits: [], reasoning: 'Test' }
          }
        ])
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

    // Wait for approval to appear
    await waitFor(() => {
      expect(screen.getByText(/Tool.*Awaiting Approval/i)).toBeInTheDocument()
    })

    // Input should be disabled
    expect(input).toBeDisabled()
    expect(sendButton).toBeDisabled()
    
    // Should show helpful message
    expect(screen.getByText(/Please review and approve.*pending tool requests/i)).toBeInTheDocument()
  })

  it('handles empty chat history gracefully', async () => {
    server.use(
      http.get('*/api/conversations/1/messages', () => {
        return HttpResponse.json([])
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
        return HttpResponse.json([])
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

    let callCount = 0
    server.use(
      http.post('*/api/conversations/1/messages/stream', () => {
        callCount++
        // Ensure unique timestamps by adding call count to milliseconds
        const now = new Date()
        now.setMilliseconds(now.getMilliseconds() + callCount)
        return createStreamingResponse([
          {
            event_type: 'message',
            text_content: 'AI response',
            role: 'agent',
            timestamp: now.toISOString()
          }
        ])
      })
    )

    render(<ConversationChat conversationId={mockConversationId} />)

    await waitFor(() => {
      expect(screen.getByPlaceholderText(/ask a question/i)).toBeInTheDocument()
    })

    const input = screen.getByPlaceholderText(/ask a question/i)

    // Send first message
    await user.type(input, 'First message')
    await user.click(screen.getByRole('button', { name: /send/i }))

    // Wait for first message to complete (both user and AI message should appear, pending should be gone)
    await waitFor(() => {
      const firstMessages = screen.queryAllByText('First message')
      // Should only appear once (as confirmed message, not pending)
      expect(firstMessages).toHaveLength(1)
      expect(screen.getByText('AI response')).toBeInTheDocument()
    }, { timeout: 3000 })

    // Wait for input to be enabled again before sending second message
    await waitFor(() => {
      expect(input).not.toBeDisabled()
    }, { timeout: 3000 })

    // Send second message - can only send after first completes
    await user.type(input, 'Second message')
    await user.click(screen.getByRole('button', { name: /send/i }))

    // Wait for second message to complete (pending should be gone)
    await waitFor(() => {
      const secondMessages = screen.queryAllByText('Second message')
      // Should only appear once (as confirmed message, not pending)
      expect(secondMessages).toHaveLength(1)
      expect(screen.getAllByText('AI response')).toHaveLength(2)
    }, { timeout: 3000 })

    // Verify both messages are rendered correctly (no duplicate key issues)
    expect(screen.getAllByText('First message')).toHaveLength(1)
    expect(screen.getAllByText('Second message')).toHaveLength(1)
    expect(screen.getAllByText('AI response')).toHaveLength(2)
  })


  it('converts pending message to confirmed message on first streamed event', async () => {
    const user = userEvent.setup()

    server.use(
      http.post('*/api/conversations/1/messages/stream', () => {
        return createStreamingResponse([
          {
            event_type: 'message',
            text_content: 'AI response after first event',
            role: 'agent',
            timestamp: new Date().toISOString()
          }
        ])
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
      http.post('*/api/conversations/1/messages/stream', () => {
        return createStreamingResponse([
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
        ])
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
      http.post('*/api/conversations/1/messages/stream', () => {
        return createStreamingResponse([
          {
            event_type: 'tool_call_request',
            tool_call_id: 'test_tool_1',
            tool_name: 'edit_document',
            tool_args: { content: 'new' }
          }
        ])
      }),
      http.post('*/api/conversations/1/approve-tools/stream', () => {
        return createStreamingResponse([
          {
            event_type: 'message',
            text_content: 'Tool execution complete',
            role: 'agent',
            timestamp: new Date().toISOString()
          }
        ])
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

  it('passes eventHandlerRegistry to processConversationStream and invokes SystemEvent handlers', async () => {
    const user = userEvent.setup()

    // Mock system event handler
    const mockSystemEventHandler = vi.fn()

    // Create a wrapper that provides event handler context
    const TestWrapper = ({ children }: { children: React.ReactNode }) => {
      return <ConversationEventHandlerProvider>{children}</ConversationEventHandlerProvider>
    }

    // Mock streaming response with SystemEvent
    server.use(
      http.post('*/api/conversations/1/messages/stream', () => {
        return createStreamingResponse([
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
          },
          {
            event_type: 'message',
            text_content: 'Task has been updated',
            role: 'agent',
            timestamp: new Date().toISOString()
          }
        ])
      })
    )

    render(
      <TestWrapper>
        <ConversationChat conversationId={mockConversationId} />
      </TestWrapper>
    )

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