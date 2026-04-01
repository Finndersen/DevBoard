import { describe, it, expect, beforeEach, vi } from 'vitest'
import { screen, waitFor, render } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { BrowserRouter } from 'react-router-dom'
import userEvent from '@testing-library/user-event'
import { server } from '../../test/setup'
import { createMockProject, createMockTask, mockDocuments } from '../../test/utils'
import { PendingMessagesProvider } from '../../contexts/PendingMessagesContext'
import ConversationEventHandlerProvider from '../../components/chat/ConversationEventHandlerProvider'
import TaskDetail from '../TaskDetail'

vi.mock('../../contexts/ViewContext', () => ({
  useViewContext: () => ({ viewId: 'test-view', viewType: 'task', entityId: '1' })
}))

// Helper to create NDJSON streaming response
const createStreamingResponse = (events: unknown[]) => {
  const ndjson = events.map(e => JSON.stringify(e)).join('\n') + '\n'
  return new HttpResponse(ndjson, {
    headers: { 'Content-Type': 'text/plain' }
  })
}

// Helper function to render TaskDetail with providers
const renderTaskDetail = (taskId: string = '1') => {
  return render(
    <PendingMessagesProvider>
      <ConversationEventHandlerProvider>
        <BrowserRouter>
          <TaskDetail id={taskId} />
        </BrowserRouter>
      </ConversationEventHandlerProvider>
    </PendingMessagesProvider>
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
      http.get('*/api/tasks/:id', ({ params }) => {
        if (params.id === '999') {
          return new HttpResponse(null, { status: 404 })
        }
        return HttpResponse.json(mockTask)
      }),
      http.get('*/api/projects/:id', () => {
        return HttpResponse.json(mockProject)
      }),
      http.get('*/api/documents/:id', ({ params }) => {
        const docId = Number(params.id)
        const doc = mockDocuments[docId as keyof typeof mockDocuments]
        if (doc) {
          return HttpResponse.json(doc)
        }
        return new HttpResponse(null, { status: 404 })
      }),
      http.get('*/api/tasks/:id/qa/history', () => {
        return HttpResponse.json([])
      }),
      http.get('*/api/conversations/*/messages', () => {
        return HttpResponse.json([])
      }),
      http.get('*/api/tasks/:id/git-status', () => {
        return HttpResponse.json({
          branch_name: null,
          branch_exists: false,
          base_branch: 'main',
          commits_ahead: 0,
          commits_behind: 0,
          can_merge: false,
          has_conflicts: false,
          worktree_slot: null,
        })
      }),
      http.get('*/api/codebases', () => {
        return HttpResponse.json([])
      }),
      http.post('*/api/tasks/:id/workflow-action', () => {
        return HttpResponse.json({ success: true })
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
      expect(screen.getByText('Planning')).toBeInTheDocument()
    }, { timeout: 3000 })
  })

  it('fetches project data for the task', async () => {
    renderTaskDetail()

    // Task should load successfully with project reference
    await waitFor(() => {
      expect(screen.getByText('Test Task')).toBeInTheDocument()
    }, { timeout: 3000 })

    // Verify task status is displayed (project data enables navigation on delete)
    expect(screen.getAllByText('Planning').length).toBeGreaterThan(0)
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

  it('displays "No codebase" when no codebase is assigned', async () => {
    server.use(
      http.get('*/api/codebases', () => {
        return HttpResponse.json([])
      })
    )

    renderTaskDetail()

    await waitFor(() => {
      expect(screen.getByText('No codebase')).toBeInTheDocument()
    }, { timeout: 3000 })
  })

  it('streams workflow action when transitioning to planning state', async () => {
    const user = userEvent.setup()
    const mockCodebase = {
      id: 1,
      name: 'Test Codebase',
      local_path: '/path/to/codebase',
    }
    const taskWithSpecification = createMockTask({
      id: 1,
      project_id: 1,
      status: 'Defining',
      codebase_id: 1,
      available_workflow_actions: [
        { key: 'task.create_implementation_plan' }
      ],
    })

    server.use(
      http.get('*/api/tasks/1', () => {
        return HttpResponse.json(taskWithSpecification)
      }),
      http.get('*/api/codebases', () => {
        return HttpResponse.json([mockCodebase])
      }),
      http.post('*/api/tasks/1/workflow-action', () => {
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
      const button = screen.queryByText('Create Implementation Plan')
      expect(button).toBeInTheDocument()
    }, { timeout: 3000 })

    const beginPlanningButton = screen.getByText('Create Implementation Plan')
    await user.click(beginPlanningButton)

    // Wait for the stream to complete
    await waitFor(() => {
      // Component should remain functional after streaming
      expect(screen.getByText('Test task specification content')).toBeInTheDocument()
    }, { timeout: 3000 })
  })

  it('refreshes git status after synchronous workflow action (no conversation_id)', async () => {
    const user = userEvent.setup()
    const taskWithAction = createMockTask({
      id: 1,
      project_id: 1,
      status: 'Planning',
      available_workflow_actions: [
        { key: 'task.begin_implementation' }
      ],
    })

    let gitStatusCallCount = 0

    server.use(
      http.get('*/api/tasks/1', () => {
        return HttpResponse.json(taskWithAction)
      }),
      http.get('*/api/tasks/1/git-status', () => {
        gitStatusCallCount++
        return HttpResponse.json({
          branch_name: null,
          branch_exists: false,
          base_branch: 'main',
          commits_ahead: 0,
          commits_behind: 0,
          can_merge: false,
          has_conflicts: false,
          worktree_slot: null,
        })
      }),
      http.post('*/api/tasks/1/workflow-action', () => {
        // Return without conversation_id to simulate synchronous completion
        return HttpResponse.json({ status: 'completed' })
      })
    )

    renderTaskDetail()

    // Wait for the action button to appear
    await waitFor(() => {
      expect(screen.getByText('Begin Implementation')).toBeInTheDocument()
    }, { timeout: 3000 })

    const callsBeforeAction = gitStatusCallCount

    // Click the workflow action button
    const actionButton = screen.getByText('Begin Implementation')
    await user.click(actionButton)

    // Verify git status was refreshed after the synchronous action
    await waitFor(() => {
      expect(gitStatusCallCount).toBeGreaterThan(callsBeforeAction)
    }, { timeout: 3000 })
  })

  it('handles streaming errors during workflow action gracefully', async () => {
    const user = userEvent.setup()
    const mockCodebase = {
      id: 1,
      name: 'Test Codebase',
      local_path: '/path/to/codebase',
    }
    const taskWithSpecification = createMockTask({
      id: 1,
      project_id: 1,
      status: 'Defining',
      codebase_id: 1,
      available_workflow_actions: [
        { key: 'task.create_implementation_plan' }
      ],
    })

    server.use(
      http.get('*/api/tasks/1', () => {
        return HttpResponse.json(taskWithSpecification)
      }),
      http.get('*/api/codebases', () => {
        return HttpResponse.json([mockCodebase])
      }),
      http.post('*/api/tasks/1/workflow-action', () => {
        return new HttpResponse(null, { status: 500 })
      })
    )

    renderTaskDetail()

    // Wait for the Planning button to appear
    await waitFor(() => {
      const button = screen.queryByText('Create Implementation Plan')
      expect(button).toBeInTheDocument()
    }, { timeout: 3000 })

    const beginPlanningButton = screen.getByText('Create Implementation Plan')
    await user.click(beginPlanningButton)

    // Verify component continues to function despite error
    await waitFor(() => {
      expect(screen.getByText('Test task specification content')).toBeInTheDocument()
    }, { timeout: 3000 })
  })

  describe('Task Deletion with Branch Management', () => {
    it('shows branch deletion checkbox when task has a branch', async () => {
      const user = userEvent.setup()
      const taskWithBranch = createMockTask({
        id: 1,
        project_id: 1,
        codebase_id: 1,
        title: 'Test Task',
        branch_name: 'feature/test-branch',
      })

      const gitStatus = {
        branch_name: 'feature/test-branch',
        branch_exists: true,
        base_branch: 'main',
        commits_ahead: 0,
        commits_behind: 0,
        can_merge: true,
        has_conflicts: false,
        worktree_slot: null,
      }

      server.use(
        http.get('*/api/tasks/1', () => {
          return HttpResponse.json(taskWithBranch)
        }),
        http.get('*/api/tasks/1/git-status', () => {
          return HttpResponse.json(gitStatus)
        })
      )

      renderTaskDetail()

      // Wait for task to load
      await waitFor(() => {
        expect(screen.getByText('Test Task')).toBeInTheDocument()
      }, { timeout: 3000 })

      // Find and click delete button in task header (the first one, not the confirm button)
      const deleteButtons = screen.getAllByRole('button', { name: /delete task/i })
      await user.click(deleteButtons[0])

      // Wait for git status to load and dialog to appear
      await waitFor(() => {
        expect(screen.getByText(/also delete git branch/i)).toBeInTheDocument()
      }, { timeout: 3000 })

      // Verify checkbox is present and checked by default
      const checkbox = screen.getByRole('checkbox', { name: /also delete git branch/i })
      expect(checkbox).toBeInTheDocument()
      expect(checkbox).toBeChecked()
      expect(checkbox).not.toBeDisabled()

      // Verify branch name is displayed
      expect(screen.getByText(/"feature\/test-branch"/)).toBeInTheDocument()
    })

    it('shows warning when branch has unmerged commits', async () => {
      const user = userEvent.setup()
      const taskWithBranch = createMockTask({
        id: 1,
        project_id: 1,
        codebase_id: 1,
        title: 'Test Task',
        branch_name: 'feature/test-branch',
      })

      const gitStatus = {
        branch_name: 'feature/test-branch',
        branch_exists: true,
        base_branch: 'main',
        commits_ahead: 3,
        commits_behind: 0,
        can_merge: true,
        has_conflicts: false,
        worktree_slot: null,
      }

      server.use(
        http.get('*/api/tasks/1', () => {
          return HttpResponse.json(taskWithBranch)
        }),
        http.get('*/api/tasks/1/git-status', () => {
          return HttpResponse.json(gitStatus)
        })
      )

      renderTaskDetail()

      // Wait for task to load
      await waitFor(() => {
        expect(screen.getByText('Test Task')).toBeInTheDocument()
      }, { timeout: 3000 })

      // Open delete dialog (click header button, not confirm button)
      const deleteButtons = screen.getAllByRole('button', { name: /delete task/i })
      await user.click(deleteButtons[0])

      // Should show warning about unmerged commits
      await waitFor(() => {
        expect(screen.getByText(/branch has 3 unmerged commits/i)).toBeInTheDocument()
      }, { timeout: 3000 })
    })

    it('shows warning with singular "commit" when branch has 1 unmerged commit', async () => {
      const user = userEvent.setup()
      const taskWithBranch = createMockTask({
        id: 1,
        project_id: 1,
        codebase_id: 1,
        title: 'Test Task',
        branch_name: 'feature/test-branch',
      })

      const gitStatus = {
        branch_name: 'feature/test-branch',
        branch_exists: true,
        base_branch: 'main',
        commits_ahead: 1,
        commits_behind: 0,
        can_merge: true,
        has_conflicts: false,
        worktree_slot: null,
      }

      server.use(
        http.get('*/api/tasks/1', () => {
          return HttpResponse.json(taskWithBranch)
        }),
        http.get('*/api/tasks/1/git-status', () => {
          return HttpResponse.json(gitStatus)
        })
      )

      renderTaskDetail()

      // Wait for task to load
      await waitFor(() => {
        expect(screen.getByText('Test Task')).toBeInTheDocument()
      }, { timeout: 3000 })

      // Open delete dialog (click header button, not confirm button)
      const deleteButtons = screen.getAllByRole('button', { name: /delete task/i })
      await user.click(deleteButtons[0])

      // Should show warning with singular "commit"
      await waitFor(() => {
        expect(screen.getByText(/branch has 1 unmerged commit$/i)).toBeInTheDocument()
      }, { timeout: 3000 })
    })

    it('calls deleteTask API with delete_branch=true when checkbox is checked', async () => {
      const user = userEvent.setup()
      const taskWithBranch = createMockTask({
        id: 1,
        project_id: 1,
        codebase_id: 1,
        title: 'Test Task',
        branch_name: 'feature/test-branch',
      })

      const gitStatus = {
        branch_name: 'feature/test-branch',
        branch_exists: true,
        base_branch: 'main',
        commits_ahead: 0,
        commits_behind: 0,
        can_merge: true,
        has_conflicts: false,
        worktree_slot: null,
      }

      const deleteCalls: Array<{ url: string; deleteBranch: string | null }> = []

      server.use(
        http.get('*/api/tasks/1', () => {
          return HttpResponse.json(taskWithBranch)
        }),
        http.get('*/api/tasks/1/git-status', () => {
          return HttpResponse.json(gitStatus)
        }),
        http.delete('*/api/tasks/1', ({ request }) => {
          const url = new URL(request.url)
          const deleteBranch = url.searchParams.get('delete_branch')
          deleteCalls.push({ url: request.url, deleteBranch })
          return HttpResponse.json({ success: true, message: 'Task deleted successfully' })
        })
      )

      renderTaskDetail()

      // Wait for task to load
      await waitFor(() => {
        expect(screen.getByText('Test Task')).toBeInTheDocument()
      }, { timeout: 3000 })

      // Open delete dialog (click header button, not confirm button)
      let deleteButtons = screen.getAllByRole('button', { name: /delete task/i })
      await user.click(deleteButtons[0])

      // Wait for git status to load and checkbox to appear
      await waitFor(() => {
        expect(screen.getByText(/also delete git branch/i)).toBeInTheDocument()
      }, { timeout: 3000 })

      // Verify checkbox is checked by default
      const checkbox = screen.getByRole('checkbox', { name: /also delete git branch/i })
      expect(checkbox).toBeChecked()

      // Confirm deletion (checkbox is checked by default) - get buttons again after dialog is open
      deleteButtons = screen.getAllByRole('button', { name: /delete task/i })
      await user.click(deleteButtons[1])

      // Verify API was called with delete_branch=true
      await waitFor(() => {
        expect(deleteCalls.length).toBeGreaterThan(0)
        // Check if any call has delete_branch=true
        const callWithDeleteBranch = deleteCalls.find(call => call.deleteBranch === 'true')
        expect(callWithDeleteBranch).toBeDefined()
      }, { timeout: 3000 })
    })

    it('calls deleteTask API without delete_branch parameter when checkbox is unchecked', async () => {
      const user = userEvent.setup()
      const taskWithBranch = createMockTask({
        id: 1,
        project_id: 1,
        codebase_id: 1,
        title: 'Test Task',
        branch_name: 'feature/test-branch',
      })

      const gitStatus = {
        branch_name: 'feature/test-branch',
        branch_exists: true,
        base_branch: 'main',
        commits_ahead: 0,
        commits_behind: 0,
        can_merge: true,
        has_conflicts: false,
        worktree_slot: null,
      }

      const deleteCalls: Array<{ url: string; deleteBranch: string | null }> = []

      server.use(
        http.get('*/api/tasks/1', () => {
          return HttpResponse.json(taskWithBranch)
        }),
        http.get('*/api/tasks/1/git-status', () => {
          return HttpResponse.json(gitStatus)
        }),
        http.delete('*/api/tasks/1', ({ request }) => {
          const url = new URL(request.url)
          const deleteBranch = url.searchParams.get('delete_branch')
          deleteCalls.push({ url: request.url, deleteBranch })
          return HttpResponse.json({ success: true, message: 'Task deleted successfully' })
        })
      )

      renderTaskDetail()

      // Wait for task to load
      await waitFor(() => {
        expect(screen.getByText('Test Task')).toBeInTheDocument()
      }, { timeout: 3000 })

      // Open delete dialog (click header button, not confirm button)
      let deleteButtons = screen.getAllByRole('button', { name: /delete task/i })
      await user.click(deleteButtons[0])

      // Wait for git status to load and checkbox to appear
      await waitFor(() => {
        expect(screen.getByText(/also delete git branch/i)).toBeInTheDocument()
      }, { timeout: 3000 })

      // Uncheck the checkbox
      const checkbox = screen.getByRole('checkbox', { name: /also delete git branch/i })
      await user.click(checkbox)
      expect(checkbox).not.toBeChecked()

      // Confirm deletion - get buttons again after dialog is open
      deleteButtons = screen.getAllByRole('button', { name: /delete task/i })
      await user.click(deleteButtons[1])

      // Verify API was called without delete_branch parameter
      await waitFor(() => {
        expect(deleteCalls.length).toBeGreaterThan(0)
        // Check that at least one call has deleteBranch=null
        const callWithoutDeleteBranch = deleteCalls.find(call => call.deleteBranch === null)
        expect(callWithoutDeleteBranch).toBeDefined()
      }, { timeout: 3000 })
    })

    it('does not show branch deletion checkbox when branch does not exist', async () => {
      const user = userEvent.setup()
      const taskWithBranch = createMockTask({
        id: 1,
        project_id: 1,
        codebase_id: 1,
        title: 'Test Task',
        branch_name: 'feature/test-branch',
      })

      const gitStatus = {
        branch_name: 'feature/test-branch',
        branch_exists: false,
        base_branch: 'main',
        commits_ahead: 0,
        commits_behind: 0,
        can_merge: false,
        has_conflicts: false,
        worktree_slot: null,
      }

      server.use(
        http.get('*/api/tasks/1', () => {
          return HttpResponse.json(taskWithBranch)
        }),
        http.get('*/api/tasks/1/git-status', () => {
          return HttpResponse.json(gitStatus)
        })
      )

      renderTaskDetail()

      // Wait for task to load
      await waitFor(() => {
        expect(screen.getByText('Test Task')).toBeInTheDocument()
      }, { timeout: 3000 })

      // Open delete dialog (click header button, not confirm button)
      const deleteButtons = screen.getAllByRole('button', { name: /delete task/i })
      await user.click(deleteButtons[0])

      // Wait for dialog to appear
      await waitFor(() => {
        expect(screen.getByText(/are you sure you want to delete/i)).toBeInTheDocument()
      }, { timeout: 3000 })

      // Verify checkbox is not present
      const checkbox = screen.queryByRole('checkbox', { name: /also delete git branch/i })
      expect(checkbox).not.toBeInTheDocument()

      // Verify message about non-existent branch is shown
      expect(screen.getByText(/branch "feature\/test-branch" does not exist/i)).toBeInTheDocument()
    })

    it('does not show branch deletion checkbox when task has no branch', async () => {
      const user = userEvent.setup()
      const taskWithoutBranch = createMockTask({
        id: 1,
        project_id: 1,
        title: 'Test Task',
        branch_name: null,
      })

      server.use(
        http.get('*/api/tasks/1', () => {
          return HttpResponse.json(taskWithoutBranch)
        }),
        http.get('*/api/tasks/1/git-status', () => {
          return new HttpResponse(null, { status: 404 })
        })
      )

      renderTaskDetail()

      // Wait for task to load
      await waitFor(() => {
        expect(screen.getByText('Test Task')).toBeInTheDocument()
      }, { timeout: 3000 })

      // Open delete dialog (click header button, not confirm button)
      const deleteButtons = screen.getAllByRole('button', { name: /delete task/i })
      await user.click(deleteButtons[0])

      // Wait for dialog to appear
      await waitFor(() => {
        expect(screen.getByText(/are you sure you want to delete/i)).toBeInTheDocument()
      }, { timeout: 3000 })

      // Verify checkbox is not present
      const checkbox = screen.queryByRole('checkbox', { name: /also delete git branch/i })
      expect(checkbox).not.toBeInTheDocument()
    })
  })
})