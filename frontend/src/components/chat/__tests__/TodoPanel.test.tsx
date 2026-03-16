import { describe, it, expect, beforeEach, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { server } from '../../../test/setup'
import { render } from '../../../test/utils'
import TodoPanel from '../TodoPanel'
import ConversationEventHandlerProvider from '../ConversationEventHandlerProvider'

let capturedStreamCompleteHandler: (() => void) | null = null

vi.mock('../../../hooks/useConversationEventHandlers', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../../hooks/useConversationEventHandlers')>()
  return {
    ...actual,
    useStreamCompleteHandler: (handler: () => void) => {
      capturedStreamCompleteHandler = handler
    },
  }
})

describe('TodoPanel', () => {
  const mockConversationId = 1

  const mockTodos = [
    {
      content: 'Fix the bug',
      status: 'completed',
      active_form: 'Fixing the bug',
      priority: null,
      id: 'todo-1',
    },
    {
      content: 'Write tests',
      status: 'in_progress',
      active_form: 'Writing tests',
      priority: null,
      id: 'todo-2',
    },
    {
      content: 'Update docs',
      status: 'pending',
      active_form: 'Updating docs',
      priority: null,
      id: 'todo-3',
    },
  ]

  beforeEach(() => {
    capturedStreamCompleteHandler = null
    vi.clearAllMocks()
    server.resetHandlers()
  })

  const renderWithProvider = (ui: React.ReactElement) => {
    return render(
      <ConversationEventHandlerProvider>
        {ui}
      </ConversationEventHandlerProvider>
    )
  }

  it('does not render for non-claude_code engine', async () => {
    server.use(
      http.get('*/api/conversations/1/todos', () => {
        return HttpResponse.json(mockTodos)
      })
    )

    renderWithProvider(
      <TodoPanel conversationId={mockConversationId} engine="internal" />
    )

    // Should not make API call and should not render anything
    await waitFor(() => {
      expect(screen.queryByText(/Tasks:/)).not.toBeInTheDocument()
    })
  })

  it('does not render when no todos exist', async () => {
    server.use(
      http.get('*/api/conversations/1/todos', () => {
        return HttpResponse.json([])
      })
    )

    renderWithProvider(
      <TodoPanel conversationId={mockConversationId} engine="claude_code" />
    )

    await waitFor(() => {
      expect(screen.queryByText(/Tasks:/)).not.toBeInTheDocument()
    })
  })

  it('renders collapsed state with summary', async () => {
    server.use(
      http.get('*/api/conversations/1/todos', () => {
        return HttpResponse.json(mockTodos)
      })
    )

    renderWithProvider(
      <TodoPanel conversationId={mockConversationId} engine="claude_code" />
    )

    await waitFor(() => {
      expect(screen.getByText('Tasks: 1/3 completed')).toBeInTheDocument()
    })

    // Should show in-progress task in collapsed bar
    expect(screen.getByText(/Writing tests/)).toBeInTheDocument()
  })

  it('expands and shows all todos when clicked', async () => {
    const user = userEvent.setup()

    server.use(
      http.get('*/api/conversations/1/todos', () => {
        return HttpResponse.json(mockTodos)
      })
    )

    renderWithProvider(
      <TodoPanel conversationId={mockConversationId} engine="claude_code" />
    )

    await waitFor(() => {
      expect(screen.getByText('Tasks: 1/3 completed')).toBeInTheDocument()
    })

    // Click to expand
    const expandButton = screen.getByRole('button')
    await user.click(expandButton)

    // Should show all todos
    await waitFor(() => {
      expect(screen.getByText('Fix the bug')).toBeInTheDocument()
      expect(screen.getByText('Writing tests')).toBeInTheDocument()
      expect(screen.getByText('Update docs')).toBeInTheDocument()
    })
  })

  it('shows active_form for in_progress todos when expanded', async () => {
    const user = userEvent.setup()

    server.use(
      http.get('*/api/conversations/1/todos', () => {
        return HttpResponse.json(mockTodos)
      })
    )

    renderWithProvider(
      <TodoPanel conversationId={mockConversationId} engine="claude_code" />
    )

    await waitFor(() => {
      expect(screen.getByText('Tasks: 1/3 completed')).toBeInTheDocument()
    })

    // Click to expand
    const expandButton = screen.getByRole('button')
    await user.click(expandButton)

    // In-progress todo should show active_form, not content
    await waitFor(() => {
      // 'Writing tests' (active_form) should appear, not 'Write tests' (content)
      expect(screen.getByText('Writing tests')).toBeInTheDocument()
      // 'Write tests' should not appear in the expanded list
      const writeTestsElements = screen.queryAllByText('Write tests')
      expect(writeTestsElements).toHaveLength(0)
    })
  })

  it('collapses when clicked again', async () => {
    const user = userEvent.setup()

    server.use(
      http.get('*/api/conversations/1/todos', () => {
        return HttpResponse.json(mockTodos)
      })
    )

    renderWithProvider(
      <TodoPanel conversationId={mockConversationId} engine="claude_code" />
    )

    await waitFor(() => {
      expect(screen.getByText('Tasks: 1/3 completed')).toBeInTheDocument()
    })

    // Click to expand
    const expandButton = screen.getByRole('button')
    await user.click(expandButton)

    // Verify expanded
    await waitFor(() => {
      expect(screen.getByText('Fix the bug')).toBeInTheDocument()
    })

    // Click to collapse
    await user.click(expandButton)

    // Should hide individual todos (collapsed view won't show 'Fix the bug' as standalone)
    await waitFor(() => {
      // Check that the expanded list is hidden - Fix the bug should not be visible as a separate item
      const listItems = screen.queryByText('Fix the bug')
      // In collapsed state, individual todo items shouldn't be visible
      // The panel collapses and only shows summary
      expect(listItems).not.toBeInTheDocument()
    })
  })

  it('handles API errors gracefully', async () => {
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})

    server.use(
      http.get('*/api/conversations/1/todos', () => {
        return new HttpResponse(null, { status: 500 })
      })
    )

    renderWithProvider(
      <TodoPanel conversationId={mockConversationId} engine="claude_code" />
    )

    // Should log error but not crash
    await waitFor(() => {
      expect(consoleSpy).toHaveBeenCalledWith(
        'Failed to fetch todos:',
        expect.any(Error)
      )
    })

    // Panel should not render anything
    expect(screen.queryByText(/Tasks:/)).not.toBeInTheDocument()

    consoleSpy.mockRestore()
  })

  it('displays correct status indicators', async () => {
    const user = userEvent.setup()

    server.use(
      http.get('*/api/conversations/1/todos', () => {
        return HttpResponse.json(mockTodos)
      })
    )

    renderWithProvider(
      <TodoPanel conversationId={mockConversationId} engine="claude_code" />
    )

    await waitFor(() => {
      expect(screen.getByText('Tasks: 1/3 completed')).toBeInTheDocument()
    })

    // Click to expand
    const expandButton = screen.getByRole('button')
    await user.click(expandButton)

    await waitFor(() => {
      // Completed todo should have line-through styling
      const completedTodo = screen.getByText('Fix the bug')
      expect(completedTodo).toHaveClass('line-through')
    })
  })

  it('refreshes todos on stream complete for claude_code engine', async () => {
    capturedStreamCompleteHandler = null

    const initialTodos = [
      {
        content: 'Fix the bug',
        status: 'completed',
        active_form: 'Fixing the bug',
        priority: null,
        id: 'todo-1',
      },
      {
        content: 'Write tests',
        status: 'in_progress',
        active_form: 'Writing tests',
        priority: null,
        id: 'todo-2',
      },
      {
        content: 'Update docs',
        status: 'pending',
        active_form: 'Updating docs',
        priority: null,
        id: 'todo-3',
      },
    ]

    server.use(
      http.get('*/api/conversations/1/todos', () => {
        return HttpResponse.json(initialTodos)
      })
    )

    renderWithProvider(
      <TodoPanel conversationId={mockConversationId} engine="claude_code" />
    )

    await waitFor(() => {
      expect(screen.getByText('Tasks: 1/3 completed')).toBeInTheDocument()
    })

    // Update MSW handler to return updated todos (2 completed instead of 1)
    const updatedTodos = [
      {
        content: 'Fix the bug',
        status: 'completed',
        active_form: 'Fixing the bug',
        priority: null,
        id: 'todo-1',
      },
      {
        content: 'Write tests',
        status: 'completed',
        active_form: 'Writing tests',
        priority: null,
        id: 'todo-2',
      },
      {
        content: 'Update docs',
        status: 'in_progress',
        active_form: 'Updating docs',
        priority: null,
        id: 'todo-3',
      },
    ]

    server.use(
      http.get('*/api/conversations/1/todos', () => {
        return HttpResponse.json(updatedTodos)
      })
    )

    // Invoke the captured stream-complete handler to trigger refetch
    expect(capturedStreamCompleteHandler).not.toBeNull()
    capturedStreamCompleteHandler!()

    await waitFor(() => {
      expect(screen.getByText('Tasks: 2/3 completed')).toBeInTheDocument()
    })
  })
})
