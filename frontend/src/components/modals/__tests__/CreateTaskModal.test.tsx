import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { render } from '../../../test/utils'
import CreateTaskModal from '../CreateTaskModal'
import { useUIStore } from '../../../stores/uiStore'
import type { Task, AgentConfigurationResponse, Codebase } from '../../../lib/api'

// Mock react-router-dom
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return {
    ...actual,
    useNavigate: vi.fn(),
  }
})

const TEST_DRAFT_ID = 'test-draft-id'
const TEST_PROJECT_ID = '1'

const mockCodabases: Codebase[] = [
  {
    id: 1,
    name: 'Test Codebase',
    description: 'A test codebase',
    local_path: '/path/to/codebase',
    repository_url: null,
    default_branch: 'main',
    merge_method: 'merge',
    branch_handling: 'worktree',
    max_worktrees: null,
    setup_command: null,
    developer_context: null,
  },
]

const mockAgentConfig: AgentConfigurationResponse = {
  agent_role: 'task_planning',
  config: {
    engine: 'internal',
    model: {
      id: 'anthropic:claude-opus-4',
      provider: 'anthropic',
      name: 'claude-opus-4',
      model_type: 'advanced',
    },
  },
  available_engines: [],
  enabled_mcp_tools: [],
  custom_instructions: null,
  model_type_display_names: {
    fast: 'claude-haiku-4-5',
    standard: 'claude-sonnet-4',
    advanced: 'claude-opus-4',
  },
}

const mockCreatedTask: Task = {
  id: 99,
  project_id: 1,
  title: 'Created Task',
  status: 'Designing',
  codebase_id: 1,
  conversation_id: 10,
  specification_document_id: 20,
  implementation_plan_document_id: null,
  created_at: '2024-01-01T00:00:00Z',
}

vi.mock('../../../lib/api', () => ({
  apiClient: {
    getProjects: vi.fn().mockResolvedValue([]),
    getProjectCodebases: vi.fn(),
    getCustomFieldDefinitions: vi.fn(),
    getAgentConfiguration: vi.fn(),
    createTask: vi.fn(),
    getProjectTasks: vi.fn().mockResolvedValue([]),
  },
}))

