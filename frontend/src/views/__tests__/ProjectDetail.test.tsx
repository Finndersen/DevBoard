import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
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
import { useUIStore } from '../../stores/uiStore'
import { useConversationStore } from '../../stores/conversationStore'

vi.mock('../../contexts/ViewContext', () => ({
  useViewContext: () => ({ viewId: 'test-view', viewType: 'project', entityId: '1' })
}))

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
            model: {
              id: 'openai:gpt-4',
              provider: 'openai',
              name: 'GPT-4',
              model_type: 'standard'
            }
          },
          available_engines: [
            {
              engine: 'internal',
              display_name: 'Internal',
              description: 'Internal agent framework',
              requires_model_selection: true,
              is_available: true,
              unavailable_reason: null
            }
          ],
          enabled_mcp_tools: [],
          model_type_display_names: {
            fast: 'openai:gpt-3.5-turbo',
            standard: 'openai:gpt-4',
            advanced: 'anthropic:claude-opus-4.1'
          }
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
      }),
      http.get('*/api/log-entries', () => {
        return HttpResponse.json([])
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
    expect(screen.getByText('Events')).toBeInTheDocument()
    expect(screen.getByText('Settings')).toBeInTheDocument()
  })

  it('can switch to events tab', async () => {
    const user = userEvent.setup()
    renderProjectDetail()

    await waitFor(() => {
      expect(screen.getByText('Test Project')).toBeInTheDocument()
    })

    // Click on Events tab
    const eventsTab = screen.getByText('Events')
    await user.click(eventsTab)

    // Verify the tab is active (has blue styling)
    expect(eventsTab).toHaveClass('border-blue-500')
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


  it('shows events tab content when clicked', async () => {
    const user = userEvent.setup()
    renderProjectDetail()

    await waitFor(() => {
      expect(screen.getByText('Test Project')).toBeInTheDocument()
    })

    await user.click(screen.getByText('Events'))

    await waitFor(() => {
      expect(screen.getByTestId('filter-bar')).toBeInTheDocument()
    })
  })

  it('displays project content on home tab', async () => {
    renderProjectDetail()

    await waitFor(() => {
      expect(screen.getByText('Test Project')).toBeInTheDocument()
    })

    // Should show specification section on the home tab
    expect(screen.getByText('Project Context')).toBeInTheDocument()

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
    expect(screen.getByText('Project Context')).toBeInTheDocument()
    
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

  describe('handleDeleteConversation', () => {
    const mockConv1 = {
      id: 1,
      title: 'Conversation 1',
      agent_role: 'project',
      engine: 'internal',
      model_id: 'openai:gpt-4',
      parent_entity_type: 'project',
      parent_entity_id: 1,
      is_active: true,
      last_activity_at: '2024-01-01T00:00:00Z',
      created_at: '2024-01-01T00:00:00Z',
      updated_at: '2024-01-01T00:00:00Z',
    }
    const mockConv2 = {
      id: 2,
      title: 'Conversation 2',
      agent_role: 'project',
      engine: 'internal',
      model_id: 'openai:gpt-4',
      parent_entity_type: 'project',
      parent_entity_id: 1,
      is_active: true,
      last_activity_at: '2024-01-02T00:00:00Z',
      created_at: '2024-01-02T00:00:00Z',
      updated_at: '2024-01-02T00:00:00Z',
    }

    let mockRemoveConversation: ReturnType<typeof vi.fn>
    let mockInvalidateConversations: ReturnType<typeof vi.fn>
    let originalRemoveConversation: (conversationId: number) => void
    let originalInvalidateConversations: () => void

    beforeEach(() => {
      mockRemoveConversation = vi.fn()
      mockInvalidateConversations = vi.fn()

      originalRemoveConversation = useConversationStore.getState().removeConversation
      originalInvalidateConversations = useUIStore.getState().invalidateConversations

      useConversationStore.setState({ removeConversation: mockRemoveConversation })
      useUIStore.setState({ invalidateConversations: mockInvalidateConversations })

      server.use(
        http.get('*/api/projects/1/conversations', () => {
          return HttpResponse.json([mockConv1, mockConv2])
        }),
        http.delete('*/api/conversations/:id', () => new HttpResponse(null, { status: 204 }))
      )
    })

    afterEach(() => {
      useConversationStore.setState({ removeConversation: originalRemoveConversation })
      useUIStore.setState({ invalidateConversations: originalInvalidateConversations })
    })

    it('deleting a non-active conversation calls invalidateConversations and removeConversation', async () => {
      const user = userEvent.setup()

      renderProjectDetail()
      await waitFor(() => expect(screen.getByText('Test Project')).toBeInTheDocument())

      // Open conversation selector dropdown (trigger shows active conversation title)
      const selectorButton = await screen.findByRole('button', { name: /conversation 1/i })
      await user.click(selectorButton)

      // Click delete on conversation 2 (non-active, second in list)
      const deleteButtons = await screen.findAllByTitle('Delete')
      await user.click(deleteButtons[1])

      await waitFor(() => {
        expect(mockRemoveConversation).toHaveBeenCalledWith(2)
        expect(mockInvalidateConversations).toHaveBeenCalled()
      })
    })

    it('deleting the active conversation invalidates, cleans store, and switches to default', async () => {
      const user = userEvent.setup()
      const mockProjectAfterDelete = createMockProject({ id: 1, name: 'Test Project', default_conversation_id: 2 })

      let projectFetchCount = 0
      server.use(
        http.get('*/api/projects/:id', () => {
          projectFetchCount++
          if (projectFetchCount > 1) return HttpResponse.json(mockProjectAfterDelete)
          return HttpResponse.json(mockProject)
        })
      )

      renderProjectDetail()
      await waitFor(() => expect(screen.getByText('Test Project')).toBeInTheDocument())

      // Open selector and delete the active conversation (id=1)
      const selectorButton = await screen.findByRole('button', { name: /conversation 1/i })
      await user.click(selectorButton)

      const deleteButtons = await screen.findAllByTitle('Delete')
      await user.click(deleteButtons[0])

      await waitFor(() => {
        expect(mockRemoveConversation).toHaveBeenCalledWith(1)
        expect(mockInvalidateConversations).toHaveBeenCalled()
      })
    })

    it('failed deletion does not call invalidateConversations or removeConversation', async () => {
      const user = userEvent.setup()

      server.use(
        http.delete('*/api/conversations/:id', () => new HttpResponse(null, { status: 500 }))
      )

      renderProjectDetail()
      await waitFor(() => expect(screen.getByText('Test Project')).toBeInTheDocument())

      const selectorButton = await screen.findByRole('button', { name: /conversation 1/i })
      await user.click(selectorButton)

      const deleteButtons = await screen.findAllByTitle('Delete')
      await user.click(deleteButtons[0])

      // Give async handler time to complete and confirm no calls were made
      await waitFor(() => expect(screen.getByText('Test Project')).toBeInTheDocument())
      await new Promise(resolve => setTimeout(resolve, 100))

      expect(mockInvalidateConversations).not.toHaveBeenCalled()
      expect(mockRemoveConversation).not.toHaveBeenCalled()
    })
  })
})