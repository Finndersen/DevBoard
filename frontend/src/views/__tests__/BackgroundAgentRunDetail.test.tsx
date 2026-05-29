import { describe, it, expect, beforeEach } from 'vitest'
import { screen, waitFor, act } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { render } from '../../test/utils'
import { server } from '../../test/setup'
import type { BackgroundAgent, BackgroundAgentRun, ConversationResponse } from '../../lib/api'
import BackgroundAgentRunDetail from '../BackgroundAgentRunDetail'
import { useConversationStreamStore } from '../../stores/conversationStreamStore'

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
  hasActive: boolean
}>) {
  const run = overrides?.run !== undefined ? overrides.run : mockRun
  const conversation = overrides?.conversation !== undefined ? overrides.conversation : mockConversation
  const messages = overrides?.messages ?? []
  const hasActive = overrides?.hasActive ?? false

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
    http.get('*/api/executions/active', () =>
      HttpResponse.json({ executions: hasActive ? [{ conversation_id: 10 }] : [] })
    ),
  )
}

describe('BackgroundAgentRunDetail', () => {
  beforeEach(() => {
    // Reset stream store between tests
    useConversationStreamStore.setState({
      activeStreams: new Map(),
      conversationMessages: new Map(),
    })
  })

  it('shows loading spinner initially', () => {
    setupHandlers()
    render(<BackgroundAgentRunDetail id="42" />)
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

  it('renders messages from the stream store', async () => {
    setupHandlers({ messages: [] })
    render(<BackgroundAgentRunDetail id="42" />)

    // Wait for conversation to resolve and history to load
    await waitFor(() => {
      expect(screen.getByTestId('run-meta-bar')).toBeInTheDocument()
    })

    // Inject a message directly into the store (simulates WS event arriving)
    act(() => {
      useConversationStreamStore.getState().addEvent(10, {
        event_type: 'message',
        role: 'assistant',
        text_content: 'Hello from the agent',
        timestamp: new Date().toISOString(),
      })
    })

    await waitFor(() => {
      expect(screen.getByText('Hello from the agent')).toBeInTheDocument()
    })
  })

  it('shows streaming footer and cursor when isStreaming=true', async () => {
    setupHandlers({ messages: [] })
    render(<BackgroundAgentRunDetail id="42" />)

    await waitFor(() => {
      expect(screen.getByTestId('run-meta-bar')).toBeInTheDocument()
    })

    // Simulate an active stream in the store
    act(() => {
      useConversationStreamStore.setState(state => {
        const updated = new Map(state.activeStreams)
        updated.set(10, {
          isStreaming: true,
          isStopping: false,
          error: null,
          startedAt: Date.now(),
          lastEventAt: Date.now(),
          pendingToolRequests: [],
          isQueued: false,
        })
        return { activeStreams: updated }
      })
    })

    await waitFor(() => {
      expect(screen.getByTestId('streaming-footer')).toBeInTheDocument()
    })
    expect(screen.getByText('Streaming live')).toBeInTheDocument()
    expect(screen.getByLabelText('Agent is streaming')).toBeInTheDocument()
  })

  it('shows live token count in footer when contextUsage is available', async () => {
    setupHandlers({ messages: [] })
    render(<BackgroundAgentRunDetail id="42" />)

    await waitFor(() => {
      expect(screen.getByTestId('run-meta-bar')).toBeInTheDocument()
    })

    act(() => {
      useConversationStreamStore.setState(state => {
        const updatedStreams = new Map(state.activeStreams)
        updatedStreams.set(10, {
          isStreaming: true,
          isStopping: false,
          error: null,
          startedAt: Date.now(),
          lastEventAt: Date.now(),
          pendingToolRequests: [],
          isQueued: false,
        })
        const updatedMessages = new Map(state.conversationMessages)
        updatedMessages.set(10, {
          messages: [],
          historyLoaded: true,
          contextUsage: { input_tokens: 500, output_tokens: 150 },
        })
        return { activeStreams: updatedStreams, conversationMessages: updatedMessages }
      })
    })

    await waitFor(() => {
      expect(screen.getByText('650 tokens')).toBeInTheDocument()
    })
  })

  it('hides streaming footer when run is not streaming', async () => {
    setupHandlers()
    render(<BackgroundAgentRunDetail id="42" />)
    await waitFor(() => {
      expect(screen.getByTestId('run-meta-bar')).toBeInTheDocument()
    })
    expect(screen.queryByTestId('streaming-footer')).not.toBeInTheDocument()
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

  it('reconnects stream when active execution exists', async () => {
    const runningRun: BackgroundAgentRun = {
      ...mockRun,
      status: 'running',
      completed_at: null,
      input_tokens: null,
      output_tokens: null,
    }
    setupHandlers({ run: runningRun, hasActive: true })
    render(<BackgroundAgentRunDetail id="42" />)

    await waitFor(() => {
      // Stream store should have marked conversation 10 as streaming
      const state = useConversationStreamStore.getState()
      expect(state.isConversationStreaming(10)).toBe(true)
    })
  })
})
