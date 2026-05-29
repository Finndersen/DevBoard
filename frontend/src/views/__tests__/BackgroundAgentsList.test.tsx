import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, waitFor, fireEvent } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { render } from '../../test/utils'
import { server } from '../../test/setup'
import type { BackgroundAgent } from '../../lib/api'
import BackgroundAgentsList from '../BackgroundAgentsList'
import { filterAgents } from '../backgroundAgentFilters'

const mockAgents: BackgroundAgent[] = [
  {
    id: 1,
    name: 'Daily Standup Summariser',
    description: 'Summarises Slack standup messages each morning',
    prompt: 'You are a standup summariser...',
    engine: 'internal',
    model_id: null,
    state: {},
    enabled: true,
    project_id: null,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    mcp_tool_ids: [],
    event_triggers: [],
    schedule_triggers: [{ id: 1, agent_id: 1, cron_expression: '0 9 * * *', last_triggered_at: null, created_at: '2026-01-01T00:00:00Z' }],
    has_active_run: false,
  },
  {
    id: 2,
    name: 'PR Review Assistant',
    description: 'Reviews new PRs and posts initial feedback',
    prompt: 'You are a PR reviewer...',
    engine: 'claude_code',
    model_id: 'claude-sonnet-4-20250514',
    state: {},
    enabled: true,
    project_id: 1,
    created_at: '2026-01-02T00:00:00Z',
    updated_at: '2026-01-02T00:00:00Z',
    mcp_tool_ids: [],
    event_triggers: [{ id: 1, agent_id: 2, event_type_pattern: 'github.pr.*', created_at: '2026-01-02T00:00:00Z' }],
    schedule_triggers: [],
    has_active_run: false,
  },
  {
    id: 3,
    name: 'Stale Task Notifier',
    description: 'Flags tasks with no activity for 7+ days',
    prompt: 'You flag stale tasks...',
    engine: 'internal',
    model_id: null,
    state: {},
    enabled: false,
    project_id: null,
    created_at: '2026-01-03T00:00:00Z',
    updated_at: '2026-01-03T00:00:00Z',
    mcp_tool_ids: [],
    event_triggers: [],
    schedule_triggers: [{ id: 2, agent_id: 3, cron_expression: '0 10 * * 1', last_triggered_at: null, created_at: '2026-01-03T00:00:00Z' }],
    has_active_run: false,
  },
]

function setupHandlers(agents: BackgroundAgent[] = mockAgents) {
  server.use(
    http.get('*/api/background-agents/', () => {
      return HttpResponse.json(agents)
    }),
    http.put('*/api/background-agents/:id', async ({ params, request }) => {
      const update = await request.json() as Partial<BackgroundAgent>
      const agent = agents.find(a => a.id === Number(params.id))
      if (!agent) return new HttpResponse(null, { status: 404 })
      return HttpResponse.json({ ...agent, ...update })
    }),
  )
}

function renderList() {
  return render(<BackgroundAgentsList />)
}

