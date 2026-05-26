import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { render, mockNavigate } from '../../../test/utils'
import CreateProjectConversationModal from '../CreateProjectConversationModal'
import { apiClient } from '../../../lib/api'
import { useUIStore } from '../../../stores/uiStore'
import type { Project, CreateConversationResponse } from '../../../lib/api'

vi.mock('../../../lib/api', () => ({
  apiClient: {
    getProjects: vi.fn(),
    createProjectConversation: vi.fn(),
  },
}))

const mockProjects: Project[] = [
  {
    id: '1',
    name: 'DevBoard',
    specification_content: 'Project spec',
    created_at: '2026-01-01T00:00:00Z',
  },
  {
    id: '2',
    name: 'Mobile App',
    specification_content: 'Mobile spec',
    created_at: '2026-01-02T00:00:00Z',
  },
]

const mockConversationResponse: CreateConversationResponse = {
  id: 123,
  parent_entity_type: 'project',
  parent_entity_id: 1,
  agent_role: 'project_qa',
  engine: 'claude_code',
  model_id: 'claude-3-5-sonnet-20241022',
  is_active: true,
  external_session_id: 'session_123',
  title: null,
  last_activity_at: null,
  created_at: '2026-05-13T10:00:00Z',
  parent_entity_name: 'DevBoard',
  project_name: 'DevBoard',
  at_cap: false,
}

