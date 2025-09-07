import { describe, it, expect, beforeEach, vi } from 'vitest'
import { screen, waitFor, render } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { server } from '../../test/setup'
import { createMockProject, createMockTask } from '../../test/utils'
import TaskDetail from '../TaskDetail'

// Helper function to render TaskDetail with proper routing
const renderTaskDetail = (taskId: string = '1') => {
  return render(
    <MemoryRouter initialEntries={[`/tasks/${taskId}`]}>
      <Routes>
        <Route path="/tasks/:id" element={<TaskDetail />} />
      </Routes>
    </MemoryRouter>
  )
}

describe('TaskDetail', () => {
  const mockTask = createMockTask({
    id: 1,
    project_id: 1,
    title: 'Test Task',
    description: 'Test task description',
    status: 'Planning',
  })

  const mockProject = createMockProject({
    id: 1,
    name: 'Test Project',
  })

  beforeEach(() => {
    vi.clearAllMocks()
    // Mock scrollIntoView which is not available in jsdom
    Element.prototype.scrollIntoView = vi.fn()
    
    // Setup default API responses
    server.use(
      http.get('*/api/tasks/1', () => {
        return HttpResponse.json(mockTask)
      }),
      http.get('*/api/projects/1', () => {
        return HttpResponse.json(mockProject)
      }),
      http.get('*/api/tasks/1/qa/history', () => {
        return HttpResponse.json([])
      })
    )
  })

  it('renders task details', async () => {
    renderTaskDetail()
    
    await waitFor(() => {
      expect(screen.getByText('Test Task')).toBeInTheDocument()
    }, { timeout: 3000 })
    
    expect(screen.getByText('Test task description')).toBeInTheDocument()
    expect(screen.getAllByText('Planning').length).toBeGreaterThan(0)
  })

  it('renders project information', async () => {
    renderTaskDetail()
    
    await waitFor(() => {
      expect(screen.getAllByText('Test Project').length).toBeGreaterThan(0)
    }, { timeout: 3000 })
  })

  it('handles missing task gracefully', async () => {
    server.use(
      http.get('*/api/tasks/999', () => {
        return new HttpResponse(null, { status: 404 })
      })
    )

    renderTaskDetail('999')
    
    await waitFor(() => {
      expect(screen.getByText('Task not found')).toBeInTheDocument()
    }, { timeout: 3000 })
  })
})