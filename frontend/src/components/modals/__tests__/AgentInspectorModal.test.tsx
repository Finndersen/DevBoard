import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { render } from '../../../test/utils'
import AgentInspectorModal from '../AgentInspectorModal'
import { apiClient } from '../../../lib/api'
import type { AgentConfigResponse } from '../../../lib/api'

vi.mock('../../../lib/api', () => ({
  apiClient: {
    getConversationAgentConfig: vi.fn(),
  },
}))

const mockAgentConfig: AgentConfigResponse = {
  agent_role: 'task_planning',
  behaviour_guidelines: 'You are an expert Task Planning Assistant...',
  context_content: '## TASK DETAILS\nID: 160\nNAME: Add agent inspector feature',
  custom_instructions: 'Always prefer TypeScript strict mode',
  role_tools: [
    {
      name: 'set_task_specification_content',
      description: 'Set the full content of the task specification document.',
      input_schema: { properties: { content: { type: 'string' } }, required: ['content'] },
      source: 'role',
      server_name: null,
    },
    {
      name: 'investigate_codebase',
      description: 'Investigate the codebase to answer questions about architecture.',
      input_schema: { properties: { query: { type: 'string' } }, required: ['query'] },
      source: 'role',
      server_name: null,
    },
  ],
  mcp_tools: [
    {
      name: 'mcp__slack__search_channels',
      description: 'Search for Slack channels by name or topic.',
      input_schema: { properties: { query: { type: 'string' } }, required: ['query'] },
      source: 'mcp',
      server_name: 'Slack',
    },
  ],
  builtin_tools: [
    {
      name: 'Read',
      description: null,
      input_schema: null,
      source: 'builtin',
      server_name: null,
    },
  ],
}

