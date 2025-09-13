import { describe, it, expect, beforeEach, vi } from 'vitest'
import { screen, waitFor, render } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { server } from '../../test/setup'
import { createMockProject, createMockTask } from '../../test/utils'
import ProjectDetail from '../ProjectDetail'

// Helper function to render ProjectDetail with proper routing
const renderProjectDetail = (projectId: string = '1') => {
  return render(
    <MemoryRouter initialEntries={[`/projects/${projectId}`]}>
      <Routes>
        <Route path="/projects/:id" element={<ProjectDetail />} />
      </Routes>
    </MemoryRouter>
  )
}

describe('ProjectDetail', () => {
  const mockProject = createMockProject({
    id: 1,
    name: 'Test Project',
    specification: 'This is a test project for development',
  })

  const mockTasks = [
    createMockTask({ id: 1, title: 'Task 1', status: 'Pending' }),
    createMockTask({ id: 2, title: 'Task 2', status: 'Planning' }),
  ]

  beforeEach(() => {
    vi.clearAllMocks()
    // Mock scrollIntoView which is not available in jsdom
    Element.prototype.scrollIntoView = vi.fn()
    
    // Setup default API responses
    server.use(
      http.get('*/api/projects/1', () => {
        return HttpResponse.json(mockProject)
      }),
      http.get('*/api/projects/1/tasks', () => {
        return HttpResponse.json(mockTasks)
      }),
      http.get('*/api/projects/1/qa/history', () => {
        return HttpResponse.json([])
      })
    )
  })

  it('renders project information', async () => {
    renderProjectDetail()
    
    await waitFor(() => {
      expect(screen.getByText('Test Project')).toBeInTheDocument()
    }, { timeout: 3000 })
    
    // Project should be rendered with basic information
    expect(screen.getByText('Board')).toBeInTheDocument()
  })

  it('renders tasks list', async () => {
    renderProjectDetail()
    
    await waitFor(() => {
      expect(screen.getByText('Task 1')).toBeInTheDocument()
      expect(screen.getByText('Task 2')).toBeInTheDocument()
    }, { timeout: 3000 })
  })

  it('handles missing project gracefully', async () => {
    server.use(
      http.get('*/api/projects/999', () => {
        return new HttpResponse(null, { status: 404 })
      })
    )

    renderProjectDetail('999')
    
    await waitFor(() => {
      expect(screen.getByText('Project not found')).toBeInTheDocument()
    }, { timeout: 3000 })
  })
})