describe('CreateTaskModal — model type selector', () => {
  beforeEach(async () => {
    vi.clearAllMocks()
    const { apiClient } = await import('../../../lib/api')
    vi.mocked(apiClient.getProjectCodebases).mockResolvedValue(mockCodabases)
    vi.mocked(apiClient.getCustomFieldDefinitions).mockResolvedValue([])
    vi.mocked(apiClient.getAgentConfiguration).mockResolvedValue(mockAgentConfig)
    vi.mocked(apiClient.createTask).mockResolvedValue(mockCreatedTask)
    vi.mocked(apiClient.getProjectTasks).mockResolvedValue([])

    // Open the modal via the store
    useUIStore.setState({ openModalDraft: TEST_DRAFT_ID, modalDrafts: {} })
  })

  // Wait for codebase data to load and select the first codebase.
  // When projectId prop is provided, the codebase select is the only combobox before selection.
  async function selectCodebase(user: ReturnType<typeof userEvent.setup>) {
    await screen.findByRole('option', { name: 'Test Codebase' })
    const [codebaseSelect] = screen.getAllByRole('combobox')
    await user.selectOptions(codebaseSelect, '1')
  }

  // Find the Agent Model select — it appears (second combobox) after a codebase is selected.
  async function findModelSelect(): Promise<HTMLElement> {
    // Wait for the model options to appear
    await screen.findByRole('option', { name: /Fast \(claude-haiku-4-5\)/i })
    const selects = screen.getAllByRole('combobox')
    return selects[selects.length - 1]
  }

  it('shows auto-select toggle (checked) and disabled dropdown when prompt is provided', async () => {
    const user = userEvent.setup()
    render(
      <CreateTaskModal draftId={TEST_DRAFT_ID} onClose={vi.fn()} projectId={TEST_PROJECT_ID} />
    )

    await user.type(screen.getByPlaceholderText(/Describe what you want/i), 'Fix a bug')
    await selectCodebase(user)

    const toggle = await screen.findByRole('checkbox', { name: /Auto-select from prompt/i })
    expect(toggle).toBeChecked()

    const modelSelect = await findModelSelect()
    expect(modelSelect).toBeDisabled()
  })

  it('enables dropdown when auto-select toggle is unchecked', async () => {
    const user = userEvent.setup()
    render(
      <CreateTaskModal draftId={TEST_DRAFT_ID} onClose={vi.fn()} projectId={TEST_PROJECT_ID} />
    )

    await user.type(screen.getByPlaceholderText(/Describe what you want/i), 'Fix a bug')
    await selectCodebase(user)

    const toggle = await screen.findByRole('checkbox', { name: /Auto-select from prompt/i })
    await user.click(toggle)
    expect(toggle).not.toBeChecked()

    const modelSelect = await findModelSelect()
    expect(modelSelect).not.toBeDisabled()
  })

  it('hides auto-select toggle when no initial prompt is given', async () => {
    const user = userEvent.setup()
    render(
      <CreateTaskModal draftId={TEST_DRAFT_ID} onClose={vi.fn()} projectId={TEST_PROJECT_ID} />
    )

    await user.type(screen.getByPlaceholderText(/Auto-generated from prompt/i), 'My Task')
    await selectCodebase(user)

    // Auto-select toggle should not appear when there is no prompt
    await waitFor(() => {
      expect(screen.queryByRole('checkbox', { name: /Auto-select from prompt/i })).not.toBeInTheDocument()
    })

    const modelSelect = await findModelSelect()
    expect(modelSelect).not.toBeDisabled()
  })

  it('populates model dropdown with options from agent config', async () => {
    const user = userEvent.setup()
    render(
      <CreateTaskModal draftId={TEST_DRAFT_ID} onClose={vi.fn()} projectId={TEST_PROJECT_ID} />
    )

    await selectCodebase(user)

    await waitFor(() => {
      expect(screen.getByRole('option', { name: 'Fast (claude-haiku-4-5)' })).toBeInTheDocument()
      expect(screen.getByRole('option', { name: 'Standard (claude-sonnet-4)' })).toBeInTheDocument()
      expect(screen.getByRole('option', { name: 'Advanced (claude-opus-4)' })).toBeInTheDocument()
    })
  })

  it('sends model_type: "auto" when auto-select is on and prompt is provided', async () => {
    const { apiClient } = await import('../../../lib/api')
    const user = userEvent.setup()
    render(
      <CreateTaskModal draftId={TEST_DRAFT_ID} onClose={vi.fn()} projectId={TEST_PROJECT_ID} />
    )

    await user.type(screen.getByPlaceholderText(/Describe what you want/i), 'Add a new feature')
    await selectCodebase(user)

    const submitButton = screen.getByRole('button', { name: /Create Task/i })
    await waitFor(() => expect(submitButton).not.toBeDisabled())
    await user.click(submitButton)

    await waitFor(() => {
      expect(apiClient.createTask).toHaveBeenCalledWith(
        TEST_PROJECT_ID,
        expect.objectContaining({ model_type: 'auto' })
      )
    })
  })

  it('sends selected model_type when auto-select is off', async () => {
    const { apiClient } = await import('../../../lib/api')
    const user = userEvent.setup()
    render(
      <CreateTaskModal draftId={TEST_DRAFT_ID} onClose={vi.fn()} projectId={TEST_PROJECT_ID} />
    )

    await user.type(screen.getByPlaceholderText(/Describe what you want/i), 'Refactor module')
    await selectCodebase(user)

    const toggle = await screen.findByRole('checkbox', { name: /Auto-select from prompt/i })
    await user.click(toggle)

    const modelSelect = await findModelSelect()
    await user.selectOptions(modelSelect, 'fast')

    const submitButton = screen.getByRole('button', { name: /Create Task/i })
    await waitFor(() => expect(submitButton).not.toBeDisabled())
    await user.click(submitButton)

    await waitFor(() => {
      expect(apiClient.createTask).toHaveBeenCalledWith(
        TEST_PROJECT_ID,
        expect.objectContaining({ model_type: 'fast' })
      )
    })
  })

  it('does not send model_type: "auto" when no prompt is given', async () => {
    const { apiClient } = await import('../../../lib/api')
    const user = userEvent.setup()
    render(
      <CreateTaskModal draftId={TEST_DRAFT_ID} onClose={vi.fn()} projectId={TEST_PROJECT_ID} />
    )

    await user.type(screen.getByPlaceholderText(/Auto-generated from prompt/i), 'My Task')
    await selectCodebase(user)

    const submitButton = screen.getByRole('button', { name: /Create Task/i })
    await waitFor(() => expect(submitButton).not.toBeDisabled())
    await user.click(submitButton)

    await waitFor(() => {
      expect(apiClient.createTask).toHaveBeenCalled()
    })
    const callArgs = vi.mocked(apiClient.createTask).mock.calls[0][1] as Record<string, unknown>
    expect(callArgs.model_type).not.toBe('auto')
  })

  it('fetches agent configuration exactly once per modal open', async () => {
    const { apiClient } = await import('../../../lib/api')
    const user = userEvent.setup()
    render(
      <CreateTaskModal draftId={TEST_DRAFT_ID} onClose={vi.fn()} projectId={TEST_PROJECT_ID} />
    )

    await user.type(screen.getByPlaceholderText(/Describe what you want/i), 'Build feature')
    await selectCodebase(user)

    // Wait for agent config fetch and any subsequent draft saves to settle
    await waitFor(() => expect(apiClient.getAgentConfiguration).toHaveBeenCalled())
    await new Promise(r => setTimeout(r, 400))

    expect(apiClient.getAgentConfiguration).toHaveBeenCalledTimes(1)
  })

  it('calls seedInitialMessage with conversation id and prompt text after task creation', async () => {
    const { useConversationStreamStore } = await import('../../../stores/conversationStreamStore')
    const seedInitialMessageSpy = vi.spyOn(useConversationStreamStore.getState(), 'seedInitialMessage')
    const user = userEvent.setup()
    const testPrompt = 'Fix critical bug in auth module'

    render(
      <CreateTaskModal draftId={TEST_DRAFT_ID} onClose={vi.fn()} projectId={TEST_PROJECT_ID} />
    )

    await user.type(screen.getByPlaceholderText(/Describe what you want/i), testPrompt)
    await selectCodebase(user)

    const submitButton = screen.getByRole('button', { name: /Create Task/i })
    await waitFor(() => expect(submitButton).not.toBeDisabled())
    await user.click(submitButton)

    await waitFor(() => {
      expect(seedInitialMessageSpy).toHaveBeenCalledWith(mockCreatedTask.conversation_id, testPrompt)
    })

    seedInitialMessageSpy.mockRestore()
  })

  it('does not call seedInitialMessage when no initial prompt is provided', async () => {
    const { apiClient } = await import('../../../lib/api')
    const { useConversationStreamStore } = await import('../../../stores/conversationStreamStore')
    const seedInitialMessageSpy = vi.spyOn(useConversationStreamStore.getState(), 'seedInitialMessage')
    const user = userEvent.setup()

    render(
      <CreateTaskModal draftId={TEST_DRAFT_ID} onClose={vi.fn()} projectId={TEST_PROJECT_ID} />
    )

    // Only provide task title, no prompt
    await user.type(screen.getByPlaceholderText(/Auto-generated from prompt/i), 'My Task')
    await selectCodebase(user)

    const submitButton = screen.getByRole('button', { name: /Create Task/i })
    await waitFor(() => expect(submitButton).not.toBeDisabled())
    await user.click(submitButton)

    await waitFor(() => {
      expect(apiClient.createTask).toHaveBeenCalled()
    })

    // seedInitialMessage should not be called when there's no prompt
    expect(seedInitialMessageSpy).not.toHaveBeenCalled()

    seedInitialMessageSpy.mockRestore()
  })
})

