import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { render } from '../../../test/utils'
import ConversationsPanel from '../ConversationsPanel'
import { useUIStore } from '../../../stores/uiStore'
import type { ModalDraft } from '../../../stores/uiStore'

vi.mock('../../../hooks/useConversations', () => ({
  useConversations: () => ({ data: [], loading: false, error: null, refetch: vi.fn() }),
}))

vi.mock('../../../stores/conversationStreamStore', () => ({
  useConversationStreamStore: vi.fn().mockImplementation(
    (selector: (state: { activeStreams: Map<unknown, unknown> }) => unknown) =>
      selector({ activeStreams: new Map() })
  ),
}))

vi.mock('../../../hooks/useViewStreamStatus', () => ({
  useViewStreamStatus: vi.fn(),
}))

vi.mock('../../../lib/api', () => ({
  apiClient: {
    getTaskPRStatus: vi.fn().mockResolvedValue({}),
    getConversations: vi.fn().mockResolvedValue([]),
  },
}))

const TEST_DRAFT_ID = 'test-draft-ghost'

function makeCreatingDraft(overrides: Partial<ModalDraft> = {}): ModalDraft {
  return {
    type: 'task',
    formData: {},
    previewLabel: 'Fix a bug in auth',
    createdAt: Date.now(),
    isCreating: true,
    creationError: null,
    ...overrides,
  }
}

describe('ConversationsPanel — ghost entry', () => {
  beforeEach(() => {
    useUIStore.setState({
      modalDrafts: {},
      openModalDraft: null,
    })
  })

  it('renders ghost entry when a draft has isCreating=true', () => {
    useUIStore.setState({
      modalDrafts: { [TEST_DRAFT_ID]: makeCreatingDraft() },
    })

    render(<ConversationsPanel />)

    expect(screen.getByTestId('ghost-entry')).toBeInTheDocument()
    expect(screen.getByText('Initialising task…')).toBeInTheDocument()
  })

  it('shows the prompt preview as subtitle in the ghost entry', () => {
    useUIStore.setState({
      modalDrafts: { [TEST_DRAFT_ID]: makeCreatingDraft({ previewLabel: 'Add OAuth login' }) },
    })

    render(<ConversationsPanel />)

    expect(screen.getByText('Add OAuth login')).toBeInTheDocument()
  })

  it('does not render ghost entry when no drafts are creating', () => {
    useUIStore.setState({
      modalDrafts: {
        [TEST_DRAFT_ID]: makeCreatingDraft({ isCreating: false }),
      },
    })

    render(<ConversationsPanel />)

    expect(screen.queryByTestId('ghost-entry')).not.toBeInTheDocument()
    expect(screen.queryByText('Initialising task…')).not.toBeInTheDocument()
  })

  it('does not render ghost entry when modalDrafts is empty', () => {
    render(<ConversationsPanel />)

    expect(screen.queryByTestId('ghost-entry')).not.toBeInTheDocument()
  })

  it('renders multiple ghost entries for multiple creating drafts', () => {
    useUIStore.setState({
      modalDrafts: {
        'draft-a': makeCreatingDraft({ previewLabel: 'Task A' }),
        'draft-b': makeCreatingDraft({ previewLabel: 'Task B' }),
      },
    })

    render(<ConversationsPanel />)

    expect(screen.getAllByTestId('ghost-entry')).toHaveLength(2)
  })

  it('calls removeModalDraft when dismiss button is clicked', async () => {
    const removeModalDraftSpy = vi.spyOn(useUIStore.getState(), 'removeModalDraft')
    const user = userEvent.setup()

    useUIStore.setState({
      modalDrafts: { [TEST_DRAFT_ID]: makeCreatingDraft() },
    })

    render(<ConversationsPanel />)

    const dismissButton = screen.getByRole('button', { name: /Dismiss initialising task/i })
    await user.click(dismissButton)

    expect(removeModalDraftSpy).toHaveBeenCalledWith(TEST_DRAFT_ID)
    removeModalDraftSpy.mockRestore()
  })
})
