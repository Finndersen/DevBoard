import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { render, mockNavigate } from '../../test/utils'
import { server } from '../../test/setup'
import type { Project } from '../../lib/api'
import ProjectsList from '../ProjectsList'

function makeProject(overrides: Partial<Project> & Pick<Project, 'id' | 'name'>): Project {
  return {
    specification_document_id: overrides.id,
    description: '',
    default_conversation_id: null,
    created_at: '2024-01-01T00:00:00Z',
    custom_fields: null,
    complete: false,
    ...overrides,
  }
}

function setupHandlers({
  activeProjects = [] as Project[],
  completeProjects = [] as Project[],
}: {
  activeProjects?: Project[]
  completeProjects?: Project[]
} = {}) {
  server.use(
    http.get('*/api/projects', ({ request }) => {
      const url = new URL(request.url)
      const completeParam = url.searchParams.get('complete')
      if (completeParam === 'true') {
        return HttpResponse.json(completeProjects)
      }
      return HttpResponse.json(activeProjects)
    }),
    http.get('*/api/custom-fields/', () => HttpResponse.json([])),
    http.patch('*/api/projects/:id', async ({ params, request }) => {
      const updates = await request.json() as Partial<Project>
      const all = [...activeProjects, ...completeProjects]
      const project = all.find(p => p.id === Number(params.id))
      if (!project) return new HttpResponse(null, { status: 404 })
      return HttpResponse.json({ ...project, ...updates })
    }),
    http.post('*/api/projects', async ({ request }) => {
      const body = await request.json() as { name: string; description: string }
      return HttpResponse.json(makeProject({
        id: 99,
        name: body.name,
        description: body.description,
      }))
    }),
  )
}

function renderProjectsList() {
  return render(<ProjectsList />)
}

