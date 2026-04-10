import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, waitFor, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { render } from '../../test/utils'
import { server } from '../../test/setup'
import type { BackgroundAgent } from '../../lib/api'
import BackgroundAgentEditor from '../BackgroundAgentEditor'

// Mock useUIStore navigateTo
const mockNavigateTo = vi.fn()
vi.mock('../../stores/uiStore', () => ({
  useUIStore: () => ({
    navigateTo: mockNavigateTo,
  }),
}))

const mockAgent: BackgroundAgent = {
  id: 42,
  name: 'Test Agent',
  description: 'A test agent description',
  prompt: 'You are a test agent.',
  engine: 'internal',
  model_id: 'openai:gpt-4',
  state: { last_run: null },
  enabled: true,
  project_id: null,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
  mcp_tool_ids: [1],
  event_triggers: [{ id: 1, agent_id: 42, event_type_pattern: 'task.*', created_at: '2026-01-01T00:00:00Z' }],
  schedule_triggers: [{ id: 1, agent_id: 42, cron_expression: '0 9 * * *', last_triggered_at: null, created_at: '2026-01-01T00:00:00Z' }],
}

const mockConfigResponse = {
  agent_role: 'project',
  config: { engine: 'internal', model_id: 'openai:gpt-4' },
  custom_instructions: null,
  available_engines: [
    {
      engine: 'internal',
      display_name: 'Internal (PydanticAI)',
      description: 'Internal agent framework',
      requires_model_selection: true,
      is_available: true,
      unavailable_reason: null,
    },
    {
      engine: 'claude_code',
      display_name: 'Claude Code',
      description: 'Anthropic Claude Code',
      requires_model_selection: false,
      is_available: true,
      unavailable_reason: null,
    },
  ],
  enabled_mcp_tools: [],
}

const mockModelsResponse = {
  models_by_engine: {
    internal: [
      { id: 'openai:gpt-4', name: 'GPT-4', provider: 'openai', model_type: 'standard' },
      { id: 'openai:gpt-3.5-turbo', name: 'GPT-3.5 Turbo', provider: 'openai', model_type: 'fast' },
    ],
    claude_code: [],
  },
}

const mockToolsResponse = [
  { tool_id: 1, tool_name: 'slack_read_channel', server_name: 'slack', description: 'Read a Slack channel' },
  { tool_id: 2, tool_name: 'slack_post_message', server_name: 'slack', description: 'Post to Slack' },
]

function addDefaultHandlers() {
  server.use(
    http.get('*/api/agents/:agentRole/configuration', () =>
      HttpResponse.json(mockConfigResponse),
    ),
    http.get('*/api/agents/available-models', () => HttpResponse.json(mockModelsResponse)),
    http.get('*/api/agents/available-mcp-tools', () => HttpResponse.json(mockToolsResponse)),
  )
}