describe('CreateProjectConversationModal', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    ;(apiClient.getProjects as any).mockResolvedValue(mockProjects)
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    ;(apiClient.createProjectConversation as any).mockResolvedValue(mockConversationResponse)
  })

  it('renders project selector and prompt textarea when open', async () => {
    render(
      <CreateProjectConversationModal
        isOpen={true}
        onClose={vi.fn()}
      />
    )

    expect(screen.getByLabelText('Project')).toBeInTheDocument()
    expect(screen.getByLabelText('Initial Prompt')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Create Conversation/i })).toBeInTheDocument()
  })

  it('populates project options', async () => {
    render(
      <CreateProjectConversationModal
        isOpen={true}
        onClose={vi.fn()}
      />
    )

    await waitFor(() => {
      expect(screen.getByRole('option', { name: 'DevBoard' })).toBeInTheDocument()
      expect(screen.getByRole('option', { name: 'Mobile App' })).toBeInTheDocument()
    })
  })

  it('disables submit button when project or prompt is missing', async () => {
    const user = userEvent.setup()
    render(
      <CreateProjectConversationModal
        isOpen={true}
        onClose={vi.fn()}
      />
    )

    const submitButton = screen.getByRole('button', { name: /Create Conversation/i })
    expect(submitButton).toBeDisabled()

    // Wait for options to load, then select project only
    const projectSelect = screen.getByLabelText('Project')
    await waitFor(() => expect(screen.getByRole('option', { name: 'DevBoard' })).toBeInTheDocument())
    await user.selectOptions(projectSelect, '1')

    expect(submitButton).toBeDisabled()

    // Add prompt
    const promptTextarea = screen.getByLabelText('Initial Prompt')
    await user.type(promptTextarea, 'What should I do?')

    expect(submitButton).not.toBeDisabled()
  })

  it('creates conversation and navigates on successful submit', async () => {
    const user = userEvent.setup()
    const onClose = vi.fn()

    render(
      <CreateProjectConversationModal
        isOpen={true}
        onClose={onClose}
      />
    )

    const projectSelect = screen.getByLabelText('Project')
    const promptTextarea = screen.getByLabelText('Initial Prompt')
    const submitButton = screen.getByRole('button', { name: /Create Conversation/i })

    await waitFor(() => expect(screen.getByRole('option', { name: 'DevBoard' })).toBeInTheDocument())
    await user.selectOptions(projectSelect, '1')
    await user.type(promptTextarea, 'What should I do?')
    await waitFor(() => expect(submitButton).not.toBeDisabled())
    await user.click(submitButton)

    await waitFor(() => {
      expect(apiClient.createProjectConversation).toHaveBeenCalledWith('1', {
        initial_message: 'What should I do?',
      })
    })

    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith('/projects/1?conversation=123')
    })

    expect(onClose).toHaveBeenCalled()
  })

  it('displays error message on failed creation', async () => {
    const user = userEvent.setup()
    const errorMessage = 'Failed to create conversation'
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    ;(apiClient.createProjectConversation as any).mockRejectedValueOnce(
      new Error(errorMessage)
    )

    render(
      <CreateProjectConversationModal
        isOpen={true}
        onClose={vi.fn()}
      />
    )

    const projectSelect = screen.getByLabelText('Project')
    const promptTextarea = screen.getByLabelText('Initial Prompt')
    const submitButton = screen.getByRole('button', { name: /Create Conversation/i })

    await waitFor(() => expect(screen.getByRole('option', { name: 'DevBoard' })).toBeInTheDocument())
    await user.selectOptions(projectSelect, '1')
    await user.type(promptTextarea, 'What should I do?')
    await user.click(submitButton)

    await waitFor(() => {
      expect(screen.getByText(errorMessage)).toBeInTheDocument()
    })
  })

  it('minimizes to draft on minimize button click', async () => {
    const user = userEvent.setup()
    const onClose = vi.fn()

    render(
      <CreateProjectConversationModal
        isOpen={true}
        onClose={onClose}
      />
    )

    const projectSelect = screen.getByLabelText('Project')
    const promptTextarea = screen.getByLabelText('Initial Prompt')

    // Wait for projects to be loaded
    await waitFor(() => {
      expect(screen.getByRole('option', { name: 'DevBoard' })).toBeInTheDocument()
    })

    await user.selectOptions(projectSelect, '1')
    await user.type(promptTextarea, 'What should I do?')

    // Click minimize button (the dash icon)
    const minimizeButton = screen.getByRole('button', { name: /Minimize to draft/i })
    await user.click(minimizeButton)

    expect(onClose).toHaveBeenCalled()

    // Check that draft was saved
    const state = useUIStore.getState()
    const drafts = Object.values(state.modalDrafts).filter(d => d.type === 'project_conversation')
    expect(drafts.length).toBeGreaterThan(0)
    expect(drafts[0].formData).toMatchObject({
      projectId: '1',
      prompt: 'What should I do?',
    })
  })

  it('restores draft when draftId is provided', async () => {
    // Create a draft first
    const store = useUIStore.getState()
    const draftId = `draft-test-${Date.now()}`
    store.saveModalDraft(draftId, {
      type: 'project_conversation',
      formData: {
        projectId: '2',
        prompt: 'Restore this prompt',
      },
      previewLabel: 'Mobile App',
      createdAt: Date.now(),
    })

    render(
      <CreateProjectConversationModal
        isOpen={true}
        onClose={vi.fn()}
        draftId={draftId}
      />
    )

    // Check that form is populated from draft
    const projectSelect = screen.getByLabelText('Project') as HTMLSelectElement
    const promptTextarea = screen.getByLabelText('Initial Prompt') as HTMLTextAreaElement

    await waitFor(() => {
      expect(projectSelect.value).toBe('2')
      expect(promptTextarea.value).toBe('Restore this prompt')
    })
  })

  it('removes draft on close button click', async () => {
    const user = userEvent.setup()
    const onClose = vi.fn()

    // Create a draft first
    const store = useUIStore.getState()
    const draftId = `draft-test-close-${Date.now()}`
    store.saveModalDraft(draftId, {
      type: 'project_conversation',
      formData: { projectId: '1', prompt: 'Test' },
      previewLabel: 'DevBoard',
      createdAt: Date.now(),
    })

    render(
      <CreateProjectConversationModal
        isOpen={true}
        onClose={onClose}
        draftId={draftId}
      />
    )

    // Click cancel button
    const cancelButton = screen.getByRole('button', { name: /Cancel/i })
    await user.click(cancelButton)

    expect(onClose).toHaveBeenCalled()

    // Check that draft was removed
    const updatedState = useUIStore.getState()
    expect(updatedState.modalDrafts[draftId]).toBeUndefined()
  })

  it('removes draft after successful creation', async () => {
    const user = userEvent.setup()
    const onClose = vi.fn()

    // Create a draft first
    const store = useUIStore.getState()
    const draftId = `draft-test-create-${Date.now()}`
    const removeModalDraftSpy = vi.spyOn(store, 'removeModalDraft')

    store.saveModalDraft(draftId, {
      type: 'project_conversation',
      formData: { projectId: '1', prompt: 'Original prompt' },
      previewLabel: 'DevBoard',
      createdAt: Date.now(),
    })

    render(
      <CreateProjectConversationModal
        isOpen={true}
        onClose={onClose}
        draftId={draftId}
      />
    )

    // Wait for projects to load and submit button to be enabled
    await waitFor(() => {
      expect(screen.getByRole('option', { name: 'DevBoard' })).toBeInTheDocument()
    })

    const submitButton = screen.getByRole('button', { name: /Create Conversation/i })
    await waitFor(() => expect(submitButton).not.toBeDisabled())
    await user.click(submitButton)

    // Wait for API call
    await waitFor(() => {
      expect(apiClient.createProjectConversation).toHaveBeenCalled()
    })

    // Verify removeModalDraft was called
    expect(removeModalDraftSpy).toHaveBeenCalledWith(draftId)

    // Verify draft was actually removed from store
    const updatedState = useUIStore.getState()
    expect(updatedState.modalDrafts[draftId]).toBeUndefined()
  })

  it('calls seedInitialMessage with conversation id and prompt text after creation', async () => {
    const { useConversationStreamStore } = await import('../../../stores/conversationStreamStore')
    const user = userEvent.setup()
    const seedInitialMessageSpy = vi.spyOn(useConversationStreamStore.getState(), 'seedInitialMessage')
    const testPrompt = 'How should I structure the API design?'

    render(
      <CreateProjectConversationModal
        isOpen={true}
        onClose={vi.fn()}
      />
    )

    const projectSelect = screen.getByLabelText('Project')
    const promptTextarea = screen.getByLabelText('Initial Prompt')
    const submitButton = screen.getByRole('button', { name: /Create Conversation/i })

    await waitFor(() => expect(screen.getByRole('option', { name: 'DevBoard' })).toBeInTheDocument())
    await user.selectOptions(projectSelect, '1')
    await user.type(promptTextarea, testPrompt)
    await waitFor(() => expect(submitButton).not.toBeDisabled())
    await user.click(submitButton)

    await waitFor(() => {
      expect(seedInitialMessageSpy).toHaveBeenCalledWith(mockConversationResponse.id, testPrompt)
    })

    seedInitialMessageSpy.mockRestore()
  })
})
