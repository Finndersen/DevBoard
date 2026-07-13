import React from 'react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, waitFor, fireEvent } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { render } from '../../test/utils'
import { server } from '../../test/setup'
import { ViewContextProvider } from '../../contexts/ViewContext'
import type { TaskListItem, TaskCountsResponse, PaginatedTaskListResponse, Project } from '../../lib/api'
import { TaskStatus } from '../../lib/api'
import TasksList from '../TasksList'

// Fixture helpers
function makeTaskListItem(overrides: Partial<TaskListItem> & Pick<TaskListItem, 'id' | 'title' | 'status'>): TaskListItem {
  return {
    project_id: 1,
    project_name: 'Test Project',
    codebase_id: 1,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    initiative_id: null,
    initiative_name: null,
    ...overrides,
  }
}

const mockActiveTasks: TaskListItem[] = [
  makeTaskListItem({ id: 10, title: 'Planning Task', status: TaskStatus.PLANNING }),
  makeTaskListItem({ id: 11, title: 'Implementing Task', status: TaskStatus.IMPLEMENTING }),
  makeTaskListItem({ id: 12, title: 'PR Open Task', status: TaskStatus.PR_OPEN }),
  makeTaskListItem({ id: 13, title: 'Merged Task', status: TaskStatus.MERGED }),
]

const mockArchivedTasks: TaskListItem[] = [
  makeTaskListItem({ id: 101, title: 'Complete Task One', status: TaskStatus.COMPLETE, project_name: 'Test Project', created_at: '2026-05-01T00:00:00Z' }),
  makeTaskListItem({ id: 102, title: 'Complete Task Two', status: TaskStatus.COMPLETE, project_name: 'Another Project', created_at: '2026-04-15T00:00:00Z' }),
]

const mockTaskCounts: TaskCountsResponse = {
  [TaskStatus.PLANNING]: 1,
  [TaskStatus.IMPLEMENTING]: 1,
  [TaskStatus.PR_OPEN]: 1,
  [TaskStatus.MERGED]: 1,
  [TaskStatus.COMPLETE]: 47,
}

function makeArchivedResponse(items: TaskListItem[], total: number, page = 1, pageSize = 20): PaginatedTaskListResponse {
  return { items, total, page, page_size: pageSize }
}

function setupHandlers({
  activeTasks = mockActiveTasks,
  archivedResponse = makeArchivedResponse(mockArchivedTasks, 2),
  counts = mockTaskCounts,
  projects,
}: {
  activeTasks?: TaskListItem[]
  archivedResponse?: PaginatedTaskListResponse
  counts?: TaskCountsResponse
  projects?: Project[]
} = {}) {
  const handlers = [
    http.get('*/api/tasks', () => HttpResponse.json(activeTasks)),
    http.get('*/api/tasks/counts', () => HttpResponse.json(counts)),
    http.get('*/api/tasks/archived', () => HttpResponse.json(archivedResponse)),
    http.get('*/api/github/open-prs', () => HttpResponse.json({ prs: [], errors: [] })),
  ]
  if (projects !== undefined) {
    handlers.push(
      http.get('*/api/projects', () => HttpResponse.json(projects))
    )
  }
  server.use(...handlers)
}

function renderTasksList() {
  return render(
    <ViewContextProvider viewId="tasks-list-view" viewType="tasks-list" entityId="">
      <TasksList />
    </ViewContextProvider>
  )
}

