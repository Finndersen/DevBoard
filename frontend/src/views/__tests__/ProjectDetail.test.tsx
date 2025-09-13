import { describe, it, expect, beforeEach, vi } from 'vitest'
import { screen, waitFor, render } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import userEvent from '@testing-library/user-event'
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
      }),
      http.get('*/api/settings/agents/project/model', () => {
        return HttpResponse.json({ model_id: 'openai/gpt-4' })
      })
    )
  })

  it('renders project information', async () => {
    renderProjectDetail()
    
    await waitFor(() => {
      expect(screen.getByText('Test Project')).toBeInTheDocument()
    }, { timeout: 3000 })
    
    // Project should be rendered with basic information and navigation tabs
    expect(screen.getByText('Board')).toBeInTheDocument()
    expect(screen.getByText('Collaborative Editor')).toBeInTheDocument()
    expect(screen.getByText('Settings')).toBeInTheDocument()
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

  it('switches to collaborative editor tab and displays side-by-side layout', async () => {
    const user = userEvent.setup()
    renderProjectDetail()
    
    await waitFor(() => {
      expect(screen.getByText('Test Project')).toBeInTheDocument()
    }, { timeout: 3000 })
    
    // Click on the Collaborative Editor tab
    const editorTab = screen.getByText('Collaborative Editor')
    await user.click(editorTab)
    
    // Should show project details section
    await waitFor(() => {
      expect(screen.getByText('Project Details')).toBeInTheDocument()
    })
    
    // Should show specification section
    expect(screen.getByText('Project Specification')).toBeInTheDocument()
    
    // Should show Q&A Agent section
    expect(screen.getByText('Q&A Agent')).toBeInTheDocument()
    
    // Should show the specification content
    expect(screen.getByText('This is a test project for development')).toBeInTheDocument()
  })

  it('allows editing specification in collaborative editor tab', async () => {
    const user = userEvent.setup()
    renderProjectDetail()
    
    await waitFor(() => {
      expect(screen.getByText('Test Project')).toBeInTheDocument()
    }, { timeout: 3000 })
    
    // Click on the Collaborative Editor tab
    const editorTab = screen.getByText('Collaborative Editor')
    await user.click(editorTab)
    
    await waitFor(() => {
      expect(screen.getByText('Project Specification')).toBeInTheDocument()
    })
    
    // Click edit button
    const editButton = screen.getByText('Edit')
    await user.click(editButton)
    
    // Should show textarea for editing
    const textarea = screen.getByPlaceholderText('Enter project specification in Markdown format...')
    expect(textarea).toBeInTheDocument()
    expect(textarea).toHaveValue('This is a test project for development')
    
    // Should show save and cancel buttons
    expect(screen.getByText('Save')).toBeInTheDocument()
    expect(screen.getByText('Cancel')).toBeInTheDocument()
  })

  it('displays agent model information in collaborative editor', async () => {
    const user = userEvent.setup()
    renderProjectDetail()
    
    await waitFor(() => {
      expect(screen.getByText('Test Project')).toBeInTheDocument()
    }, { timeout: 3000 })
    
    // Click on the Collaborative Editor tab
    const editorTab = screen.getByText('Collaborative Editor')
    await user.click(editorTab)
    
    await waitFor(() => {
      expect(screen.getByText('Agent')).toBeInTheDocument()
    })
    
    // Should display the model information
    await waitFor(() => {
      expect(screen.getByText('Model: openai/gpt-4')).toBeInTheDocument()
    })
  })
})