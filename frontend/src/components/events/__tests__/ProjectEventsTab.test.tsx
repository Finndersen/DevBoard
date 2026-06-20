import React from 'react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, waitFor, fireEvent } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { render } from '../../../test/utils'
import { server } from '../../../test/setup'
import type { LogEntry } from '../../../lib/api'
import ProjectEventsTab from '../ProjectEventsTab'

function renderProjectEventsTab(projectId: number = 1) {
  return render(<ProjectEventsTab projectId={projectId} />)
}

const mockEntries: LogEntry[] = [
  {
    id: 1,
    timestamp: new Date(Date.now() - 25 * 60_000).toISOString(),
    source: 'developer',
    type: 'thought',
    content: 'Developer thought entry',
    metadata: null,
    project_id: 1,
    task_id: 10,
    status: 'active',
    pinned: false,
  },
  {
    id: 2,
    timestamp: new Date(Date.now() - 60 * 60_000).toISOString(),
    source: 'system',
    type: 'task_status_change',
    content: 'Task moved to implementing',
    metadata: null,
    project_id: 1,
    task_id: 11,
    status: 'active',
    pinned: false,
  },
  {
    id: 3,
    timestamp: new Date(Date.now() - 2 * 60 * 60_000).toISOString(),
    source: 'agent',
    type: 'spec_updated',
    content: 'Agent updated spec',
    metadata: null,
    project_id: 1,
    task_id: null,
    status: 'active',
    pinned: false,
  },
]

const pinnedEntry: LogEntry = {
  id: 5,
  timestamp: new Date(Date.now() - 30 * 60_000).toISOString(),
  source: 'developer',
  type: 'blocker',
  content: 'Pinned blocker entry',
  metadata: null,
  project_id: 1,
  task_id: 12,
  status: 'active',
  pinned: true,
}

function setupHandlers(projectId: number = 1, entries: LogEntry[] = mockEntries, pinned: LogEntry[] = []) {
  server.use(
    http.get('*/api/log-entries', ({ request }) => {
      const url = new URL(request.url)
      const reqProjectId = url.searchParams.get('project_id')
      if (reqProjectId !== String(projectId)) return HttpResponse.json([])
      if (url.searchParams.get('pinned') === 'true') {
        return HttpResponse.json(pinned)
      }
      return HttpResponse.json(entries)
    }),
    http.patch('*/api/log-entries/:id', async ({ params, request }) => {
      const update = await request.json() as Partial<LogEntry>
      const entry = entries.find(e => e.id === Number(params.id))
        ?? (pinned.find(e => e.id === Number(params.id)))
      if (!entry) return new HttpResponse(null, { status: 404 })
      return HttpResponse.json({ ...entry, ...update })
    }),
  )
}

