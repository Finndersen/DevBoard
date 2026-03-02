import { describe, it, expect, beforeEach, vi } from 'vitest'
import { screen, waitFor, render as rtlRender } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { BrowserRouter } from 'react-router-dom'
import userEvent from '@testing-library/user-event'
import { server } from '../../test/setup'
import { createMockProject, createMockTask, mockDocuments } from '../../test/utils'
import { PendingMessagesProvider } from '../../contexts/PendingMessagesContext'
import { DarkModeProvider } from '../../contexts/DarkModeContext'
import ConversationEventHandlerProvider from '../../components/chat/ConversationEventHandlerProvider'
import ProjectDetail from '../ProjectDetail'

// Helper function to render ProjectDetail with proper routing
const renderProjectDetail = (projectId: string = '1') => {
  return rtlRender(
    <DarkModeProvider>
      <PendingMessagesProvider>
        <ConversationEventHandlerProvider>
          <BrowserRouter>
            <ProjectDetail id={projectId} />
          </BrowserRouter>
        </ConversationEventHandlerProvider>
      </PendingMessagesProvider>
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
      http.get('*/api/projects/:id', ({ params }) => {
        if (params.id === '999') {
          return new HttpResponse(null, { status: 404 })
        }
        return HttpResponse.json(mockProject)
      }),
      http.get('*/api/projects/:id/tasks', () => {
        return HttpResponse.json(mockTasks)
      }),
      http.get('*/api/documents/:id', ({ params }) => {
        const docId = Number(params.id)
        const doc = mockDocuments[docId as keyof typeof mockDocuments]
        if (doc) {
          return HttpResponse.json(doc)
        }
        return new HttpResponse(null, { status: 404 })
      }),
      http.get('*/api/projects/:id/qa/history', () => {
        return HttpResponse.json([])
      }),
      http.get('*/api/projects/:id/codebases', () => {
        return HttpResponse.json([])
      }),
      http.get('*/api/conversations/:id', ({ params }) => {
        return HttpResponse.json({
          id: Number(params.id),
          agent_role: 'qa',
          engine: 'internal',
          model_id: 'openai:gpt-4',
          created_at: '2024-01-01T00:00:00Z',
          updated_at: '2024-01-01T00:00:00Z'
        })
      }),
      http.get('*/api/conversations/*/messages', () => {
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
      }),
      http.get('*/api/models/by-engine', () => {
        return HttpResponse.json({
          models_by_engine: {
            internal: [
              {
                id: 'openai:gpt-4',
                name: 'GPT-4',
                provider: 'openai',
                model_type: 'chat'
              }
            ]
          }
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
    expect(screen.getByText('Settings')).toBeInTheDocument()
  })

  it('can switch to settings tab', async () => {
    const user = userEvent.setup()
    renderProjectDetail()

    await waitFor(() => {
      expect(screen.getByText('Test Project')).toBeInTheDocument()
    })

    // Click on Settings tab
    const settingsTab = screen.getByText('Settings')
    await user.click(settingsTab)

    // Verify the tab is active (has blue styling)
    expect(settingsTab).toHaveClass('border-blue-500')
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

    // Should show the specification content (fetched asynchronously)
    await waitFor(() => {
      expect(screen.getByText('Test project specification content')).toBeInTheDocument()
    }, { timeout: 3000 })
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

    // Should have a chat input for asking questions
    await waitFor(() => {
      expect(screen.getByPlaceholderText('Ask a question about this project...')).toBeInTheDocument()
    }, { timeout: 3000 })
  })
})