describe('CreateTaskModal — non-blocking submission', () => {
  beforeEach(async () => {
    vi.clearAllMocks()
    const { apiClient } = await import('../../../lib/api')
    vi.mocked(apiClient.getProjectCodebases).mockResolvedValue(mockCodabases)
    vi.mocked(apiClient.getCustomFieldDefinitions).mockResolvedValue([])
    vi.mocked(apiClient.getAgentConfiguration).mockResolvedValue(mockAgentConfig)
    vi.mocked(apiClient.getProjectTasks).mockResolvedValue([])

    // Open the modal via the store with an initial draft
    useUIStore.setState({
      openModalDraft: TEST_DRAFT_ID,
      modalDrafts: {
        [TEST_DRAFT_ID]: {
          type: 'task',
          formData: {},
          previewLabel: 'Test Task',
          createdAt: Date.now()
        }
      }
    })
  })

  async function selectCodebase(user: ReturnType<typeof userEvent.setup>) {
    await screen.findByRole('option', { name: 'Test Codebase' })
    const [codebaseSelect] = screen.getAllByRole('combobox')
    await user.selectOptions(codebaseSelect, '1')
  }

  it('closes modal immediately on submit without waiting for API response', async () => {
    const { apiClient } = await import('../../../lib/api')
    vi.mocked(apiClient.createTask).mockImplementation(
      () => new Promise(resolve => setTimeout(() => resolve(mockCreatedTask), 100))
    )

    const onClose = vi.fn()
    const user = userEvent.setup()

    render(
      <CreateTaskModal draftId={TEST_DRAFT_ID} onClose={onClose} projectId={TEST_PROJECT_ID} />
    )

    await user.type(screen.getByPlaceholderText(/Describe what you want/i), 'Add feature')
    await selectCodebase(user)

    const submitButton = screen.getByRole('button', { name: /Create Task/i })
    await waitFor(() => expect(submitButton).not.toBeDisabled())
    await user.click(submitButton)

    // Modal should close immediately (onClose called synchronously)
    expect(onClose).toHaveBeenCalled()

    // Modal should not be visible
    expect(screen.queryByText(/Create New Task/i)).not.toBeInTheDocument()
  })

  it('marks task creation as in-progress in store and removes on success', async () => {
    const { apiClient } = await import('../../../lib/api')
    // Use a deferred promise so the "creating" window stays open until we explicitly resolve —
    // a real timer here races with userEvent's internal awaits and flakes under load.
    let resolveCreate!: (value: typeof mockCreatedTask) => void
    vi.mocked(apiClient.createTask).mockImplementation(
      () => new Promise(resolve => { resolveCreate = resolve })
    )

    const user = userEvent.setup()

    render(
      <CreateTaskModal draftId={TEST_DRAFT_ID} onClose={vi.fn()} projectId={TEST_PROJECT_ID} />
    )

    await user.type(screen.getByPlaceholderText(/Describe what you want/i), 'Add feature')
    await selectCodebase(user)

    const submitButton = screen.getByRole('button', { name: /Create Task/i })
    await waitFor(() => expect(submitButton).not.toBeDisabled())

    // Before submit, draft should exist and not be creating
    let state = useUIStore.getState()
    expect(state.modalDrafts[TEST_DRAFT_ID]).toBeDefined()

    await user.click(submitButton)

    // Right after submit (API call still pending), draft should be marked as creating
    state = useUIStore.getState()
    expect(state.modalDrafts[TEST_DRAFT_ID]?.isCreating).toBe(true)

    // Resolve the API call — draft should then be removed
    resolveCreate(mockCreatedTask)
    await waitFor(() => {
      state = useUIStore.getState()
      expect(state.modalDrafts[TEST_DRAFT_ID]).toBeUndefined()
    })

    // Verify API was called
    expect(apiClient.createTask).toHaveBeenCalled()
  })

  it('handles API failure by setting error state in draft', async () => {
    const { apiClient } = await import('../../../lib/api')
    const testError = new Error('Network error')
    vi.mocked(apiClient.createTask).mockRejectedValue(testError)

    // Reset store for this test
    const testDraftId = 'test-draft-error'
    useUIStore.setState({
      openModalDraft: testDraftId,
      modalDrafts: {
        [testDraftId]: {
          type: 'task',
          formData: {},
          previewLabel: 'Error Test',
          createdAt: Date.now()
        }
      }
    })

    const user = userEvent.setup()

    render(
      <CreateTaskModal draftId={testDraftId} onClose={vi.fn()} projectId={TEST_PROJECT_ID} />
    )

    await user.type(screen.getByPlaceholderText(/Describe what you want/i), 'Add feature')
    await selectCodebase(user)

    const submitButton = screen.getByRole('button', { name: /Create Task/i })
    await waitFor(() => expect(submitButton).not.toBeDisabled())
    await user.click(submitButton)

    // Wait for async error handling
    await waitFor(() => {
      const state = useUIStore.getState()
      const draft = state.modalDrafts[testDraftId]
      expect(draft?.creationError).toBe('Network error')
      expect(draft?.isCreating).toBe(false)
    })
  })
})
