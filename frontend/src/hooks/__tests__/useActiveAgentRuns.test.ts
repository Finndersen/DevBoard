import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { server } from '../../test/setup'
import { useActiveAgentRuns } from '../useActiveAgentRuns'
import type { BackgroundAgent } from '../../lib/api'

const mockAgents: BackgroundAgent[] = [
  {
    id: 1,
    name: 'Agent 1',
    description: 'Test agent 1',
    prompt: 'Prompt 1',
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
  {
    id: 2,
    name: 'Agent 2',
    description: 'Test agent 2',
    prompt: 'Prompt 2',
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
    has_active_run: true,
  },
]

describe('useActiveAgentRuns', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    server.use(
      http.get('*/api/background-agents/', () => {
        return HttpResponse.json(mockAgents)
      }),
    )
  })

  afterEach(() => {
    vi.clearAllTimers()
  })

  it('returns hasAnyRunning and runningAgentIds', async () => {
    const { result } = renderHook(() => useActiveAgentRuns())

    await waitFor(() => {
      expect(result.current.hasAnyRunning).toBe(true)
    })
    expect(result.current.runningAgentIds).toEqual(new Set([2]))
  })

  it('identifies running agents correctly', async () => {
    const { result } = renderHook(() => useActiveAgentRuns())

    await waitFor(() => {
      expect(result.current.runningAgentIds.has(2)).toBe(true)
      expect(result.current.runningAgentIds.has(1)).toBe(false)
    })
  })

  it('sets hasAnyRunning to true when agents are running', async () => {
    const { result } = renderHook(() => useActiveAgentRuns())

    await waitFor(() => {
      expect(result.current.hasAnyRunning).toBe(true)
    })
  })

  it('sets hasAnyRunning to false when no agents are running', async () => {
    server.use(
      http.get('*/api/background-agents/', () => {
        return HttpResponse.json(mockAgents.map(a => ({ ...a, has_active_run: false })))
      }),
    )

    const { result } = renderHook(() => useActiveAgentRuns())

    await waitFor(() => {
      expect(result.current.hasAnyRunning).toBe(false)
    })
    expect(result.current.runningAgentIds.size).toBe(0)
  })

  it('handles API errors gracefully', async () => {
    server.use(
      http.get('*/api/background-agents/', () => {
        return new HttpResponse(null, { status: 500 })
      }),
    )

    const { result } = renderHook(() => useActiveAgentRuns())

    // Should not crash, errors are logged
    await waitFor(() => {
      expect(result.current.hasAnyRunning).toBe(false)
    })
  })
})
