import { describe, it, expect, beforeEach, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { server } from '../../../test/setup'
import { render } from '../../../test/utils'
import AgentChat from '../AgentChat'
import * as approvalsStore from '../../../stores/approvalsStore'

// Mock the approvals store to verify clearApprovals is called
vi.mock('../../../stores/approvalsStore', () => ({
  useApprovalActions: vi.fn(),
  useApprovals: vi.fn(() => [])
}))

vi.mock('../../../contexts/ViewContext', () => ({
  useViewContext: () => ({ viewId: 'test-view', viewType: 'task', entityId: '1' })
}))

describe('AgentChat', () => {
  const mockConversationId = 1
  const mockClearApprovals = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()

    // Clear localStorage
    localStorage.clear()

    // Mock scrollIntoView
    Element.prototype.scrollIntoView = vi.fn()

    // Mock window.location.reload for jsdom
    delete (window as { location?: unknown }).location
    // @ts-ignore - mock location for testing
    window.location = { reload: vi.fn() }

    // Reset server handlers
    server.resetHandlers()

    // Mock useApprovalActions hook
    vi.mocked(approvalsStore.useApprovalActions).mockReturnValue({
      setApprovals: vi.fn(),
      addApproval: vi.fn(),
      removeApproval: vi.fn(),
      clearApprovals: mockClearApprovals,
      getApprovals: vi.fn(() => []),
      hasApprovals: vi.fn(() => false),
      processApprovalDecision: vi.fn()
    })

    // Setup default API responses
    server.use(
      http.get('*/api/conversations/1', () => {
        return HttpResponse.json({
          id: 1,
          agent_role: 'qa',
          engine: 'anthropic_claude',
          model_id: 'anthropic:claude-3-5-sonnet-20241022',
          external_session_id: 'test-session-123',
          created_at: '2024-01-01T00:00:00Z',
          updated_at: '2024-01-01T00:00:00Z'
        })
      }),
      http.get('*/api/models/by-engine', () => {
        return HttpResponse.json({
          models_by_engine: {
            anthropic_claude: [
              {
                id: 'anthropic:claude-3-5-sonnet-20241022',
                name: 'Claude 3.5 Sonnet',
                provider: 'anthropic',
                model_type: 'chat'
              }
            ]
          }
        })
      }),
      http.get('*/api/conversations/1/messages', () => {
        return HttpResponse.json([
          {
            event_type: 'message',
            text_content: 'Test message',
            role: 'user',
            timestamp: '2024-01-01T10:00:00Z'
          }
        ])
      }),
      http.post('*/api/conversations/1/reset', () => {
        return HttpResponse.json({ new_conversation_id: 2, message: 'Conversation reset successfully.' })
      })
    )
  })

  it('renders agent chat interface', async () => {
    render(<AgentChat conversationId={mockConversationId} />)

    await waitFor(() => {
      expect(screen.getByText('Qa Agent')).toBeInTheDocument()
    })

    expect(screen.getByPlaceholderText(/ask a question/i)).toBeInTheDocument()
  })

  it('clears pending tool approvals when clearing chat history', async () => {
    const user = userEvent.setup()

    // Mock approval state with clearApprovals
    vi.mocked(approvalsStore.useApprovalActions).mockReturnValue({
      setApprovals: vi.fn(),
      addApproval: vi.fn(),
      removeApproval: vi.fn(),
      clearApprovals: mockClearApprovals,
      getApprovals: vi.fn(() => [
        {
          tool_call_id: 'edit_123',
          tool_name: 'edit_project_specification',
          tool_args: { edits: [] },
          conversationId: 1
        }
      ]),
      hasApprovals: vi.fn(() => true),
      processApprovalDecision: vi.fn()
    })

    render(<AgentChat conversationId={mockConversationId} />)

    await waitFor(() => {
      expect(screen.getByText('Qa Agent')).toBeInTheDocument()
    })

    // Find and click the clear chat button
    const clearButton = screen.getByTitle('Clear Chat History')
    await user.click(clearButton)

    // Confirm in the modal
    await waitFor(() => {
      expect(screen.getByText(/are you sure/i)).toBeInTheDocument()
    })

    const confirmButton = screen.getByRole('button', { name: /clear history/i })
    await user.click(confirmButton)

    // Verify clearApprovals was called with the correct key
    await waitFor(() => {
      expect(mockClearApprovals).toHaveBeenCalledWith('conversation-1')
    })
  })

  it('displays session ID when available', async () => {
    render(<AgentChat conversationId={mockConversationId} />)

    await waitFor(() => {
      expect(screen.getByText('Qa Agent')).toBeInTheDocument()
    })

    // Should show info button
    const infoButton = screen.getByTitle('View session ID')
    expect(infoButton).toBeInTheDocument()
  })

  it('shows model selector when conversation is loaded', async () => {
    render(<AgentChat conversationId={mockConversationId} />)

    await waitFor(() => {
      expect(screen.getByText('Qa Agent')).toBeInTheDocument()
    })

    // Wait for model selector to finish loading
    await waitFor(() => {
      expect(screen.queryByText(/loading/i)).not.toBeInTheDocument()
    })

    // Should show model information
    expect(screen.getByText('Anthropic Claude')).toBeInTheDocument()
  })

  it('handles null conversationId gracefully', () => {
    render(<AgentChat conversationId={null} />)

    expect(screen.getByText(/no conversation started yet/i)).toBeInTheDocument()
  })

  it('formats agent role display name correctly', async () => {
    server.use(
      http.get('*/api/conversations/1', () => {
        return HttpResponse.json({
          id: 1,
          agent_role: 'investigation',
          engine: 'anthropic_claude',
          model_id: 'anthropic:claude-3-5-sonnet-20241022',
          created_at: '2024-01-01T00:00:00Z',
          updated_at: '2024-01-01T00:00:00Z'
        })
      })
    )

    render(<AgentChat conversationId={mockConversationId} />)

    await waitFor(() => {
      expect(screen.getByText('Investigation Agent')).toBeInTheDocument()
    })
  })
})