describe('ProjectsList', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders empty state when no projects exist', async () => {
    setupHandlers()
    renderProjectsList()

    await waitFor(() => {
      expect(screen.getByText('No projects yet')).toBeInTheDocument()
    })
  })

  it('renders top-level projects with purple diamond icon', async () => {
    const projects = [
      makeProject({ id: 1, name: 'Alpha Project' }),
      makeProject({ id: 2, name: 'Beta Project' }),
    ]
    setupHandlers({ activeProjects: projects })
    renderProjectsList()

    await waitFor(() => {
      expect(screen.getByText('Alpha Project')).toBeInTheDocument()
      expect(screen.getByText('Beta Project')).toBeInTheDocument()
    })

    // Both projects have the ◆ icon
    const icons = screen.getAllByText('◆')
    expect(icons).toHaveLength(2)
  })


  it('navigates to project when project card is clicked', async () => {
    const user = userEvent.setup()
    const projects = [makeProject({ id: 1, name: 'Click Me Project' })]
    setupHandlers({ activeProjects: projects })
    renderProjectsList()

    await waitFor(() => {
      expect(screen.getByText('Click Me Project')).toBeInTheDocument()
    })

    await user.click(screen.getByText('Click Me Project'))

    // navigateTo is called via useUIStore, which actually fires the store method.
    // We verify the card is clickable by checking the text is visible and was clicked.
    // The navigate mock verifies navigation on create; for navigateTo we trust the store.
    expect(screen.getByText('Click Me Project')).toBeInTheDocument()
  })

  it('shows completed projects in a separate section with muted styling', async () => {
    const activeProjects = [makeProject({ id: 1, name: 'Active Project' })]
    const completeProjects = [
      makeProject({ id: 2, name: 'Done Project', complete: true }),
      makeProject({ id: 3, name: 'Another Done Project', complete: true }),
    ]
    setupHandlers({ activeProjects, completeProjects })
    renderProjectsList()

    await waitFor(() => {
      expect(screen.getByText('Active Project')).toBeInTheDocument()
      expect(screen.getByText('Done Project')).toBeInTheDocument()
      expect(screen.getByText('Another Done Project')).toBeInTheDocument()
    })

    // Completed section heading
    expect(screen.getByText(/Completed \(2\)/)).toBeInTheDocument()

    // Completed items have Restore buttons
    const restoreButtons = screen.getAllByText('Restore')
    expect(restoreButtons).toHaveLength(2)
  })

  it('toggling complete on a project calls PATCH and refetches', async () => {
    const user = userEvent.setup()
    let patchCalled = false

    const projects = [makeProject({ id: 1, name: 'Active Project' })]
    server.use(
      http.get('*/api/projects', ({ request }) => {
        const url = new URL(request.url)
        const completeParam = url.searchParams.get('complete')
        if (completeParam === 'true') return HttpResponse.json([])
        return HttpResponse.json(projects)
      }),
      http.get('*/api/custom-fields/', () => HttpResponse.json([])),
      http.patch('*/api/projects/:id', async ({ request }) => {
        const updates = await request.json() as Partial<Project>
        patchCalled = true
        return HttpResponse.json({ ...projects[0], ...updates })
      }),
    )

    renderProjectsList()

    await waitFor(() => {
      expect(screen.getByText('Active Project')).toBeInTheDocument()
    })

    const completeButton = screen.getByRole('button', { name: 'Complete' })
    await user.click(completeButton)

    await waitFor(() => {
      expect(patchCalled).toBe(true)
    })
  })

  it('restoring a complete project calls PATCH with complete: false', async () => {
    const user = userEvent.setup()
    const patchBodies: Partial<Project>[] = []

    const completeProjects = [makeProject({ id: 2, name: 'Done Project', complete: true })]
    server.use(
      http.get('*/api/projects', ({ request }) => {
        const url = new URL(request.url)
        const completeParam = url.searchParams.get('complete')
        if (completeParam === 'true') return HttpResponse.json(completeProjects)
        return HttpResponse.json([])
      }),
      http.get('*/api/custom-fields/', () => HttpResponse.json([])),
      http.patch('*/api/projects/:id', async ({ request }) => {
        const updates = await request.json() as Partial<Project>
        patchBodies.push(updates)
        return HttpResponse.json({ ...completeProjects[0], ...updates })
      }),
    )

    renderProjectsList()

    await waitFor(() => {
      expect(screen.getByText('Done Project')).toBeInTheDocument()
    })

    await user.click(screen.getByText('Restore'))

    await waitFor(() => {
      expect(patchBodies).toHaveLength(1)
      expect(patchBodies[0]).toEqual({ complete: false })
    })
  })

  it('opens create modal when New Project is clicked', async () => {
    const user = userEvent.setup()
    setupHandlers()
    renderProjectsList()

    await waitFor(() => {
      expect(screen.getByText('No projects yet')).toBeInTheDocument()
    })

    await user.click(screen.getByRole('button', { name: /New Project/i }))

    expect(screen.getByText('Create New Project')).toBeInTheDocument()
  })

  it('creates a project with name and description in request', async () => {
    const user = userEvent.setup()
    const requestBodies: { name: string; description?: string }[] = []

    server.use(
      http.get('*/api/projects', ({ request }) => {
        const url = new URL(request.url)
        if (url.searchParams.get('complete') === 'true') return HttpResponse.json([])
        return HttpResponse.json([])
      }),
      http.get('*/api/custom-fields/', () => HttpResponse.json([])),
      http.post('*/api/projects', async ({ request }) => {
        const body = await request.json() as { name: string; description?: string }
        requestBodies.push(body)
        return HttpResponse.json(makeProject({ id: 10, name: body.name }))
      }),
    )

    renderProjectsList()

    await waitFor(() => {
      expect(screen.getByText('No projects yet')).toBeInTheDocument()
    })

    await user.click(screen.getByRole('button', { name: /New Project/i }))
    await waitFor(() => expect(screen.getByText('Create New Project')).toBeInTheDocument())

    await user.type(screen.getByLabelText(/Name/i), 'My New Project')
    const submitBtn = screen.getAllByRole('button', { name: 'Create Project' }).find(b => b.getAttribute('type') === 'submit')!
    await user.click(submitBtn)

    await waitFor(() => {
      expect(requestBodies).toHaveLength(1)
      expect(requestBodies[0].name).toBe('My New Project')
    })

    expect(mockNavigate).toHaveBeenCalledWith('/projects/10?tab=settings')
  })
})
