import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { ApprovalsProvider, useApprovals } from '../../contexts/ApprovalsContext'
import { createProjectApprovalKey } from '../../utils/approvalKeys'
import type { PendingApproval } from '../../lib/api'

// Mock localStorage
const localStorageMock = {
  getItem: vi.fn(),
  setItem: vi.fn(),
  removeItem: vi.fn(),
  clear: vi.fn(),
}
Object.defineProperty(window, 'localStorage', {
  value: localStorageMock
})

const TestComponent = () => {
  const { getApprovals, setApprovals, hasApprovals, clearApprovals } = useApprovals()
  const projectKey = createProjectApprovalKey(1)
  const approvals = getApprovals(projectKey)

  const addTestApproval = () => {
    const testApproval: PendingApproval = {
      tool_call_id: 'test-123',
      tool_name: 'edit_task_specification',
      document_type: 'task_specification',
      reasoning: 'Test approval',
      edits: [{ find: 'old', replace: 'new' }],
      diff_preview: null
    }
    setApprovals(projectKey, [testApproval])
  }

  return (
    <div>
      <div data-testid="approval-count">{approvals.length}</div>
      <div data-testid="has-approvals">{hasApprovals(projectKey) ? 'true' : 'false'}</div>
      <button onClick={addTestApproval}>Add Approval</button>
      <button onClick={() => clearApprovals(projectKey)}>Clear Approvals</button>
      {approvals.map(approval => (
        <div key={approval.tool_call_id} data-testid="approval-item">
          {approval.tool_name}: {approval.reasoning}
        </div>
      ))}
    </div>
  )
}

describe('ApprovalsContext', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorageMock.getItem.mockReturnValue(null)
  })

  it('provides approval state management', () => {
    render(
      <ApprovalsProvider>
        <TestComponent />
      </ApprovalsProvider>
    )

    expect(screen.getByTestId('approval-count')).toHaveTextContent('0')
    expect(screen.getByTestId('has-approvals')).toHaveTextContent('false')
  })

  it('allows adding and clearing approvals', () => {
    render(
      <ApprovalsProvider>
        <TestComponent />
      </ApprovalsProvider>
    )

    // Add approval
    fireEvent.click(screen.getByText('Add Approval'))
    
    expect(screen.getByTestId('approval-count')).toHaveTextContent('1')
    expect(screen.getByTestId('has-approvals')).toHaveTextContent('true')
    expect(screen.getByTestId('approval-item')).toHaveTextContent('edit_task_specification: Test approval')

    // Clear approval
    fireEvent.click(screen.getByText('Clear Approvals'))
    
    expect(screen.getByTestId('approval-count')).toHaveTextContent('0')
    expect(screen.getByTestId('has-approvals')).toHaveTextContent('false')
  })

  it('saves to localStorage when state changes', () => {
    render(
      <ApprovalsProvider>
        <TestComponent />
      </ApprovalsProvider>
    )

    fireEvent.click(screen.getByText('Add Approval'))

    // Should save to localStorage
    expect(localStorageMock.setItem).toHaveBeenCalledWith(
      'devboard_pending_approvals',
      expect.stringContaining('project-1')
    )
  })

  it('loads from localStorage on mount', () => {
    const savedState = {
      'project-1': [
        {
          tool_call_id: 'saved-123',
          tool_name: 'edit_implementation_plan',
          document_type: 'implementation_plan',
          reasoning: 'Saved approval',
          edits: [{ find: 'saved', replace: 'loaded' }],
          diff_preview: null
        }
      ]
    }
    localStorageMock.getItem.mockReturnValue(JSON.stringify(savedState))

    render(
      <ApprovalsProvider>
        <TestComponent />
      </ApprovalsProvider>
    )

    expect(screen.getByTestId('approval-count')).toHaveTextContent('1')
    expect(screen.getByTestId('approval-item')).toHaveTextContent('edit_implementation_plan: Saved approval')
  })

  it('handles localStorage errors gracefully', () => {
    localStorageMock.getItem.mockImplementation(() => {
      throw new Error('localStorage error')
    })

    // Should not throw
    expect(() => {
      render(
        <ApprovalsProvider>
          <TestComponent />
        </ApprovalsProvider>
      )
    }).not.toThrow()

    expect(screen.getByTestId('approval-count')).toHaveTextContent('0')
  })
})