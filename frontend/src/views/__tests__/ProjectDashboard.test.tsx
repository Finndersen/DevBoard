import { describe, it, expect, beforeEach, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { server } from '../../test/setup'
import { render, createMockProject } from '../../test/utils'
import ProjectDashboard from '../ProjectDashboard'

describe('ProjectDashboard', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    // Set up default empty projects response
    server.use(
      http.get('*/api/projects', () => {
        return HttpResponse.json([])
      })
    )
  })

  it('renders dashboard header and components', async () => {
    render(<ProjectDashboard />)
    
    await waitFor(() => {
      expect(screen.getByText('Projects')).toBeInTheDocument()
    }, { timeout: 3000 })
    
    // Should have at least one New Project button
    expect(screen.getAllByRole('button', { name: /new project/i }).length).toBeGreaterThan(0)
  })

  it('shows empty state when no projects exist', async () => {
    render(<ProjectDashboard />)

    await waitFor(() => {
      expect(screen.getByText(/No projects/i)).toBeInTheDocument()
    }, { timeout: 3000 })
  })

  it('loads and displays projects when they exist', async () => {
    const mockProjects = [
      createMockProject({ id: 1, name: 'Project 1', current_status: 'Active' }),
    ]

    server.use(
      http.get('*/api/projects', () => {
        return HttpResponse.json(mockProjects)
      })
    )

    render(<ProjectDashboard />)

    await waitFor(() => {
      expect(screen.getByText('Project 1')).toBeInTheDocument()
    }, { timeout: 3000 })
  })
})