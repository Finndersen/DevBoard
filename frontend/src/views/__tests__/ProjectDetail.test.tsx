import { describe, it, expect, beforeEach, vi } from 'vitest'
import { screen, waitFor, render as rtlRender } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { BrowserRouter } from 'react-router-dom'
import userEvent from '@testing-library/user-event'
import { server } from '../../test/setup'
import { createMockProject, createMockTask } from '../../test/utils'
import { ApprovalsProvider } from '../../contexts/ApprovalsContext'
import { PendingMessagesProvider } from '../../contexts/PendingMessagesContext'
import { DarkModeProvider } from '../../contexts/DarkModeContext'
import ProjectDetail from '../ProjectDetail'

// Helper function to render ProjectDetail with proper routing
const renderProjectDetail = (projectId: string = '1') => {
  return rtlRender(
    <DarkModeProvider>
      <ApprovalsProvider>
        <PendingMessagesProvider>
          <BrowserRouter>
            <ProjectDetail id={projectId} />
          </BrowserRouter>
        </PendingMessagesProvider>
      </ApprovalsProvider>
    </DarkModeProvider>
  )
}

describe('ProjectDetail', () => {
  const mockProject = createMockProject({
    id: 1,
    name: 'Test Project',
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
      }),
      http.get('*/api/agents/project/configuration', () => {
        return HttpResponse.json({
          agent_role: 'project',
          config: {
            engine: 'internal',
            model_id: 'openai:gpt-4'
          },
          available_engines: [
            {
              engine: 'internal',
              display_name: 'Internal',
              description: 'Internal agent framework'
            }
          ]
        })
      })
    )
  })

  it('renders project information', async () => {
    renderProjectDetail()
    
    await waitFor(() => {
      expect(screen.getByText('Test Project')).toBeInTheDocument()
    })
    
    // Project should be rendered with basic information and navigation tabs
    expect(screen.getByText('Home')).toBeInTheDocument()
    expect(screen.getByText('Tasks')).toBeInTheDocument()
    expect(screen.getByText('Settings')).toBeInTheDocument()
  })

  it('can switch to tasks tab', async () => {
    const user = userEvent.setup()
    renderProjectDetail()
    
    await waitFor(() => {
      expect(screen.getByText('Test Project')).toBeInTheDocument()
    })
    
    // Click on Tasks tab
    const tasksTab = screen.getByText('Tasks')
    await user.click(tasksTab)
    
    // Verify the tab is active (has blue styling)
    expect(tasksTab).toHaveClass('border-blue-500')
    
    // Should show tasks content area or at least not show the specification
    // (The exact content may vary depending on implementation)
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
    })
  })

  it('displays project content on home tab', async () => {
    renderProjectDetail()
    
    await waitFor(() => {
      expect(screen.getByText('Test Project')).toBeInTheDocument()
    })
    
    // Should show specification section on the home tab
    expect(screen.getByText('Project Specification')).toBeInTheDocument()
    
    // Should show the specification content
    expect(screen.getByText('Test project specification content')).toBeInTheDocument()
  })

  it('allows editing specification', async () => {
    const user = userEvent.setup()
    renderProjectDetail()
    
    await waitFor(() => {
      expect(screen.getByText('Test Project')).toBeInTheDocument()
    })
    
    // Should see the specification section on home tab
    expect(screen.getByText('Project Specification')).toBeInTheDocument()
    
    // Click edit button
    const editButton = screen.getByText('Edit')
    await user.click(editButton)
    
    // Should show textarea for editing
    await waitFor(() => {
      const textareas = screen.getAllByRole('textbox')
      expect(textareas.length).toBeGreaterThan(0)
      const textarea = textareas.find(ta => (ta as HTMLTextAreaElement).value === 'Test project specification content')
      expect(textarea).toBeInTheDocument()
      expect(textarea).toHaveValue('Test project specification content')
    })
    
    // Should show save and cancel buttons
    expect(screen.getByText('Save')).toBeInTheDocument()
    expect(screen.getByText('Cancel')).toBeInTheDocument()
  })

  it('displays Q&A chat interface', async () => {
    renderProjectDetail()
    
    await waitFor(() => {
      expect(screen.getByText('Test Project')).toBeInTheDocument()
    })
    
    // Should show Agent section in the right panel 
    expect(screen.getByText('Agent')).toBeInTheDocument()
    
    // Should have a chat input
    expect(screen.getByPlaceholderText('Ask a question about this project...')).toBeInTheDocument()
  })
})