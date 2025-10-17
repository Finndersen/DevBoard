import { describe, it, expect, beforeEach, vi } from 'vitest'
import { screen, waitFor, render } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { server } from '../../test/setup'
import { createMockProject, createMockTask } from '../../test/utils'
import { ApprovalsProvider } from '../../contexts/ApprovalsContext'
import { PendingMessagesProvider } from '../../contexts/PendingMessagesContext'
import TaskDetail from '../TaskDetail'

// Helper function to render TaskDetail with proper routing
const renderTaskDetail = (taskId: string = '1') => {
  return render(
    <ApprovalsProvider>
      <PendingMessagesProvider>
        <MemoryRouter initialEntries={[`/tasks/${taskId}`]}>
          <Routes>
            <Route path="/tasks/:id" element={<TaskDetail />} />
          </Routes>
        </MemoryRouter>
      </PendingMessagesProvider>
    </ApprovalsProvider>
  )
}

describe('TaskDetail', () => {
  const mockTask = createMockTask({
    id: 1,
    project_id: 1,
    title: 'Test Task',
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
      }),
      http.get('*/api/conversations/*/messages', () => {
        return HttpResponse.json([])
      })
    )
  })

  it('renders task details', async () => {
    renderTaskDetail()

    await waitFor(() => {
      expect(screen.getByText('Test task specification content')).toBeInTheDocument()
    }, { timeout: 3000 })

    expect(screen.getAllByText('Planning').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Task Specification').length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText('Implementation Plan')).toBeInTheDocument()
    // Agent title is now dynamically loaded based on conversation's agent_role
    await waitFor(() => {
      expect(screen.getByText('Task Specification Agent')).toBeInTheDocument()
    }, { timeout: 3000 })
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
      expect(screen.getByText('API request failed: 404 Not Found')).toBeInTheDocument()
    }, { timeout: 3000 })
  })

  it('displays codebase information when assigned', async () => {
    const mockCodebase = {
      id: 1,
      name: 'Test Codebase',
      description: 'A test codebase',
      local_path: '/path/to/test/codebase',
      repository_url: 'https://github.com/test/repo',
    }

    const taskWithCodebase = createMockTask({
      id: 1,
      codebase_id: 1,
    })

    server.use(
      http.get('*/api/tasks/1', () => {
        return HttpResponse.json(taskWithCodebase)
      }),
      http.get('*/api/codebases', () => {
        return HttpResponse.json([mockCodebase])
      })
    )

    renderTaskDetail()

    await waitFor(() => {
      expect(screen.getByText('Test Codebase')).toBeInTheDocument()
    }, { timeout: 3000 })
  })

  it('displays "None" when no codebase is assigned', async () => {
    server.use(
      http.get('*/api/codebases', () => {
        return HttpResponse.json([])
      })
    )

    renderTaskDetail()

    await waitFor(() => {
      expect(screen.getByText('None')).toBeInTheDocument()
    }, { timeout: 3000 })
  })
})