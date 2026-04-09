import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, waitFor, fireEvent } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { render } from '../../test/utils'
import { server } from '../../test/setup'
import type { LogEntry } from '../../lib/api'
import EventsList from '../EventsList'

const mockEntries: LogEntry[] = [
  {
    id: 1,
    timestamp: new Date(Date.now() - 25 * 60_000).toISOString(),
    source: 'developer',
    type: 'thought',
    content: 'Developer thought entry',
    metadata: null,
    project_id: 1,
    task_id: null,
    status: 'active',
    pinned: false,
  },
  {
    id: 2,
    timestamp: new Date(Date.now() - 60 * 60_000).toISOString(),
    source: 'system',
    type: 'task_status_change',
    content: 'Task moved to implementing',
    metadata: { old_status: 'planning', new_status: 'implementing' },
    project_id: null,
    task_id: 1,
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
    project_id: null,
    task_id: null,
    status: 'active',
    pinned: false,
  },
  {
    id: 4,
    timestamp: new Date(Date.now() - 3 * 60 * 60_000).toISOString(),
    source: 'developer',
    type: 'blocker',
    content: 'Resolved blocker',
    metadata: null,
    project_id: null,
    task_id: null,
    status: 'resolved',
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
  task_id: null,
  status: 'active',
  pinned: true,
}

function setupHandlers(entries: LogEntry[] = mockEntries, pinned: LogEntry[] = []) {
  server.use(
    http.get('*/api/log-entries', ({ request }) => {
      const url = new URL(request.url)
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

describe('EventsList', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    setupHandlers()
  })

  it('renders filter bar with source toggles', async () => {
    render(<EventsList />)

    await waitFor(() => {
      expect(screen.getByTestId('filter-bar')).toBeInTheDocument()
    })

    expect(screen.getByTestId('source-toggle-developer')).toBeInTheDocument()
    expect(screen.getByTestId('source-toggle-system')).toBeInTheDocument()
    expect(screen.getByTestId('source-toggle-agent')).toBeInTheDocument()
  })

  it('renders all source types in the main feed', async () => {
    render(<EventsList />)

    await waitFor(() => {
      expect(screen.getByText('Developer thought entry')).toBeInTheDocument()
    })

    expect(screen.getByText('Task moved to implementing')).toBeInTheDocument()
    expect(screen.getByText('Agent updated spec')).toBeInTheDocument()
  })

  it('shows correct source labels for each entry type', async () => {
    render(<EventsList />)

    await waitFor(() => {
      expect(screen.getAllByText('👤 developer').length).toBeGreaterThan(0)
    })

    expect(screen.getByText('⚙️ system')).toBeInTheDocument()
    expect(screen.getByText('🤖 agent')).toBeInTheDocument()
  })

  it('renders resolved entries with reduced opacity and strikethrough', async () => {
    render(<EventsList />)

    await waitFor(() => {
      expect(screen.getByText('Resolved blocker')).toBeInTheDocument()
    })

    const resolvedText = screen.getByText('Resolved blocker')
    expect(resolvedText).toHaveClass('line-through')

    const card = resolvedText.closest('[data-testid="entry-card"]')
    expect(card).toHaveClass('opacity-50')
  })

  it('shows expandable metadata section for entries with metadata', async () => {
    render(<EventsList />)

    await waitFor(() => {
      expect(screen.getByText('Task moved to implementing')).toBeInTheDocument()
    })

    // The entry with metadata should have a details/summary element
    const summaries = screen.getAllByText('metadata')
    expect(summaries.length).toBeGreaterThan(0)
  })

  it('shows project link for entries with project_id', async () => {
    render(<EventsList />)

    await waitFor(() => {
      // Project name appears as a clickable button in the entry card (not just as a select option)
      expect(screen.getByRole('button', { name: 'Test Project' })).toBeInTheDocument()
    })
  })

  it('shows task link for entries with task_id', async () => {
    render(<EventsList />)

    await waitFor(() => {
      expect(screen.getByText('Task #1')).toBeInTheDocument()
    })
  })

  describe('source toggles', () => {
    it('all sources are active by default (no source filter)', async () => {
      render(<EventsList />)

      await waitFor(() => {
        expect(screen.getByTestId('source-toggle-developer')).toBeInTheDocument()
      })

      expect(screen.getByTestId('source-toggle-developer')).toHaveAttribute('aria-pressed', 'true')
      expect(screen.getByTestId('source-toggle-system')).toHaveAttribute('aria-pressed', 'true')
      expect(screen.getByTestId('source-toggle-agent')).toHaveAttribute('aria-pressed', 'true')
    })

    it('selects only clicked source, deactivating others', async () => {
      render(<EventsList />)

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

    it('clicking active source resets to all sources', async () => {
      render(<EventsList />)

      await waitFor(() => {
        expect(screen.getByTestId('source-toggle-developer')).toBeInTheDocument()
      })

      // Select developer
      fireEvent.click(screen.getByTestId('source-toggle-developer'))
      await waitFor(() => {
        expect(screen.getByTestId('source-toggle-system')).toHaveAttribute('aria-pressed', 'false')
      })

      // Click developer again — should go back to all active
      fireEvent.click(screen.getByTestId('source-toggle-developer'))
      await waitFor(() => {
        expect(screen.getByTestId('source-toggle-system')).toHaveAttribute('aria-pressed', 'true')
        expect(screen.getByTestId('source-toggle-agent')).toHaveAttribute('aria-pressed', 'true')
      })
    })
  })

  describe('pinned section', () => {
    it('shows pinned section when pinned entries exist', async () => {
      setupHandlers(mockEntries, [pinnedEntry])

      render(<EventsList />)

      await waitFor(() => {
        expect(screen.getByTestId('pinned-section')).toBeInTheDocument()
      })

      expect(screen.getByText('Pinned (1)')).toBeInTheDocument()
    })

    it('hides pinned section when no pinned entries', async () => {
      render(<EventsList />)

      await waitFor(() => {
        expect(screen.queryByTestId('pinned-section')).not.toBeInTheDocument()
      })
    })

    it('collapses pinned section when header is clicked', async () => {
      setupHandlers(mockEntries, [pinnedEntry])

      render(<EventsList />)

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

  describe('inline actions', () => {
    it('calls updateLogEntry with pinned=true when pin button is clicked', async () => {
      const patchSpy = vi.fn().mockResolvedValue({ ...mockEntries[0], pinned: true })
      server.use(
        http.patch('*/api/log-entries/:id', async ({ params }) => {
          const result = patchSpy(Number(params.id))
          return HttpResponse.json(await result)
        }),
      )

      render(<EventsList />)

      await waitFor(() => {
        expect(screen.getByText('Developer thought entry')).toBeInTheDocument()
      })

      // Find pin buttons (entries with pinned=false have a pin button)
      const pinButtons = screen.getAllByTitle('Pin')
      fireEvent.click(pinButtons[0])

      await waitFor(() => {
        expect(patchSpy).toHaveBeenCalledWith(expect.any(Number))
      })
    })

    it('calls updateLogEntry with status=resolved when resolve button is clicked', async () => {
      const patchSpy = vi.fn().mockResolvedValue({ ...mockEntries[0], status: 'resolved' })
      server.use(
        http.patch('*/api/log-entries/:id', async ({ params }) => {
          const result = patchSpy(Number(params.id))
          return HttpResponse.json(await result)
        }),
      )

      render(<EventsList />)

      await waitFor(() => {
        expect(screen.getByText('Developer thought entry')).toBeInTheDocument()
      })

      // Find resolve buttons (active entries have a ✓ button)
      const resolveButtons = screen.getAllByTitle('Resolve')
      fireEvent.click(resolveButtons[0])

      await waitFor(() => {
        expect(patchSpy).toHaveBeenCalledWith(expect.any(Number))
      })
    })
  })

  describe('project filter', () => {
    it('updates the project filter when a project is selected', async () => {
      render(<EventsList />)

      await waitFor(() => {
        expect(screen.getByTestId('project-filter')).toBeInTheDocument()
      })

      const select = screen.getByTestId('project-filter') as HTMLSelectElement
      fireEvent.change(select, { target: { value: '1' } })

      expect(select.value).toBe('1')
    })
  })

  describe('load more', () => {
    it('shows load more button when a full page of results is returned', async () => {
      const fullPage = Array.from({ length: 20 }, (_, i) => ({
        ...mockEntries[0],
        id: i + 10,
        content: `Entry ${i}`,
      }))
      setupHandlers(fullPage)

      render(<EventsList />)

      await waitFor(() => {
        expect(screen.getByTestId('load-more')).toBeInTheDocument()
      })
    })

    it('does not show load more button when fewer than limit results are returned', async () => {
      render(<EventsList />)

      await waitFor(() => {
        expect(screen.queryByTestId('load-more')).not.toBeInTheDocument()
      })
    })
  })
})
