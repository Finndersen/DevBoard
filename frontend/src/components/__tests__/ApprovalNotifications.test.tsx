import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import { BrowserRouter } from 'react-router-dom'
import ApprovalNotifications from '../ApprovalNotifications'

// Mock the useApprovals hook for testing
const mockApprovalsState = {
  approvals: {
    'project-1': [
      {
        tool_call_id: 'test-1',
        tool_name: 'edit_task_specification',
        document_type: 'task_specification',
        reasoning: 'Test reasoning',
        edits: [{ find: 'old', replace: 'new' }],
        diff_preview: null
      }
    ],
    'task-2': [
      {
        tool_call_id: 'test-2',
        tool_name: 'edit_implementation_plan',
        document_type: 'implementation_plan',
        reasoning: 'Another test',
        edits: [{ find: 'old2', replace: 'new2' }],
        diff_preview: null
      },
      {
        tool_call_id: 'test-3',
        tool_name: 'edit_implementation_plan',
        document_type: 'implementation_plan',
        reasoning: 'Third test',
        edits: [{ find: 'old3', replace: 'new3' }],
        diff_preview: null
      }
    ]
  }
}

vi.mock('../../contexts/ApprovalsContext', async () => {
  const actual = await vi.importActual('../../contexts/ApprovalsContext')
  return {
    ...actual,
    useApprovals: () => ({
      state: mockApprovalsState,
      setApprovals: vi.fn(),
      addApproval: vi.fn(),
      removeApproval: vi.fn(),
      clearApprovals: vi.fn(),
      getApprovals: vi.fn(),
      hasApprovals: vi.fn()
    })
  }
})

const renderWithRouter = (component: React.ReactElement) => {
  return render(
    <BrowserRouter>
      {component}
    </BrowserRouter>
  )
}

describe('ApprovalNotifications', () => {
  it('shows notification when there are pending approvals', () => {
    renderWithRouter(<ApprovalNotifications />)

    expect(screen.getByText('3 Pending Approvals')).toBeInTheDocument()
    expect(screen.getByText('You have document edit approvals awaiting your decision:')).toBeInTheDocument()
  })

  it('shows project and task links with approval counts', () => {
    renderWithRouter(<ApprovalNotifications />)

    expect(screen.getByText('Project 1: 1 approval')).toBeInTheDocument()
    expect(screen.getByText('Task 2: 2 approvals')).toBeInTheDocument()
  })

  it('creates correct navigation links', () => {
    renderWithRouter(<ApprovalNotifications />)

    const projectLink = screen.getByRole('link', { name: /project 1: 1 approval/i })
    const taskLink = screen.getByRole('link', { name: /task 2: 2 approvals/i })

    expect(projectLink).toHaveAttribute('href', '/projects/1')
    expect(taskLink).toHaveAttribute('href', '/tasks/2')
  })
})

describe('ApprovalNotifications with no pending approvals', () => {
  it('does not render when there are no pending approvals', () => {
    // Override mock for this test
    vi.mocked(vi.importActual('../../contexts/ApprovalsContext')).mockImplementation(async () => ({
      ...await vi.importActual('../../contexts/ApprovalsContext'),
      useApprovals: () => ({
        state: { approvals: {} },
        setApprovals: vi.fn(),
        addApproval: vi.fn(),
        removeApproval: vi.fn(),
        clearApprovals: vi.fn(),
        getApprovals: vi.fn(),
        hasApprovals: vi.fn()
      })
    }))

    renderWithRouter(<ApprovalNotifications />)

    expect(screen.queryByText(/pending approval/i)).not.toBeInTheDocument()
  })
})