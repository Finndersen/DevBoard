import { describe, it, expect, beforeEach, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { server } from '../../test/setup'
import { render } from '../../test/utils'
import ConversationChat from '../ConversationChat'

describe('ConversationChat', () => {
  const mockConversationId = 1

  beforeEach(() => {
    vi.clearAllMocks()
    
    // Mock scrollIntoView which is not available in jsdom
    Element.prototype.scrollIntoView = vi.fn()
    
    // Setup default API responses for conversation API
    server.use(
      http.get('*/api/conversations/1/messages', () => {
        return HttpResponse.json([
          {
            id: 1,
            text_content: 'What is the status?',
            role: 'user',
            timestamp: '2024-01-01T10:00:00Z',
          },
          {
            id: 2,
            text_content: 'The project is progressing well.',
            role: 'agent',
            timestamp: '2024-01-01T10:01:00Z',
          },
        ])
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
    render(<ConversationChat conversationId={mockConversationId} />)

    await waitFor(() => {
      expect(screen.getByText('What is the status?')).toBeInTheDocument()
      expect(screen.getByText('The project is progressing well.')).toBeInTheDocument()
    })
  })

  it('displays messages with correct user/assistant styling', async () => {
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
      http.post('*/api/conversations/1/messages', async ({ request }) => {
        const { message } = await request.json() as { message: string }
        return HttpResponse.json({
          type: 'message',
          message: {
            id: 3,
            text_content: `AI response to: ${message}`,
            role: 'agent',
            timestamp: new Date().toISOString()
          },
          tool_requests: null
        })
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

    // Should show user message immediately
    await waitFor(() => {
      expect(screen.getByText('New question')).toBeInTheDocument()
    })

    // Should show AI response after API call
    await waitFor(() => {
      expect(screen.getByText('AI response to: New question')).toBeInTheDocument()
    })

    // Input should be cleared
    expect(input).toHaveValue('')
  })

  it('sends message on Enter key press', async () => {
    const user = userEvent.setup()
    
    server.use(
      http.post('*/api/conversations/1/messages', () => {
        return HttpResponse.json({
          type: 'message',
          message: {
            id: 3,
            text_content: 'AI response',
            role: 'agent',
            timestamp: new Date().toISOString()
          },
          tool_requests: null
        })
      })
    )

    render(<ConversationChat conversationId={mockConversationId} />)

    await waitFor(() => {
      expect(screen.getByPlaceholderText(/ask a question/i)).toBeInTheDocument()
    })

    const input = screen.getByPlaceholderText(/ask a question/i)

    await user.type(input, 'Test message{enter}')

    await waitFor(() => {
      expect(screen.getByText('Test message')).toBeInTheDocument()
    })
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

    // Should still only have the original 2 messages from setup
    expect(screen.getByText('What is the status?')).toBeInTheDocument()
    expect(screen.getByText('The project is progressing well.')).toBeInTheDocument()
  })

  it('shows loading state while sending message', async () => {
    const user = userEvent.setup()
    
    // Delay the API response to test loading state
    server.use(
      http.post('*/api/conversations/1/messages', async () => {
        await new Promise(resolve => setTimeout(resolve, 200))
        return HttpResponse.json({
          type: 'message',
          message: {
            id: 3,
            text_content: 'AI response',
            role: 'agent',
            timestamp: new Date().toISOString()
          },
          tool_requests: null
        })
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

    // Send button should be disabled during loading (empty input after submit)
    expect(sendButton).toBeDisabled()

    // Wait for response and button to be enabled again
    await waitFor(() => {
      expect(screen.getByText('AI response')).toBeInTheDocument()
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

    await waitFor(() => {
      expect(consoleSpy).toHaveBeenCalledWith('Failed to send message:', expect.any(Error))
    })

    consoleSpy.mockRestore()
  })

  it('formats timestamps correctly', async () => {
    const testDate = '2024-01-01T15:30:00Z'
    
    server.use(
      http.get('*/api/conversations/1/messages', () => {
        return HttpResponse.json([
          {
            id: 1,
            text_content: 'Test message',
            role: 'user',
            timestamp: testDate,
          },
        ])
      })
    )

    render(<ConversationChat conversationId={mockConversationId} />)

    await waitFor(() => {
      expect(screen.getByText('Test message')).toBeInTheDocument()
    })

    // Should format time (exact format may vary based on locale)
    const timeElement = screen.getByText(/\d{1,2}:\d{2}/)
    expect(timeElement).toBeInTheDocument()
  })

  it('auto-scrolls to bottom when new messages are added', async () => {
    const user = userEvent.setup()
    const scrollSpy = vi.spyOn(Element.prototype, 'scrollIntoView')
    
    server.use(
      http.post('*/api/conversations/1/messages', () => {
        return HttpResponse.json({
          type: 'message',
          message: {
            id: 3,
            text_content: 'AI response',
            role: 'agent',
            timestamp: new Date().toISOString()
          },
          tool_requests: null
        })
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

    // Should call scrollIntoView to auto-scroll
    expect(scrollSpy).toHaveBeenCalled()

    scrollSpy.mockRestore()
  })

  it('displays messages in chronological order', async () => {
    const messages = [
      {
        id: 1,
        text_content: 'First message',
        role: 'user' as const,
        timestamp: '2024-01-01T10:00:00Z',
      },
      {
        id: 2,
        text_content: 'Second message',
        role: 'agent' as const,
        timestamp: '2024-01-01T10:01:00Z',
      },
      {
        id: 3,
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
      http.post('*/api/conversations/1/messages', () => {
        return HttpResponse.json({
          type: 'tool_request',
          message: null,
          tool_requests: [{
            tool_call_id: 'edit_123',
            tool_name: 'edit_project_specification',
            tool_args: {
              edits: [
                { find: 'old text', replace: 'new text' }
              ],
              reasoning: 'Updating project specification'
            }
          }]
        })
      }),
      
      // Mock approval endpoint
      http.post('*/api/conversations/1/approve-tools', () => {
        return HttpResponse.json({
          type: 'message',
          message: {
            id: 4,
            text_content: 'Successfully updated the project specification.',
            role: 'agent',
            timestamp: new Date().toISOString()
          },
          tool_requests: null
        })
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
      expect(screen.getByText('old text')).toBeInTheDocument()
      expect(screen.getByText('new text')).toBeInTheDocument()
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

    // Input should be enabled again
    expect(input).not.toBeDisabled()
  })

  it('prevents sending messages while tool approval is pending', async () => {
    const user = userEvent.setup()
    
    server.use(
      http.post('*/api/conversations/1/messages', () => {
        return HttpResponse.json({
          type: 'tool_request',
          message: null,
          tool_requests: [{
            tool_call_id: 'edit_123',
            tool_name: 'edit_project_specification',
            tool_args: { edits: [], reasoning: 'Test' }
          }]
        })
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

  it('generates unique message IDs for new messages', async () => {
    const user = userEvent.setup()
    
    server.use(
      http.post('*/api/conversations/1/messages', () => {
        return HttpResponse.json({
          type: 'message',
          message: {
            id: Date.now(),
            text_content: 'AI response',
            role: 'agent',
            timestamp: new Date().toISOString()
          },
          tool_requests: null
        })
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

    await waitFor(() => {
      expect(screen.getByText('AI response')).toBeInTheDocument()
    })

    // Send second message
    await user.type(input, 'Second message')
    await user.click(screen.getByRole('button', { name: /send/i }))

    await waitFor(() => {
      expect(screen.getAllByText('AI response')).toHaveLength(2)
    })

    // All messages should be rendered (no duplicate key issues)
    expect(screen.getByText('First message')).toBeInTheDocument()
    expect(screen.getByText('Second message')).toBeInTheDocument()
  })
})