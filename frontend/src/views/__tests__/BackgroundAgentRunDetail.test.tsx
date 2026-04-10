import { describe, it, expect } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { render } from '../../test/utils'
import { server } from '../../test/setup'
import type { BackgroundAgent, BackgroundAgentRun, ConversationResponse } from '../../lib/api'
import BackgroundAgentRunDetail from '../BackgroundAgentRunDetail'

const mockAgent: BackgroundAgent = {
  id: 1,
  name: 'Daily Standup Summariser',
  description: 'Summarises standup messages',
  prompt: 'You are a standup agent.',
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
  input_tokens: 2180,
  output_tokens: 340,
  error: null,
}

const mockConversation: ConversationResponse = {
  id: 10,
  parent_entity_type: 'background_agent_run',
  parent_entity_id: 42,
  agent_role: 'background_agent',
  engine: 'internal',
  model_id: null,
  is_active: false,
  external_session_id: null,
  title: null,
  last_activity_at: null,
  created_at: '2026-01-01T00:00:00Z',
  parent_entity_name: null,
  project_name: null,
}

function setupHandlers(overrides?: Partial<{
  run: BackgroundAgentRun | null
  conversation: ConversationResponse | null
  messages: unknown[]
}>) {
  const run = overrides?.run !== undefined ? overrides.run : mockRun
  const conversation = overrides?.conversation !== undefined ? overrides.conversation : mockConversation
  const messages = overrides?.messages ?? []

  server.use(
    http.get('*/api/background-agent-runs/42', () =>
      run ? HttpResponse.json(run) : HttpResponse.json({ detail: 'Not found' }, { status: 404 })
    ),
    http.get('*/api/background-agents/1', () => HttpResponse.json(mockAgent)),
    http.get('*/api/background-agent-runs/42/conversation', () =>
      conversation ? HttpResponse.json(conversation) : HttpResponse.json({ detail: 'Not found' }, { status: 404 })
    ),
    http.get('*/api/conversations/10/messages', () =>
      HttpResponse.json({ messages, context_usage: null })
    ),
  )
}

describe('BackgroundAgentRunDetail', () => {
  it('shows loading spinner initially', () => {
    setupHandlers()
    render(<BackgroundAgentRunDetail id="42" />)
    // During loading, no metadata bar is visible
    expect(screen.queryByTestId('run-meta-bar')).not.toBeInTheDocument()
  })

  it('renders run metadata after loading', async () => {
    setupHandlers()
    render(<BackgroundAgentRunDetail id="42" />)
    await waitFor(() => {
      expect(screen.getByTestId('run-meta-bar')).toBeInTheDocument()
    })
    expect(screen.getByText('completed')).toBeInTheDocument()
    expect(screen.getByText(/Manual/)).toBeInTheDocument()
    expect(screen.getByText(/2180 in · 340 out/)).toBeInTheDocument()
  })

  it('shows agent name in back button', async () => {
    setupHandlers()
    render(<BackgroundAgentRunDetail id="42" />)
    await waitFor(() => {
      expect(screen.getByText(/Daily Standup Summariser/)).toBeInTheDocument()
    })
  })

  it('shows "Run Conversation" title', async () => {
    setupHandlers()
    render(<BackgroundAgentRunDetail id="42" />)
    await waitFor(() => {
      expect(screen.getByText('Run Conversation')).toBeInTheDocument()
    })
  })

  it('renders empty state when no messages', async () => {
    setupHandlers({ messages: [] })
    render(<BackgroundAgentRunDetail id="42" />)
    await waitFor(() => {
      expect(screen.getByTestId('run-meta-bar')).toBeInTheDocument()
    })
    await waitFor(() => {
      expect(screen.getByText('No messages in this run')).toBeInTheDocument()
    })
  })

  it('shows error state when run fails to load', async () => {
    setupHandlers({ run: null })
    render(<BackgroundAgentRunDetail id="42" />)
    await waitFor(() => {
      expect(screen.queryByTestId('run-meta-bar')).not.toBeInTheDocument()
    })
  })

  it('shows error detail for failed runs', async () => {
    const failedRun: BackgroundAgentRun = {
      ...mockRun,
      status: 'failed',
      error: 'Slack API rate limit exceeded',
      completed_at: new Date(Date.now() - 60_000).toISOString(),
    }
    setupHandlers({ run: failedRun })
    render(<BackgroundAgentRunDetail id="42" />)
    await waitFor(() => {
      expect(screen.getByText(/Slack API rate limit exceeded/)).toBeInTheDocument()
    })
  })

  it('shows schedule trigger icon and label', async () => {
    const scheduleRun: BackgroundAgentRun = {
      ...mockRun,
      triggered_by: 'schedule:0 9 * * *',
    }
    setupHandlers({ run: scheduleRun })
    render(<BackgroundAgentRunDetail id="42" />)
    await waitFor(() => {
      expect(screen.getByText(/Schedule/)).toBeInTheDocument()
    })
  })
})
