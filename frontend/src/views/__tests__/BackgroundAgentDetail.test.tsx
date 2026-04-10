import { describe, it, expect } from 'vitest'
import { screen, waitFor, fireEvent } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { render } from '../../test/utils'
import { server } from '../../test/setup'
import type { BackgroundAgent, BackgroundAgentRun, BackgroundAgentRunStats } from '../../lib/api'
import BackgroundAgentDetail from '../BackgroundAgentDetail'
import {
  computeSuccessRate,
  formatTriggeredBy,
  formatDuration,
  formatRelativeTime,
} from '../backgroundAgentUtils'

// ── Unit tests for utility functions ─────────────────────────────────────────

describe('computeSuccessRate', () => {
  it('returns null when total is 0', () => {
    expect(computeSuccessRate(0, 0)).toBeNull()
  })

  it('returns 100 when all runs completed', () => {
    expect(computeSuccessRate(10, 10)).toBe(100)
  })

  it('computes fractional rate correctly', () => {
    expect(computeSuccessRate(3, 4)).toBe(75)
  })
})

describe('formatTriggeredBy', () => {
  it('formats manual trigger', () => {
    const result = formatTriggeredBy('manual')
    expect(result.label).toBe('Manual')
    expect(result.icon).toBeTruthy()
  })

  it('formats schedule trigger', () => {
    const result = formatTriggeredBy('schedule:0 9 * * *')
    expect(result.label).toBe('Schedule')
  })

  it('formats event trigger', () => {
    const result = formatTriggeredBy('event:task.completed')
    expect(result.label).toBe('Event')
  })

  it('falls back to the raw string for unknown triggers', () => {
    const result = formatTriggeredBy('unknown-source')
    expect(result.label).toBe('unknown-source')
  })
})

describe('formatDuration', () => {
  it('returns em-dash when completedAt is null', () => {
    expect(formatDuration('2026-01-01T00:00:00Z', null)).toBe('—')
  })

  it('formats seconds', () => {
    const start = '2026-01-01T00:00:00Z'
    const end = '2026-01-01T00:00:12Z'
    expect(formatDuration(start, end)).toBe('12s')
  })

  it('formats minutes', () => {
    const start = '2026-01-01T00:00:00Z'
    const end = '2026-01-01T00:02:30Z'
    expect(formatDuration(start, end)).toBe('2m 30s')
  })
})

describe('formatRelativeTime', () => {
  it('returns "just now" for very recent timestamps', () => {
    const ts = new Date(Date.now() - 30_000).toISOString()
    expect(formatRelativeTime(ts)).toBe('just now')
  })

  it('formats minutes ago', () => {
    const ts = new Date(Date.now() - 5 * 60_000).toISOString()
    expect(formatRelativeTime(ts)).toBe('5m ago')
  })

  it('formats hours ago', () => {
    const ts = new Date(Date.now() - 3 * 60 * 60_000).toISOString()
    expect(formatRelativeTime(ts)).toBe('3h ago')
  })
})

// ── Component tests ───────────────────────────────────────────────────────────

const mockAgent: BackgroundAgent = {
  id: 1,
  name: 'Daily Standup Summariser',
  description: 'Summarises standup messages',
  prompt: 'You are a standup agent.',
  engine: 'internal',
  model_id: null,
  state: { last_run: null },
  enabled: true,
  project_id: null,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
  mcp_tool_ids: [],
  event_triggers: [],
  schedule_triggers: [],
}

const mockRun: BackgroundAgentRun = {
  id: 42,
  agent_id: 1,
  conversation_id: 10,
  triggered_by: 'manual',
  trigger_event_id: null,
  started_at: new Date(Date.now() - 2 * 60 * 60_000).toISOString(),
  completed_at: new Date(Date.now() - 2 * 60 * 60_000 + 12_000).toISOString(),
  status: 'completed',
  state_before: {},
  state_after: null,
  input_tokens: 2000,
  output_tokens: 300,
  error: null,
}

const mockStats: BackgroundAgentRunStats = {
  total_runs: 10,
  completed: 9,
  failed: 1,
  avg_input_tokens: 1800,
  avg_output_tokens: 280,
}

function setupHandlers() {
  server.use(
    http.get('*/api/background-agents/1', () => HttpResponse.json(mockAgent)),
    http.get('*/api/background-agents/1/runs', () => HttpResponse.json([mockRun])),
    http.get('*/api/background-agents/1/runs/stats', () => HttpResponse.json(mockStats)),
  )
}

describe('BackgroundAgentDetail component', () => {
  it('renders agent name and enabled badge', async () => {
    setupHandlers()
    render(<BackgroundAgentDetail id="1" />)
    await waitFor(() => {
      expect(screen.getByText('Daily Standup Summariser')).toBeInTheDocument()
    })
    expect(screen.getByText('Enabled')).toBeInTheDocument()
  })

  it('displays summary stats', async () => {
    setupHandlers()
    render(<BackgroundAgentDetail id="1" />)
    await waitFor(() => {
      expect(screen.getByText('10')).toBeInTheDocument() // total runs
    })
    expect(screen.getByText('90.0%')).toBeInTheDocument() // success rate
    expect(screen.getByText('1,800')).toBeInTheDocument() // avg tokens
  })

  it('renders run rows in history tab', async () => {
    setupHandlers()
    render(<BackgroundAgentDetail id="1" />)
    await waitFor(() => {
      expect(screen.getAllByTestId('run-row').length).toBeGreaterThan(0)
    })
    expect(screen.getByText('completed')).toBeInTheDocument()
    expect(screen.getByText('2000 in · 300 out')).toBeInTheDocument()
  })

  it('shows failed run error message', async () => {
    const failedRun: BackgroundAgentRun = {
      ...mockRun,
      id: 99,
      status: 'failed',
      error: 'Connection timeout',
    }
    server.use(
      http.get('*/api/background-agents/1', () => HttpResponse.json(mockAgent)),
      http.get('*/api/background-agents/1/runs', () => HttpResponse.json([failedRun])),
      http.get('*/api/background-agents/1/runs/stats', () => HttpResponse.json(mockStats)),
    )
    render(<BackgroundAgentDetail id="1" />)
    await waitFor(() => {
      expect(screen.getByText(/Connection timeout/)).toBeInTheDocument()
    })
  })

  it('switches to configuration tab', async () => {
    setupHandlers()
    render(<BackgroundAgentDetail id="1" />)
    await waitFor(() => {
      expect(screen.getByText('Daily Standup Summariser')).toBeInTheDocument()
    })
    fireEvent.click(screen.getByText('Configuration'))
    expect(screen.getByText('You are a standup agent.')).toBeInTheDocument()
  })

  it('switches to state tab', async () => {
    setupHandlers()
    render(<BackgroundAgentDetail id="1" />)
    await waitFor(() => {
      expect(screen.getByText('Daily Standup Summariser')).toBeInTheDocument()
    })
    fireEvent.click(screen.getByText('State'))
    expect(screen.getByText(/last_run/)).toBeInTheDocument()
  })

  it('shows error when agent fails to load', async () => {
    server.use(
      http.get('*/api/background-agents/1', () => HttpResponse.json({ detail: 'Not found' }, { status: 404 })),
      http.get('*/api/background-agents/1/runs', () => HttpResponse.json([])),
      http.get('*/api/background-agents/1/runs/stats', () => HttpResponse.json(mockStats)),
    )
    render(<BackgroundAgentDetail id="1" />)
    await waitFor(() => {
      expect(screen.queryByText('Daily Standup Summariser')).not.toBeInTheDocument()
    })
  })
})
