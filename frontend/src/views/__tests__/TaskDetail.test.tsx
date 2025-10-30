import { describe, it, expect, beforeEach, vi } from 'vitest'
import { screen, waitFor, render } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { BrowserRouter } from 'react-router-dom'
import userEvent from '@testing-library/user-event'
import { server } from '../../test/setup'
import { createMockProject, createMockTask } from '../../test/utils'
import { ApprovalsProvider } from '../../contexts/ApprovalsContext'
import { PendingMessagesProvider } from '../../contexts/PendingMessagesContext'
import TaskDetail from '../TaskDetail'

// Helper to create NDJSON streaming response
const createStreamingResponse = (events: any[]) => {
  const ndjson = events.map(e => JSON.stringify(e)).join('\n') + '\n'
  return new HttpResponse(ndjson, {
    headers: { 'Content-Type': 'text/plain' }
  })
}

// Helper function to render TaskDetail with providers
const renderTaskDetail = (taskId: string = '1') => {
  return render(
    <ApprovalsProvider>
      <PendingMessagesProvider>
        <BrowserRouter>
          <TaskDetail id={taskId} />
        </BrowserRouter>
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

  it('streams prompt action when transitioning to planning state', async () => {
    const user = userEvent.setup()
    const taskWithSpecification = createMockTask({
      id: 1,
      project_id: 1,
      status: 'Defining',
      specification: {
        id: 3,
        document_type: 'task_specification',
        content: 'Test task specification content',
        content_hash: 'task123',
        created_at: '2024-01-01T00:00:00Z',
        updated_at: '2024-01-01T00:00:00Z',
      },
    })
    const updatedTask = createMockTask({
      id: 1,
      project_id: 1,
      status: 'Planning',
      specification: taskWithSpecification.specification,
    })

    server.use(
      http.get('*/api/tasks/1', () => {
        return HttpResponse.json(taskWithSpecification)
      }),
      http.post('*/api/tasks/1/state-transition', () => {
        return HttpResponse.json({
          ...updatedTask,
          conversation_id: 2,
        })
      }),
      http.post('*/api/conversations/2/prompt-action', () => {
        return createStreamingResponse([
          {
            event_type: 'message',
            role: 'agent',
            text_content: 'I will help you create an implementation plan.',
            timestamp: '2024-01-01T00:00:00Z',
          },
        ])
      })
    )

    renderTaskDetail()

    // Wait for the Planning button to appear
    await waitFor(() => {
      const button = screen.queryByText('Begin Planning')
      expect(button).toBeInTheDocument()
    }, { timeout: 3000 })

    const beginPlanningButton = screen.getByText('Begin Planning')
    await user.click(beginPlanningButton)

    // Wait for the stream to complete
    await waitFor(() => {
      // Component should remain functional after streaming
      expect(screen.getByText('Test task specification content')).toBeInTheDocument()
    }, { timeout: 3000 })
  })

  it('handles streaming errors during prompt action gracefully', async () => {
    const user = userEvent.setup()
    const taskWithSpecification = createMockTask({
      id: 1,
      project_id: 1,
      status: 'Defining',
      specification: {
        id: 3,
        document_type: 'task_specification',
        content: 'Test task specification content',
        content_hash: 'task123',
        created_at: '2024-01-01T00:00:00Z',
        updated_at: '2024-01-01T00:00:00Z',
      },
    })
    const updatedTask = createMockTask({
      id: 1,
      project_id: 1,
      status: 'Planning',
      specification: taskWithSpecification.specification,
    })

    server.use(
      http.get('*/api/tasks/1', () => {
        return HttpResponse.json(taskWithSpecification)
      }),
      http.post('*/api/tasks/1/state-transition', () => {
        return HttpResponse.json({
          ...updatedTask,
          conversation_id: 2,
        })
      }),
      http.post('*/api/conversations/2/prompt-action', () => {
        return new HttpResponse(null, { status: 404 })
      })
    )

    renderTaskDetail()

    // Wait for the Planning button to appear
    await waitFor(() => {
      const button = screen.queryByText('Begin Planning')
      expect(button).toBeInTheDocument()
    }, { timeout: 3000 })

    const beginPlanningButton = screen.getByText('Begin Planning')
    await user.click(beginPlanningButton)

    // Verify component continues to function despite error
    await waitFor(() => {
      expect(screen.getByText('Test task specification content')).toBeInTheDocument()
    }, { timeout: 3000 })
  })
})