describe('BackgroundAgentsList', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    setupHandlers()
  })

  it('renders the view header with title', async () => {
    renderList()
    await waitFor(() => {
      expect(screen.getByText('Agents')).toBeInTheDocument()
    })
  })

  it('renders the create agent button', async () => {
    renderList()
    await waitFor(() => {
      expect(screen.getByTestId('create-agent-button')).toBeInTheDocument()
    })
  })

  it('renders the filter bar', async () => {
    renderList()
    await waitFor(() => {
      expect(screen.getByTestId('filter-bar')).toBeInTheDocument()
    })
    expect(screen.getByTestId('filter-all')).toBeInTheDocument()
    expect(screen.getByTestId('filter-enabled')).toBeInTheDocument()
    expect(screen.getByTestId('filter-disabled')).toBeInTheDocument()
    expect(screen.getByTestId('filter-scheduled')).toBeInTheDocument()
    expect(screen.getByTestId('filter-event-driven')).toBeInTheDocument()
  })

  it('renders all agents from API', async () => {
    renderList()
    await waitFor(() => {
      expect(screen.getByText('Daily Standup Summariser')).toBeInTheDocument()
    })
    expect(screen.getByText('PR Review Assistant')).toBeInTheDocument()
    expect(screen.getByText('Stale Task Notifier')).toBeInTheDocument()
  })

  it('shows agent descriptions', async () => {
    renderList()
    await waitFor(() => {
      expect(screen.getByText('Summarises Slack standup messages each morning')).toBeInTheDocument()
    })
  })

  it('renders enabled toggle for each agent', async () => {
    renderList()
    await waitFor(() => {
      expect(screen.getByTestId('toggle-1')).toBeInTheDocument()
    })
    expect(screen.getByTestId('toggle-1')).toHaveAttribute('aria-checked', 'true')
    expect(screen.getByTestId('toggle-3')).toHaveAttribute('aria-checked', 'false')
  })

  it('renders schedule trigger icon for agents with schedules', async () => {
    renderList()
    await waitFor(() => {
      expect(screen.getAllByTestId('agent-row').length).toBeGreaterThan(0)
    })
    // Agent 1 has schedule
    const row1 = screen.getByTestId('agent-name-1').closest('tr')!
    expect(row1.querySelector('[data-testid="trigger-schedule"]')).toBeInTheDocument()
    expect(row1.querySelector('[data-testid="trigger-event"]')).not.toBeInTheDocument()
  })

  it('renders event trigger icon for agents with event triggers', async () => {
    renderList()
    await waitFor(() => {
      expect(screen.getByTestId('agent-name-2')).toBeInTheDocument()
    })
    const row2 = screen.getByTestId('agent-name-2').closest('tr')!
    expect(row2.querySelector('[data-testid="trigger-event"]')).toBeInTheDocument()
    expect(row2.querySelector('[data-testid="trigger-schedule"]')).not.toBeInTheDocument()
  })

  it('always renders manual trigger icon', async () => {
    renderList()
    await waitFor(() => {
      expect(screen.getByTestId('agents-table')).toBeInTheDocument()
    })
    const manualIcons = screen.getAllByTestId('trigger-manual')
    expect(manualIcons).toHaveLength(mockAgents.length)
  })

  it('calls updateAgent when toggle is clicked', async () => {
    const putSpy = vi.fn().mockImplementation((_req) => {
      return HttpResponse.json({ ...mockAgents[0], enabled: false })
    })
    server.use(http.put('*/api/background-agents/1', putSpy))

    renderList()
    await waitFor(() => {
      expect(screen.getByTestId('toggle-1')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByTestId('toggle-1'))

    await waitFor(() => {
      expect(putSpy).toHaveBeenCalled()
    })
  })

  it('optimistically updates toggle state', async () => {
    // Delay the server response to test optimistic update
    server.use(
      http.put('*/api/background-agents/1', async () => {
        await new Promise(resolve => setTimeout(resolve, 100))
        return HttpResponse.json({ ...mockAgents[0], enabled: false })
      }),
    )

    renderList()
    await waitFor(() => {
      expect(screen.getByTestId('toggle-1')).toBeInTheDocument()
    })

    expect(screen.getByTestId('toggle-1')).toHaveAttribute('aria-checked', 'true')
    fireEvent.click(screen.getByTestId('toggle-1'))

    // Optimistic update should be immediate
    expect(screen.getByTestId('toggle-1')).toHaveAttribute('aria-checked', 'false')
  })

  it('shows empty state when no agents', async () => {
    setupHandlers([])
    renderList()
    await waitFor(() => {
      expect(screen.getByText(/No background agents configured yet/)).toBeInTheDocument()
    })
  })

  it('shows error state when API fails', async () => {
    server.use(
      http.get('*/api/background-agents/', () => {
        return new HttpResponse(null, { status: 500 })
      }),
    )
    renderList()
    await waitFor(() => {
      // ErrorMessage component renders
      expect(screen.getByRole('alert')).toBeInTheDocument()
    })
  })

  it('shows "Running now" badge when agent has active run', async () => {
    const agentWithRun: BackgroundAgent[] = [
      { ...mockAgents[0], has_active_run: true },
    ]
    setupHandlers(agentWithRun)
    renderList()
    await waitFor(() => {
      expect(screen.getByTestId('running-badge-1')).toBeInTheDocument()
    })
    expect(screen.getByText('Running now')).toBeInTheDocument()
    expect(screen.queryByTestId('toggle-1')).not.toBeInTheDocument()
  })

  it('shows toggle when agent does not have active run', async () => {
    renderList()
    await waitFor(() => {
      expect(screen.getByTestId('toggle-1')).toBeInTheDocument()
    })
    expect(screen.queryByTestId('running-badge-1')).not.toBeInTheDocument()
  })

  it('shows toggle for one agent and running badge for another', async () => {
    const mixedAgents: BackgroundAgent[] = [
      { ...mockAgents[0], has_active_run: false },
      { ...mockAgents[1], has_active_run: true },
    ]
    setupHandlers(mixedAgents)
    renderList()
    await waitFor(() => {
      expect(screen.getByTestId('toggle-1')).toBeInTheDocument()
    })
    expect(screen.getByTestId('running-badge-2')).toBeInTheDocument()
    expect(screen.queryByTestId('toggle-2')).not.toBeInTheDocument()
  })
})

describe('filterAgents', () => {
  it('returns all agents for "all" filter', () => {
    const result = filterAgents(mockAgents, 'all')
    expect(result).toHaveLength(3)
  })

  it('returns only enabled agents', () => {
    const result = filterAgents(mockAgents, 'enabled')
    expect(result).toHaveLength(2)
    expect(result.every(a => a.enabled)).toBe(true)
  })

  it('returns only disabled agents', () => {
    const result = filterAgents(mockAgents, 'disabled')
    expect(result).toHaveLength(1)
    expect(result[0].name).toBe('Stale Task Notifier')
  })

  it('returns only agents with schedule triggers', () => {
    const result = filterAgents(mockAgents, 'scheduled')
    expect(result).toHaveLength(2)
    expect(result.every(a => a.schedule_triggers.length > 0)).toBe(true)
  })

  it('returns only agents with event triggers', () => {
    const result = filterAgents(mockAgents, 'event-driven')
    expect(result).toHaveLength(1)
    expect(result[0].name).toBe('PR Review Assistant')
  })

  it('returns empty array when no agents match filter', () => {
    const disabledAgents = mockAgents.filter(a => !a.enabled)
    // All disabled agents filtered for enabled
    const result = filterAgents(disabledAgents, 'enabled')
    expect(result).toHaveLength(0)
  })
})
