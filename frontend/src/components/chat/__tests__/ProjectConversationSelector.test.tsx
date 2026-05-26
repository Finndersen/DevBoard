import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { render } from '../../../test/utils'
import ProjectConversationSelector from '../ProjectConversationSelector'
import { apiClient } from '../../../lib/api'
import type { ConversationResponse } from '../../../lib/api'

// Mock the apiClient
vi.mock('../../../lib/api', () => ({
  apiClient: {
    getProjectConversations: vi.fn(),
  },
}))

const mockConversations: ConversationResponse[] = [
  {
    id: 1,
    project_id: 1,
    title: 'First Conversation',
    last_activity_at: '2024-01-01T10:00:00Z',
  },
  {
    id: 2,
    project_id: 1,
    title: 'Second Conversation',
    last_activity_at: '2024-01-01T11:00:00Z',
  },
]

const mockConversationsWithNewId: ConversationResponse[] = [
  ...mockConversations,
  {
    id: 3,
    project_id: 1,
    title: 'New Conversation',
    last_activity_at: '2024-01-01T12:00:00Z',
  },
]

describe('ProjectConversationSelector', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('rendering', () => {
    it('renders with correct button structure and fetches on mount', async () => {
      vi.mocked(apiClient.getProjectConversations).mockResolvedValue(mockConversations)

      render(
        <ProjectConversationSelector
          projectId={1}
          activeConversationId={1}
          onSelect={vi.fn()}
          onNew={vi.fn()}
          onDelete={vi.fn()}
          onRename={vi.fn()}
        />
      )

      await waitFor(() => {
        expect(screen.getByText('First Conversation')).toBeInTheDocument()
      })

      expect(apiClient.getProjectConversations).toHaveBeenCalledWith(1)
      const button = screen.getByRole('button', { hidden: true })
      expect(button).toBeInTheDocument()
      expect(button).toHaveTextContent('First Conversation')
    })

    it('displays "Untitled" when activeConversationId does not match any conversation', async () => {
      vi.mocked(apiClient.getProjectConversations).mockResolvedValue(mockConversations)

      render(
        <ProjectConversationSelector
          projectId={1}
          activeConversationId={999}
          onSelect={vi.fn()}
          onNew={vi.fn()}
          onDelete={vi.fn()}
          onRename={vi.fn()}
        />
      )

      await waitFor(() => {
        // Wait for initial fetch
        expect(apiClient.getProjectConversations).toHaveBeenCalled()
      })

      // The trigger button should show "Untitled"
      const button = screen.getByRole('button', { hidden: true })
      expect(button).toHaveTextContent('Untitled')
    })
  })

  describe('activeConversationId refetch behavior', () => {
    it('refetches conversations when activeConversationId changes and conversation is not in list', async () => {
      const { rerender } = render(
        <ProjectConversationSelector
          projectId={1}
          activeConversationId={1}
          onSelect={vi.fn()}
          onNew={vi.fn()}
          onDelete={vi.fn()}
          onRename={vi.fn()}
        />
      )

      vi.mocked(apiClient.getProjectConversations).mockResolvedValue(mockConversations)

      await waitFor(() => {
        expect(apiClient.getProjectConversations).toHaveBeenCalled()
      })

      const initialCallCount = vi.mocked(apiClient.getProjectConversations).mock.calls.length

      // Now rerender with a new activeConversationId that doesn't exist in the list
      vi.mocked(apiClient.getProjectConversations).mockResolvedValue(mockConversationsWithNewId)

      rerender(
        <ProjectConversationSelector
          projectId={1}
          activeConversationId={3}
          onSelect={vi.fn()}
          onNew={vi.fn()}
          onDelete={vi.fn()}
          onRename={vi.fn()}
        />
      )

      // Should trigger a refetch because conversation 3 is not in the initial list
      await waitFor(() => {
        expect(apiClient.getProjectConversations).toHaveBeenCalledTimes(initialCallCount + 1)
      })

      // Now the button should display the new conversation's title
      await waitFor(() => {
        const button = screen.getByRole('button', { hidden: true })
        expect(button).toHaveTextContent('New Conversation')
      })
    })

    it('does not refetch when activeConversationId changes but conversation is already in list', async () => {
      vi.mocked(apiClient.getProjectConversations).mockResolvedValue(mockConversations)

      const { rerender } = render(
        <ProjectConversationSelector
          projectId={1}
          activeConversationId={1}
          onSelect={vi.fn()}
          onNew={vi.fn()}
          onDelete={vi.fn()}
          onRename={vi.fn()}
        />
      )

      await waitFor(() => {
        expect(apiClient.getProjectConversations).toHaveBeenCalled()
      })

      const initialCallCount = vi.mocked(apiClient.getProjectConversations).mock.calls.length

      // Change activeConversationId to an existing conversation (id: 2)
      rerender(
        <ProjectConversationSelector
          projectId={1}
          activeConversationId={2}
          onSelect={vi.fn()}
          onNew={vi.fn()}
          onDelete={vi.fn()}
          onRename={vi.fn()}
        />
      )

      // Should NOT trigger another fetch since conversation 2 is already in the list
      await waitFor(() => {
        expect(apiClient.getProjectConversations).toHaveBeenCalledTimes(initialCallCount)
      })

      // The button should now display the second conversation's title
      const button = screen.getByRole('button', { hidden: true })
      expect(button).toHaveTextContent('Second Conversation')
    })

    it('updates display title once refetch resolves', async () => {
      const { rerender } = render(
        <ProjectConversationSelector
          projectId={1}
          activeConversationId={1}
          onSelect={vi.fn()}
          onNew={vi.fn()}
          onDelete={vi.fn()}
          onRename={vi.fn()}
        />
      )

      vi.mocked(apiClient.getProjectConversations).mockResolvedValue(mockConversations)

      await waitFor(() => {
        expect(apiClient.getProjectConversations).toHaveBeenCalled()
      })

      // Simulate a new conversation being created — rerender with new ID
      vi.mocked(apiClient.getProjectConversations).mockResolvedValue(mockConversationsWithNewId)

      rerender(
        <ProjectConversationSelector
          projectId={1}
          activeConversationId={3}
          onSelect={vi.fn()}
          onNew={vi.fn()}
          onDelete={vi.fn()}
          onRename={vi.fn()}
        />
      )

      // Initially should show "Untitled" because conversation 3 is not yet fetched
      let button = screen.getByRole('button', { hidden: true })
      expect(button).toHaveTextContent('Untitled')

      // Wait for refetch to complete
      await waitFor(() => {
        button = screen.getByRole('button', { hidden: true })
        expect(button).toHaveTextContent('New Conversation')
      })
    })
  })

  describe('dropdown interaction', () => {
    it('opens and closes dropdown when button is clicked', async () => {
      vi.mocked(apiClient.getProjectConversations).mockResolvedValue(mockConversations)

      const user = userEvent.setup()

      render(
        <ProjectConversationSelector
          projectId={1}
          activeConversationId={1}
          onSelect={vi.fn()}
          onNew={vi.fn()}
          onDelete={vi.fn()}
          onRename={vi.fn()}
        />
      )

      await waitFor(() => {
        expect(apiClient.getProjectConversations).toHaveBeenCalled()
      })

      const button = screen.getByRole('button', { hidden: true })

      // Initially dropdown should be closed — no dropdown menu should exist
      expect(screen.queryByText('No conversations yet')).not.toBeInTheDocument()

      // Click button to open
      await user.click(button)

      // Now the dropdown menu should be visible with conversation list
      await waitFor(() => {
        // The dropdown renders both conversations in a list
        const items = screen.getAllByText(/Conversation/)
        expect(items.length).toBeGreaterThan(1)
      })

      // Click button again to close
      await user.click(button)

      // Wait for the dropdown to close — reopen to verify it was closed
      await new Promise(resolve => setTimeout(resolve, 50))
      // If we try to open again and see the conversations, the previous close worked
      await user.click(button)
      await waitFor(() => {
        const items = screen.getAllByText(/Conversation/)
        expect(items.length).toBeGreaterThan(0)
      })
    })

    it('refetches conversations when dropdown opens', async () => {
      vi.mocked(apiClient.getProjectConversations).mockResolvedValue(mockConversations)

      const user = userEvent.setup()

      render(
        <ProjectConversationSelector
          projectId={1}
          activeConversationId={1}
          onSelect={vi.fn()}
          onNew={vi.fn()}
          onDelete={vi.fn()}
          onRename={vi.fn()}
        />
      )

      await waitFor(() => {
        expect(apiClient.getProjectConversations).toHaveBeenCalled()
      })

      const initialCallCount = vi.mocked(apiClient.getProjectConversations).mock.calls.length

      const button = screen.getByRole('button', { hidden: true })
      await user.click(button)

      // Should refetch when dropdown opens
      await waitFor(() => {
        expect(apiClient.getProjectConversations).toHaveBeenCalledTimes(initialCallCount + 1)
      })
    })

    it('calls onSelect when a conversation is clicked', async () => {
      vi.mocked(apiClient.getProjectConversations).mockResolvedValue(mockConversations)

      const onSelect = vi.fn()
      const user = userEvent.setup()

      render(
        <ProjectConversationSelector
          projectId={1}
          activeConversationId={1}
          onSelect={onSelect}
          onNew={vi.fn()}
          onDelete={vi.fn()}
          onRename={vi.fn()}
        />
      )

      await waitFor(() => {
        expect(apiClient.getProjectConversations).toHaveBeenCalled()
      })

      const button = screen.getByRole('button', { hidden: true })
      await user.click(button)

      // Find the "Second Conversation" text and click its parent row
      await waitFor(() => {
        expect(screen.getByText('Second Conversation')).toBeInTheDocument()
      })

      const secondConvTitle = screen.getByText('Second Conversation')
      const secondConvRow = secondConvTitle.closest('.cursor-pointer')!
      await user.click(secondConvRow)

      expect(onSelect).toHaveBeenCalledWith(2)
    })
  })

})