describe('ProjectEventsTab', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    setupHandlers()
  })

  it('renders entries filtered to the project', async () => {
    renderProjectEventsTab(1)

    await waitFor(() => {
      expect(screen.getByText('Developer thought entry')).toBeInTheDocument()
    })

    expect(screen.getByText('Task moved to implementing')).toBeInTheDocument()
    expect(screen.getByText('Agent updated spec')).toBeInTheDocument()
  })

  it('renders filter bar with source toggles', async () => {
    renderProjectEventsTab()

    await waitFor(() => {
      expect(screen.getByTestId('filter-bar')).toBeInTheDocument()
    })

    expect(screen.getByTestId('source-toggle-developer')).toBeInTheDocument()
    expect(screen.getByTestId('source-toggle-system')).toBeInTheDocument()
    expect(screen.getByTestId('source-toggle-agent')).toBeInTheDocument()
  })

  it('shows task links without project links', async () => {
    renderProjectEventsTab()

    await waitFor(() => {
      expect(screen.getByText('Task #10')).toBeInTheDocument()
    })

    expect(screen.getByText('Task #11')).toBeInTheDocument()

    // Should NOT show project links
    expect(screen.queryByText(/Project #/)).not.toBeInTheDocument()
  })

  describe('source toggles', () => {
    it('all sources are active by default', async () => {
      renderProjectEventsTab()

      await waitFor(() => {
        expect(screen.getByTestId('source-toggle-developer')).toBeInTheDocument()
      })

      expect(screen.getByTestId('source-toggle-developer')).toHaveAttribute('aria-pressed', 'true')
      expect(screen.getByTestId('source-toggle-system')).toHaveAttribute('aria-pressed', 'true')
      expect(screen.getByTestId('source-toggle-agent')).toHaveAttribute('aria-pressed', 'true')
    })

    it('filters entries when a source is selected', async () => {
      renderProjectEventsTab()

      await waitFor(() => {
        expect(screen.getByTestId('source-toggle-developer')).toBeInTheDocument()
      })

      fireEvent.click(screen.getByTestId('source-toggle-developer'))

      await waitFor(() => {
        expect(screen.getByTestId('source-toggle-developer')).toHaveAttribute('aria-pressed', 'true')
        expect(screen.getByTestId('source-toggle-system')).toHaveAttribute('aria-pressed', 'false')
        expect(screen.getByTestId('source-toggle-agent')).toHaveAttribute('aria-pressed', 'false')
      })
    })

    it('resets to all sources when active source is clicked again', async () => {
      renderProjectEventsTab()

      await waitFor(() => {
        expect(screen.getByTestId('source-toggle-developer')).toBeInTheDocument()
      })

      fireEvent.click(screen.getByTestId('source-toggle-developer'))
      await waitFor(() => {
        expect(screen.getByTestId('source-toggle-system')).toHaveAttribute('aria-pressed', 'false')
      })

      fireEvent.click(screen.getByTestId('source-toggle-developer'))
      await waitFor(() => {
        expect(screen.getByTestId('source-toggle-system')).toHaveAttribute('aria-pressed', 'true')
      })
    })
  })

  describe('type filter', () => {
    it('updates when text is entered', async () => {
      renderProjectEventsTab()

      await waitFor(() => {
        expect(screen.getByTestId('type-filter')).toBeInTheDocument()
      })

      const input = screen.getByTestId('type-filter') as HTMLInputElement
      fireEvent.change(input, { target: { value: 'thought' } })

      expect(input.value).toBe('thought')
    })
  })

  describe('pinned section', () => {
    it('shows pinned section when pinned entries exist', async () => {
      setupHandlers(1, mockEntries, [pinnedEntry])

      renderProjectEventsTab()

      await waitFor(() => {
        expect(screen.getByTestId('pinned-section')).toBeInTheDocument()
      })

      expect(screen.getByText('Pinned (1)')).toBeInTheDocument()
      expect(screen.getByText('Pinned blocker entry')).toBeInTheDocument()
    })

    it('hides pinned section when no pinned entries', async () => {
      renderProjectEventsTab()

      await waitFor(() => {
        expect(screen.queryByTestId('pinned-section')).not.toBeInTheDocument()
      })
    })

    it('collapses when header is clicked', async () => {
      setupHandlers(1, mockEntries, [pinnedEntry])

      renderProjectEventsTab()

      await waitFor(() => {
        expect(screen.getByText('Pinned blocker entry')).toBeInTheDocument()
      })

      const pinnedHeader = screen.getByRole('button', { name: /Pinned/ })
      fireEvent.click(pinnedHeader)

      await waitFor(() => {
        expect(screen.queryByText('Pinned blocker entry')).not.toBeInTheDocument()
      })
    })
  })

  describe('load more', () => {
    it('shows load more button when a full page of results is returned', async () => {
      const fullPage = Array.from({ length: 20 }, (_, i) => ({
        ...mockEntries[0],
        id: i + 10,
        content: `Entry ${i}`,
      }))
      setupHandlers(1, fullPage)

      renderProjectEventsTab()

      await waitFor(() => {
        expect(screen.getByTestId('load-more')).toBeInTheDocument()
      })
    })

    it('does not show load more button when fewer than limit results are returned', async () => {
      renderProjectEventsTab()

      await waitFor(() => {
        expect(screen.queryByTestId('load-more')).not.toBeInTheDocument()
      })
    })

    it('appends entries when load more button is clicked', async () => {
      const page1 = Array.from({ length: 20 }, (_, i) => ({
        ...mockEntries[0],
        id: i + 100,
        content: `Entry ${i}`,
      }))
      const page2 = Array.from({ length: 10 }, (_, i) => ({
        ...mockEntries[0],
        id: i + 200,
        content: `Entry ${i + 20}`,
      }))

      server.use(
        http.get('*/api/log-entries', ({ request }) => {
          const url = new URL(request.url)
          const reqProjectId = url.searchParams.get('project_id')
          const reqOffset = Number(url.searchParams.get('offset') ?? 0)

          if (reqProjectId !== '1') return HttpResponse.json([])
          if (url.searchParams.get('pinned') === 'true') return HttpResponse.json([])

          if (reqOffset === 0) return HttpResponse.json(page1)
          if (reqOffset === 20) return HttpResponse.json(page2)
          return HttpResponse.json([])
        }),
      )

      renderProjectEventsTab()

      await waitFor(() => {
        expect(screen.getByText('Entry 0')).toBeInTheDocument()
      })

      const loadMoreButton = screen.getByTestId('load-more')
      fireEvent.click(loadMoreButton)

      await waitFor(() => {
        expect(screen.getByText('Entry 20')).toBeInTheDocument()
      })
    })
  })

  describe('empty state', () => {
    it('shows empty state message when no entries', async () => {
      setupHandlers(1, [])

      renderProjectEventsTab()

      await waitFor(() => {
        expect(screen.getByText('No events')).toBeInTheDocument()
      })
    })
  })

  describe('refresh button', () => {
    it('refetches entries when clicked', async () => {
      const fetchSpy = vi.fn()
      server.use(
        http.get('*/api/log-entries', () => {
          fetchSpy()
          return HttpResponse.json(mockEntries)
        }),
      )

      renderProjectEventsTab()

      await waitFor(() => {
        expect(screen.getByTestId('refresh-button')).toBeInTheDocument()
      })

      const initialCallCount = fetchSpy.mock.calls.length

      fireEvent.click(screen.getByTestId('refresh-button'))

      await waitFor(() => {
        expect(fetchSpy.mock.calls.length).toBeGreaterThan(initialCallCount)
      })
    })
  })
})