describe('TasksList', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    setupHandlers()
  })

  describe('Active tab — kanban', () => {
    it('renders Active tab by default', async () => {
      renderTasksList()
      await waitFor(() => {
        expect(screen.getByText('Active')).toBeInTheDocument()
      })
      expect(screen.getByText('Archived')).toBeInTheDocument()
    })

    it('shows MERGED task in the MERGED column', async () => {
      renderTasksList()
      await waitFor(() => {
        expect(screen.getByText('Merged Task')).toBeInTheDocument()
      })
      expect(screen.getByText('Merged')).toBeInTheDocument()
    })

    it('shows tasks in correct columns', async () => {
      renderTasksList()
      await waitFor(() => {
        expect(screen.getByText('Planning Task')).toBeInTheDocument()
      })
      expect(screen.getByText('Implementing Task')).toBeInTheDocument()
      expect(screen.getByText('PR Open Task')).toBeInTheDocument()
      expect(screen.getByText('Merged Task')).toBeInTheDocument()
    })

    it('does not show COMPLETE column heading on active tab', async () => {
      renderTasksList()
      await waitFor(() => {
        expect(screen.getByText('Merged')).toBeInTheDocument()
      })
      expect(screen.queryByRole('heading', { name: /complete/i })).not.toBeInTheDocument()
    })

    it('does not show COMPLETE tasks in the kanban', async () => {
      setupHandlers({
        activeTasks: [
          ...mockActiveTasks,
          makeTaskListItem({ id: 99, title: 'Should Not Appear', status: TaskStatus.COMPLETE }),
        ],
      })
      renderTasksList()
      await waitFor(() => {
        expect(screen.getByText('Merged Task')).toBeInTheDocument()
      })
      // The COMPLETE task should not be visible because there is no COMPLETE column
      expect(screen.queryByText('Should Not Appear')).not.toBeInTheDocument()
    })

    it('shows "New Task" button on active tab', async () => {
      renderTasksList()
      await waitFor(() => {
        expect(screen.getByRole('button', { name: /new task/i })).toBeInTheDocument()
      })
    })
  })

  describe('Archived tab', () => {
    it('does NOT fetch archived tasks on initial render (lazy loading)', async () => {
      let archivedFetchCount = 0
      server.use(
        http.get('*/api/tasks/archived', () => {
          archivedFetchCount++
          return HttpResponse.json(makeArchivedResponse([], 0))
        }),
      )
      renderTasksList()
      // Wait for the active tasks to load
      await waitFor(() => {
        expect(screen.getByText('Planning Task')).toBeInTheDocument()
      })
      // Archived endpoint should NOT have been called yet
      expect(archivedFetchCount).toBe(0)
    })

    it('fetches and renders archived tasks when tab is clicked', async () => {
      renderTasksList()
      await waitFor(() => {
        expect(screen.getByText('Planning Task')).toBeInTheDocument()
      })

      fireEvent.click(screen.getByText('Archived'))

      await waitFor(() => {
        expect(screen.getByText('Complete Task One')).toBeInTheDocument()
      })
      expect(screen.getByText('Complete Task Two')).toBeInTheDocument()
    })

    it('keeps "New Task" button visible on archived tab', async () => {
      renderTasksList()
      await waitFor(() => {
        expect(screen.getByRole('button', { name: /new task/i })).toBeInTheDocument()
      })

      fireEvent.click(screen.getByText('Archived'))

      await waitFor(() => {
        expect(screen.getByText('Complete Task One')).toBeInTheDocument()
      })
      // Button should still be visible on archived tab
      expect(screen.getByRole('button', { name: /new task/i })).toBeInTheDocument()
    })

    it('shows archived count badge from task counts endpoint', async () => {
      renderTasksList()
      await waitFor(() => {
        // The archived tab badge should show 47 (from mockTaskCounts COMPLETE count)
        const archivedTab = screen.getByText('Archived').closest('button')
        expect(archivedTab?.textContent).toContain('47')
      })
    })

    it('shows pagination controls when there are multiple pages', async () => {
      setupHandlers({
        archivedResponse: makeArchivedResponse(mockArchivedTasks, 47, 1, 20),
      })
      renderTasksList()
      await waitFor(() => {
        expect(screen.getByText('Planning Task')).toBeInTheDocument()
      })

      fireEvent.click(screen.getByText('Archived'))

      await waitFor(() => {
        expect(screen.getByText(/Page 1 of/)).toBeInTheDocument()
      })
      expect(screen.getByRole('button', { name: /next/i })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /prev/i })).toBeInTheDocument()
    })

    it('navigates to page 2 when Next button is clicked', async () => {
      const page1Items = [makeTaskListItem({ id: 101, title: 'Archived Page 1', status: TaskStatus.COMPLETE })]
      const page2Items = [makeTaskListItem({ id: 201, title: 'Archived Page 2', status: TaskStatus.COMPLETE })]
      let currentPage = 1

      server.use(
        http.get('*/api/tasks/archived', ({ request }) => {
          const url = new URL(request.url)
          currentPage = Number(url.searchParams.get('page') ?? '1')
          const items = currentPage === 1 ? page1Items : page2Items
          return HttpResponse.json(makeArchivedResponse(items, 25, currentPage, 20))
        }),
      )

      renderTasksList()
      await waitFor(() => expect(screen.getByText('Planning Task')).toBeInTheDocument())

      fireEvent.click(screen.getByText('Archived'))
      await waitFor(() => expect(screen.getByText('Archived Page 1')).toBeInTheDocument())

      fireEvent.click(screen.getByRole('button', { name: /next/i }))
      await waitFor(() => expect(screen.getByText('Archived Page 2')).toBeInTheDocument())
      expect(currentPage).toBe(2)
    })

    it('shows empty state when no archived tasks', async () => {
      setupHandlers({ archivedResponse: makeArchivedResponse([], 0) })
      renderTasksList()
      await waitFor(() => expect(screen.getByText('Planning Task')).toBeInTheDocument())

      fireEvent.click(screen.getByText('Archived'))

      await waitFor(() => {
        expect(screen.getByText(/no archived tasks/i)).toBeInTheDocument()
      })
    })
  })

  describe('Task card project/initiative display', () => {
    it('shows purple project name when task has no initiative', async () => {
      setupHandlers({
        activeTasks: [makeTaskListItem({ id: 10, title: 'Direct Task', status: TaskStatus.PLANNING, project_name: 'My Project', initiative_id: null, initiative_name: null })],
      })
      renderTasksList()
      await waitFor(() => expect(screen.getByText('Direct Task')).toBeInTheDocument())
      const projectName = screen.getAllByText('My Project')[0]
      expect(projectName).toBeInTheDocument()
      expect(projectName.className).toMatch(/purple/)
      // No initiative separator
      expect(screen.queryByText('›')).not.toBeInTheDocument()
    })

    it('shows amber initiative name when task is in an initiative', async () => {
      setupHandlers({
        activeTasks: [makeTaskListItem({ id: 10, title: 'Initiative Task', status: TaskStatus.PLANNING, project_name: 'Parent Project', initiative_id: 5, initiative_name: 'My Initiative' })],
      })
      renderTasksList()
      await waitFor(() => expect(screen.getByText('Initiative Task')).toBeInTheDocument())
      // Both project and initiative inline text present
      expect(screen.getByText('Parent Project')).toBeInTheDocument()
      expect(screen.getByText('›')).toBeInTheDocument()
      const initiativeName = screen.getByText('My Initiative')
      expect(initiativeName).toBeInTheDocument()
      expect(initiativeName.className).toMatch(/amber/)
    })
  })

  describe('Project filter', () => {
    it('refetches active tasks when project filter changes', async () => {
      let lastProjectId: string | null = null
      server.use(
        http.get('*/api/tasks', ({ request }) => {
          const url = new URL(request.url)
          lastProjectId = url.searchParams.get('project_id')
          return HttpResponse.json(mockActiveTasks)
        }),
      )
      renderTasksList()
      await waitFor(() => expect(screen.getByText('Planning Task')).toBeInTheDocument())

      const select = screen.getByRole('combobox')
      fireEvent.change(select, { target: { value: '1' } })

      await waitFor(() => {
        expect(lastProjectId).toBe('1')
      })
    })

    it('refetches archived tasks when project changes while on archived tab', async () => {
      let archivedProjectId: string | null = null
      server.use(
        http.get('*/api/tasks/archived', ({ request }) => {
          const url = new URL(request.url)
          archivedProjectId = url.searchParams.get('project_id')
          return HttpResponse.json(makeArchivedResponse(mockArchivedTasks, 2))
        }),
      )

      renderTasksList()
      await waitFor(() => expect(screen.getByText('Planning Task')).toBeInTheDocument())

      // Open archived tab
      fireEvent.click(screen.getByText('Archived'))
      await waitFor(() => expect(screen.getByText('Complete Task One')).toBeInTheDocument())

      // Change project filter
      const select = screen.getByRole('combobox')
      fireEvent.change(select, { target: { value: '1' } })

      await waitFor(() => {
        expect(archivedProjectId).toBe('1')
      })
    })

    it('renders all projects as a flat list in the filter dropdown', async () => {
      const projects: Project[] = [
        { id: 1, name: 'Alpha Project', specification_document_id: 1, description: '', default_conversation_id: null, created_at: '2026-01-01T00:00:00Z', custom_fields: null, complete: false },
        { id: 2, name: 'Beta Project', specification_document_id: 2, description: '', default_conversation_id: null, created_at: '2026-01-01T00:00:00Z', custom_fields: null, complete: false },
      ]
      setupHandlers({ projects })
      renderTasksList()

      await waitFor(() => expect(screen.getByText('Planning Task')).toBeInTheDocument())

      const select = screen.getByRole('combobox')
      const options = select.querySelectorAll('option')
      const optionTexts = Array.from(options).map(o => o.textContent ?? '')

      // Both projects appear in the dropdown
      const alphaIdx = optionTexts.findIndex(t => t.includes('Alpha Project'))
      const betaIdx = optionTexts.findIndex(t => t.includes('Beta Project'))
      expect(alphaIdx).toBeGreaterThan(-1)
      expect(betaIdx).toBeGreaterThan(-1)
      expect(optionTexts[alphaIdx]).toContain('◆')
      expect(optionTexts[betaIdx]).toContain('◆')
      // No ▸ prefix in any option
      expect(optionTexts.every(t => !t.includes('▸'))).toBe(true)
    })
  })
})
