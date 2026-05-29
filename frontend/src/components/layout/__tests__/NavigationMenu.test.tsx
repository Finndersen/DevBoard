import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { render } from '../../../test/utils'
import { server } from '../../../test/setup'
import NavigationMenu from '../NavigationMenu'
import type { BackgroundAgent } from '../../../lib/api'

const mockAgents: BackgroundAgent[] = [
  {
    id: 1,
    name: 'Test Agent',
    description: 'Test',
    prompt: 'Prompt',
    engine: 'internal',
    model_id: null,
    state: {},
    enabled: true,
    project_id: null,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    mcp_tool_ids: [],
    event_triggers: [],
    schedule_triggers: [],
    has_active_run: false,
  },
]

describe('NavigationMenu', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.clearAllTimers()
    server.use(
      http.get('*/api/background-agents/', () => {
        return HttpResponse.json(mockAgents)
      }),
    )
  })

  it('renders navigation items', async () => {
    render(<NavigationMenu />)
    await waitFor(() => {
      expect(screen.getByText('Home')).toBeInTheDocument()
    })
    expect(screen.getByText('Agents')).toBeInTheDocument()
    expect(screen.getByText('Projects')).toBeInTheDocument()
  })

  it('does not show pulsing dot when no agents are running', async () => {
    render(<NavigationMenu />)
    await waitFor(() => {
      expect(screen.getByText('Agents')).toBeInTheDocument()
    })
    // Find the Agents nav item and check it doesn't have a running badge
    const agentsLink = screen.getByText('Agents').closest('a')
    const badge = agentsLink?.querySelector('[class*="animate-pulse"]')
    expect(badge).not.toBeInTheDocument()
  })

  it('shows pulsing dot when agents are running', async () => {
    const agentsWithRunning: BackgroundAgent[] = [
      { ...mockAgents[0], has_active_run: true },
    ]
    server.use(
      http.get('*/api/background-agents/', () => {
        return HttpResponse.json(agentsWithRunning)
      }),
    )

    render(<NavigationMenu />)
    await waitFor(() => {
      expect(screen.getByText('Agents')).toBeInTheDocument()
    })

    // Find the Agents nav item and check for the pulsing badge
    const agentsLink = screen.getByText('Agents').closest('a')
    const badge = agentsLink?.querySelector('[class*="animate-pulse"]')
    expect(badge).toBeInTheDocument()
  })

  it('shows DevBoard logo', () => {
    render(<NavigationMenu />)
    expect(screen.getByText('DevBoard')).toBeInTheDocument()
  })

  it('shows collapse toggle button', () => {
    render(<NavigationMenu />)
    expect(screen.getByLabelText(/Collapse sidebar|Expand sidebar/)).toBeInTheDocument()
  })
})