describe('AgentInspectorModal', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('does not render when closed', () => {
    render(<AgentInspectorModal isOpen={false} onClose={() => {}} conversationId={42} />)
    expect(screen.queryByText('Agent Inspector')).not.toBeInTheDocument()
  })

  it('renders loading state initially', () => {
    vi.mocked(apiClient.getConversationAgentConfig).mockReturnValue(new Promise(() => {}))
    const { container } = render(
      <AgentInspectorModal isOpen={true} onClose={() => {}} conversationId={42} />
    )
    expect(container.querySelector('.animate-spin')).toBeInTheDocument()
  })

  it('renders all sections after data loads', async () => {
    vi.mocked(apiClient.getConversationAgentConfig).mockResolvedValue(mockAgentConfig)
    render(<AgentInspectorModal isOpen={true} onClose={() => {}} conversationId={42} />)

    await waitFor(() => {
      expect(screen.getByText('Behaviour Guidelines')).toBeInTheDocument()
      expect(screen.getByText('Context Content')).toBeInTheDocument()
      expect(screen.getByText('Tools')).toBeInTheDocument()
    })

    expect(screen.getByText('You are an expert Task Planning Assistant...')).toBeInTheDocument()
    expect(screen.getByText(/## TASK DETAILS/)).toBeInTheDocument()
  })

  it('hides custom instructions section when null', async () => {
    const config = { ...mockAgentConfig, custom_instructions: null }
    vi.mocked(apiClient.getConversationAgentConfig).mockResolvedValue(config)
    render(<AgentInspectorModal isOpen={true} onClose={() => {}} conversationId={42} />)

    await waitFor(() => {
      expect(screen.getByText('Behaviour Guidelines')).toBeInTheDocument()
    })
    expect(screen.queryByText('Custom Instructions')).not.toBeInTheDocument()
  })

  it('shows custom instructions section when present', async () => {
    vi.mocked(apiClient.getConversationAgentConfig).mockResolvedValue(mockAgentConfig)
    render(<AgentInspectorModal isOpen={true} onClose={() => {}} conversationId={42} />)

    await waitFor(() => {
      expect(screen.getByText('Custom Instructions')).toBeInTheDocument()
      expect(screen.getByText('Always prefer TypeScript strict mode')).toBeInTheDocument()
    })
  })

  it('tool filter buttons show correct counts and filter the list', async () => {
    const user = userEvent.setup()
    vi.mocked(apiClient.getConversationAgentConfig).mockResolvedValue(mockAgentConfig)
    render(<AgentInspectorModal isOpen={true} onClose={() => {}} conversationId={42} />)

    await waitFor(() => {
      expect(screen.getByText('All (4)')).toBeInTheDocument()
      expect(screen.getByText('Role (2)')).toBeInTheDocument()
      expect(screen.getByText('MCP (1)')).toBeInTheDocument()
      expect(screen.getByText('Builtin (1)')).toBeInTheDocument()
    })

    // Filter by Role — role tools visible, builtin hidden
    await user.click(screen.getByText('Role (2)'))
    expect(screen.getByText('set_task_specification_content')).toBeInTheDocument()
    expect(screen.queryByText('Read')).not.toBeInTheDocument()

    // Filter by Builtin — builtin visible, role tools hidden
    await user.click(screen.getByText('Builtin (1)'))
    expect(screen.getByText('Read')).toBeInTheDocument()
    expect(screen.queryByText('set_task_specification_content')).not.toBeInTheDocument()

    // Filter by All — all tools visible again
    await user.click(screen.getByText('All (4)'))
    expect(screen.getByText('set_task_specification_content')).toBeInTheDocument()
    expect(screen.getByText('Read')).toBeInTheDocument()
  })

  it('schema toggle expands and collapses', async () => {
    const user = userEvent.setup()
    vi.mocked(apiClient.getConversationAgentConfig).mockResolvedValue(mockAgentConfig)
    render(<AgentInspectorModal isOpen={true} onClose={() => {}} conversationId={42} />)

    await waitFor(() => {
      expect(screen.getAllByText(/▶ Input schema/).length).toBeGreaterThan(0)
    })

    // Schema content should not be visible initially
    expect(screen.queryByText(/"properties"/)).not.toBeInTheDocument()

    // Expand the first schema toggle
    const toggles = screen.getAllByText(/▶ Input schema/)
    await user.click(toggles[0])

    // Schema JSON should now be visible
    await waitFor(() => {
      expect(screen.getByText(/"properties"/)).toBeInTheDocument()
    })

    // Collapse it again
    await user.click(screen.getByText('▼ Input schema'))
    expect(screen.queryByText(/"properties"/)).not.toBeInTheDocument()
  })

  it('builtin tools show no schema toggle', async () => {
    const user = userEvent.setup()
    vi.mocked(apiClient.getConversationAgentConfig).mockResolvedValue(mockAgentConfig)
    render(<AgentInspectorModal isOpen={true} onClose={() => {}} conversationId={42} />)

    await waitFor(() => {
      expect(screen.getByText('Builtin (1)')).toBeInTheDocument()
    })

    await user.click(screen.getByText('Builtin (1)'))
    expect(screen.getByText('Read')).toBeInTheDocument()
    expect(screen.queryByText(/Input schema/)).not.toBeInTheDocument()
    expect(screen.getByText('Built-in engine tool')).toBeInTheDocument()
  })

  it('shows error state with retry option on fetch failure', async () => {
    vi.mocked(apiClient.getConversationAgentConfig).mockRejectedValue(new Error('Network error'))
    render(<AgentInspectorModal isOpen={true} onClose={() => {}} conversationId={42} />)

    await waitFor(() => {
      expect(screen.getByText('Network error')).toBeInTheDocument()
      expect(screen.getByText('Retry')).toBeInTheDocument()
    })
  })

  it('retries fetch when retry button is clicked', async () => {
    const user = userEvent.setup()
    vi.mocked(apiClient.getConversationAgentConfig)
      .mockRejectedValueOnce(new Error('Network error'))
      .mockResolvedValueOnce(mockAgentConfig)

    render(<AgentInspectorModal isOpen={true} onClose={() => {}} conversationId={42} />)

    await waitFor(() => {
      expect(screen.getByText('Retry')).toBeInTheDocument()
    })

    await user.click(screen.getByText('Retry'))

    await waitFor(() => {
      expect(apiClient.getConversationAgentConfig).toHaveBeenCalledTimes(2)
      expect(screen.getByText('Behaviour Guidelines')).toBeInTheDocument()
    })
  })

  it('displays agent role badge in modal title', async () => {
    vi.mocked(apiClient.getConversationAgentConfig).mockResolvedValue(mockAgentConfig)
    render(<AgentInspectorModal isOpen={true} onClose={() => {}} conversationId={42} />)

    await waitFor(() => {
      expect(screen.getByText('Task Planning Agent')).toBeInTheDocument()
    })
  })
})
