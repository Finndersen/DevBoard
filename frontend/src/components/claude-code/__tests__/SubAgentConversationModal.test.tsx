import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { render } from '../../../test/utils'
import SubAgentConversationModal from '../SubAgentConversationModal'
import { apiClient } from '../../../lib/api'
import type { ConversationEvent } from '../../../lib/api'

vi.mock('../../../lib/api', () => ({
  apiClient: {
    getClaudeCodeSubAgentMessages: vi.fn(),
  },
}))

vi.mock('../../chat/ConversationMessageList', () => ({
  default: ({ messages, showEmptyState, emptyStateMessage }: { messages: ConversationEvent[]; showEmptyState: boolean; emptyStateMessage: string }) => (
    <div data-testid="conversation-message-list">
      {showEmptyState && <div>{emptyStateMessage}</div>}
      {messages.map((msg, i) => (
        <div key={i} data-testid="message-item">
          {'text_content' in msg ? (msg as { text_content: string }).text_content : 'non-text'}
        </div>
      ))}
    </div>
  ),
}))

const mockMessages: ConversationEvent[] = [
  {
    event_type: 'text_message',
    role: 'user',
    text_content: 'Investigate the auth module',
    timestamp: '2024-01-01T10:00:00Z',
  },
  {
    event_type: 'text_message',
    role: 'agent',
    text_content: 'The auth module uses JWT tokens for authentication.',
    timestamp: '2024-01-01T10:00:05Z',
  },
]

describe('SubAgentConversationModal', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('does not render content when closed', () => {
    render(
      <SubAgentConversationModal
        isOpen={false}
        onClose={() => {}}
        sessionId="session-123"
        agentId="ac2a274"
        title="Test sub-agent"
      />
    )

    expect(screen.queryByText('Test sub-agent')).not.toBeInTheDocument()
  })

  it('fetches and displays messages when opened', async () => {
    vi.mocked(apiClient.getClaudeCodeSubAgentMessages).mockResolvedValue(mockMessages)

    render(
      <SubAgentConversationModal
        isOpen={true}
        onClose={() => {}}
        sessionId="session-123"
        agentId="ac2a274"
        title="Investigate auth module"
      />
    )

    await waitFor(() => {
      expect(apiClient.getClaudeCodeSubAgentMessages).toHaveBeenCalledWith('session-123', 'ac2a274')
    })

    await waitFor(() => {
      expect(screen.getByText('The auth module uses JWT tokens for authentication.')).toBeInTheDocument()
    })
  })

  it('shows loading spinner while fetching', () => {
    vi.mocked(apiClient.getClaudeCodeSubAgentMessages).mockReturnValue(new Promise(() => {}))

    const { container } = render(
      <SubAgentConversationModal
        isOpen={true}
        onClose={() => {}}
        sessionId="session-123"
        agentId="ac2a274"
        title="Loading test"
      />
    )

    expect(container.querySelector('.animate-spin')).toBeInTheDocument()
  })

  it('shows error with retry button on fetch failure', async () => {
    vi.mocked(apiClient.getClaudeCodeSubAgentMessages).mockRejectedValue(new Error('Network error'))

    render(
      <SubAgentConversationModal
        isOpen={true}
        onClose={() => {}}
        sessionId="session-123"
        agentId="ac2a274"
        title="Error test"
      />
    )

    await waitFor(() => {
      expect(screen.getByText('Network error')).toBeInTheDocument()
    })
    expect(screen.getByText('Retry')).toBeInTheDocument()
  })

  it('retries fetch when retry button is clicked', async () => {
    const user = userEvent.setup()
    vi.mocked(apiClient.getClaudeCodeSubAgentMessages)
      .mockRejectedValueOnce(new Error('Network error'))
      .mockResolvedValueOnce(mockMessages)

    render(
      <SubAgentConversationModal
        isOpen={true}
        onClose={() => {}}
        sessionId="session-123"
        agentId="ac2a274"
        title="Retry test"
      />
    )

    await waitFor(() => {
      expect(screen.getByText('Retry')).toBeInTheDocument()
    })

    await user.click(screen.getByText('Retry'))

    await waitFor(() => {
      expect(apiClient.getClaudeCodeSubAgentMessages).toHaveBeenCalledTimes(2)
    })
  })

  it('shows empty state when no messages returned', async () => {
    vi.mocked(apiClient.getClaudeCodeSubAgentMessages).mockResolvedValue([])

    render(
      <SubAgentConversationModal
        isOpen={true}
        onClose={() => {}}
        sessionId="session-123"
        agentId="ac2a274"
        title="Empty test"
      />
    )

    await waitFor(() => {
      expect(screen.getByText('No messages in this sub-agent session')).toBeInTheDocument()
    })
  })
})