describe('BackgroundAgentEditor — create mode', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    addDefaultHandlers()
    server.use(
      http.post('*/api/background-agents/', async ({ request }) => {
        const body = await request.json() as Record<string, unknown>
        return HttpResponse.json({ ...mockAgent, id: 99, name: body.name as string })
      }),
      http.patch('*/api/background-agents/99/state', () => HttpResponse.json(mockAgent)),
    )
  })

  it('renders create form with empty fields', async () => {
    render(<BackgroundAgentEditor id="new" />)

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Create Agent' })).toBeInTheDocument()
    })

    expect(screen.getByPlaceholderText('e.g. Daily Standup Summariser')).toHaveValue('')
    expect(screen.getByPlaceholderText("What does this agent do?")).toHaveValue('')
    expect(screen.getByPlaceholderText("Define the agent's behaviour...")).toHaveValue('')
  })

  it('shows validation error when name is missing', async () => {
    const user = userEvent.setup()
    render(<BackgroundAgentEditor id="new" />)

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Create Agent' })).toBeInTheDocument()
    })

    // Fill in prompt but not name
    await user.type(screen.getByPlaceholderText("Define the agent's behaviour..."), 'Do something')

    // Click save
    const saveButton = screen.getByRole('button', { name: 'Create Agent' })
    await user.click(saveButton)

    expect(screen.getByText('Name is required')).toBeInTheDocument()
  })

  it('shows validation error when prompt is missing', async () => {
    const user = userEvent.setup()
    render(<BackgroundAgentEditor id="new" />)

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Create Agent' })).toBeInTheDocument()
    })

    // Fill in name but not prompt
    await user.type(screen.getByPlaceholderText('e.g. Daily Standup Summariser'), 'My Agent')

    const saveButton = screen.getByRole('button', { name: 'Create Agent' })
    await user.click(saveButton)

    expect(screen.getByText('Prompt is required')).toBeInTheDocument()
  })

  it('shows validation error for invalid JSON in initial state', async () => {
    const user = userEvent.setup()
    render(<BackgroundAgentEditor id="new" />)

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Create Agent' })).toBeInTheDocument()
    })

    // Fill required fields
    await user.type(screen.getByPlaceholderText('e.g. Daily Standup Summariser'), 'My Agent')
    await user.type(screen.getByPlaceholderText("Define the agent's behaviour..."), 'Do something')

    // Enter invalid JSON in state field
    const stateTextarea = screen.getByPlaceholderText('{}')
    await user.clear(stateTextarea)
    await user.type(stateTextarea, 'not valid json')

    // Trigger blur to show JSON error
    fireEvent.blur(stateTextarea)

    expect(screen.getByText('Invalid JSON')).toBeInTheDocument()
  })

  it('shows validation error for invalid cron expression', async () => {
    const user = userEvent.setup()
    render(<BackgroundAgentEditor id="new" />)

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Create Agent' })).toBeInTheDocument()
    })

    // Add a schedule trigger
    await user.click(screen.getByText('Add schedule'))

    const cronInput = screen.getByLabelText('Schedule trigger 1')
    await user.type(cronInput, 'not-a-cron')

    // Fill required fields then try to save
    await user.type(screen.getByPlaceholderText('e.g. Daily Standup Summariser'), 'My Agent')
    await user.type(screen.getByPlaceholderText("Define the agent's behaviour..."), 'Do something')

    const saveButton = screen.getByRole('button', { name: 'Create Agent' })
    await user.click(saveButton)

    expect(screen.getByText('Invalid cron expression (expected 5 fields)')).toBeInTheDocument()
  })

  it('creates agent and navigates to detail on successful save', async () => {
    const user = userEvent.setup()
    render(<BackgroundAgentEditor id="new" />)

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Create Agent' })).toBeInTheDocument()
    })

    await user.type(screen.getByPlaceholderText('e.g. Daily Standup Summariser'), 'New Agent')
    await user.type(screen.getByPlaceholderText("Define the agent's behaviour..."), 'You are helpful.')

    const saveButton = screen.getByRole('button', { name: 'Create Agent' })
    await user.click(saveButton)

    await waitFor(() => {
      expect(mockNavigateTo).toHaveBeenCalledWith(
        expect.objectContaining({
          type: 'background-agent-detail',
          entityId: '99',
        }),
      )
    })
  })

  it('navigates back to agents list on cancel', async () => {
    const user = userEvent.setup()
    render(<BackgroundAgentEditor id="new" />)

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Create Agent' })).toBeInTheDocument()
    })

    await user.click(screen.getByRole('button', { name: 'Cancel' }))

    expect(mockNavigateTo).toHaveBeenCalledWith(
      expect.objectContaining({ type: 'background-agents-list' }),
    )
  })

  it('can add and remove schedule triggers', async () => {
    const user = userEvent.setup()
    render(<BackgroundAgentEditor id="new" />)

    await waitFor(() => {
      expect(screen.getByText('Add schedule')).toBeInTheDocument()
    })

    // Add a schedule trigger
    await user.click(screen.getByText('Add schedule'))
    expect(screen.getByLabelText('Schedule trigger 1')).toBeInTheDocument()

    // Remove it
    await user.click(screen.getByLabelText('Remove schedule trigger'))
    expect(screen.queryByLabelText('Schedule trigger 1')).not.toBeInTheDocument()
  })

  it('can add and remove event triggers', async () => {
    const user = userEvent.setup()
    render(<BackgroundAgentEditor id="new" />)

    await waitFor(() => {
      expect(screen.getByText('Add event trigger')).toBeInTheDocument()
    })

    await user.click(screen.getByText('Add event trigger'))
    expect(screen.getByLabelText('Event trigger 1')).toBeInTheDocument()

    await user.click(screen.getByLabelText('Remove event trigger'))
    expect(screen.queryByLabelText('Event trigger 1')).not.toBeInTheDocument()
  })
})

describe('BackgroundAgentEditor — edit mode', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    addDefaultHandlers()
    server.use(
      http.get('*/api/background-agents/42', () => HttpResponse.json(mockAgent)),
      http.put('*/api/background-agents/42', async ({ request }) => {
        const body = await request.json() as Record<string, unknown>
        return HttpResponse.json({ ...mockAgent, ...body })
      }),
      http.patch('*/api/background-agents/42/state', () => HttpResponse.json(mockAgent)),
    )
  })

  it('populates form with existing agent data', async () => {
    render(<BackgroundAgentEditor id="42" />)

    await waitFor(() => {
      expect(screen.getByDisplayValue('Test Agent')).toBeInTheDocument()
    })

    expect(screen.getByDisplayValue('A test agent description')).toBeInTheDocument()
    expect(screen.getByDisplayValue('You are a test agent.')).toBeInTheDocument()
    // Schedule trigger should be populated
    expect(screen.getByDisplayValue('0 9 * * *')).toBeInTheDocument()
    // Event trigger should be populated
    expect(screen.getByDisplayValue('task.*')).toBeInTheDocument()
    // Tool should be shown
    expect(screen.getByText('slack_read_channel')).toBeInTheDocument()
  })

  it('shows edit title in header', async () => {
    render(<BackgroundAgentEditor id="42" />)

    await waitFor(() => {
      expect(screen.getByText('Edit Test Agent')).toBeInTheDocument()
    })
  })

  it('navigates to agent detail on cancel in edit mode', async () => {
    const user = userEvent.setup()
    render(<BackgroundAgentEditor id="42" />)

    await waitFor(() => {
      expect(screen.getByText('Edit Test Agent')).toBeInTheDocument()
    })

    await user.click(screen.getByRole('button', { name: 'Cancel' }))

    expect(mockNavigateTo).toHaveBeenCalledWith(
      expect.objectContaining({ type: 'background-agent-detail', entityId: '42' }),
    )
  })

  it('saves changes and navigates to detail on success', async () => {
    const user = userEvent.setup()
    render(<BackgroundAgentEditor id="42" />)

    await waitFor(() => {
      expect(screen.getByDisplayValue('Test Agent')).toBeInTheDocument()
    })

    // Update name
    const nameInput = screen.getByDisplayValue('Test Agent')
    await user.clear(nameInput)
    await user.type(nameInput, 'Updated Agent')

    await user.click(screen.getByRole('button', { name: 'Save Changes' }))

    await waitFor(() => {
      expect(mockNavigateTo).toHaveBeenCalledWith(
        expect.objectContaining({ type: 'background-agent-detail' }),
      )
    })
  })
})
