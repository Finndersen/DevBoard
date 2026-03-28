import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { render } from '../../../test/utils'
import SubAgentConversationModal from '../SubAgentConversationModal'
import type { ConversationEvent } from '../../../lib/api'

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
        fetchMessages={() => Promise.resolve([])}
        title="Test sub-agent"
      />
    )

    expect(screen.queryByText(/Test sub-agent/)).not.toBeInTheDocument()
  })

  it('fetches and displays messages when opened', async () => {
    const fetchMessages = vi.fn().mockResolvedValue(mockMessages)

    render(
      <SubAgentConversationModal
        isOpen={true}
        onClose={() => {}}
        fetchMessages={fetchMessages}
        title="Investigate auth module"
      />
    )

    await waitFor(() => {
      expect(fetchMessages).toHaveBeenCalledTimes(1)
    })

    await waitFor(() => {
      expect(screen.getByText('The auth module uses JWT tokens for authentication.')).toBeInTheDocument()
    })
  })

  it('shows loading spinner while fetching', () => {
    const fetchMessages = vi.fn().mockReturnValue(new Promise(() => {}))

    const { container } = render(
      <SubAgentConversationModal
        isOpen={true}
        onClose={() => {}}
        fetchMessages={fetchMessages}
        title="Loading test"
      />
    )

    expect(container.querySelector('.animate-spin')).toBeInTheDocument()
  })

  it('shows error with retry button on fetch failure', async () => {
    const fetchMessages = vi.fn().mockRejectedValue(new Error('Network error'))

    render(
      <SubAgentConversationModal
        isOpen={true}
        onClose={() => {}}
        fetchMessages={fetchMessages}
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
    const fetchMessages = vi.fn()
      .mockRejectedValueOnce(new Error('Network error'))
      .mockResolvedValueOnce(mockMessages)

    render(
      <SubAgentConversationModal
        isOpen={true}
        onClose={() => {}}
        fetchMessages={fetchMessages}
        title="Retry test"
      />
    )

    await waitFor(() => {
      expect(screen.getByText('Retry')).toBeInTheDocument()
    })

    await user.click(screen.getByText('Retry'))

    await waitFor(() => {
      expect(fetchMessages).toHaveBeenCalledTimes(2)
    })
  })

  it('shows empty state when no messages returned', async () => {
    const fetchMessages = vi.fn().mockResolvedValue([])

    render(
      <SubAgentConversationModal
        isOpen={true}
        onClose={() => {}}
        fetchMessages={fetchMessages}
        title="Empty test"
      />
    )

    await waitFor(() => {
      expect(screen.getByText('No messages in this sub-agent session')).toBeInTheDocument()
    })
  })

  it('displays "Sub Agent:" prefix in the modal header', () => {
    render(
      <SubAgentConversationModal
        isOpen={true}
        onClose={() => {}}
        fetchMessages={() => new Promise(() => {})}
        title="Investigate auth module"
      />
    )

    expect(screen.getByText(/Sub Agent: Investigate auth module/)).toBeInTheDocument()
  })

  it('displays sub-agent type badge when subagentType is provided', () => {
    render(
      <SubAgentConversationModal
        isOpen={true}
        onClose={() => {}}
        fetchMessages={() => new Promise(() => {})}
        title="Investigate auth module"
        subagentType="Explore"
      />
    )

    expect(screen.getByText('Explore')).toBeInTheDocument()
  })

  it('does not display sub-agent type badge when subagentType is not provided', () => {
    render(
      <SubAgentConversationModal
        isOpen={true}
        onClose={() => {}}
        fetchMessages={() => new Promise(() => {})}
        title="Test title"
      />
    )

    expect(screen.queryByText('Explore')).not.toBeInTheDocument()
    expect(screen.queryByText('Bash')).not.toBeInTheDocument()
  })

  it('displays agent ID in the modal header', () => {
    render(
      <SubAgentConversationModal
        isOpen={true}
        onClose={() => {}}
        fetchMessages={() => new Promise(() => {})}
        title="Test title"
        subtitle="ac2a274"
      />
    )

    expect(screen.getByText('ac2a274')).toBeInTheDocument()
  })
})
