import { render, screen, fireEvent, act, renderHook } from '@testing-library/react'
import { describe, it, expect, beforeEach } from 'vitest'
import { useApprovalsStore, useApprovalActions, useApprovals, useAllApprovals } from '../../stores/approvalsStore'
import { createProjectApprovalKey } from '../../utils/approvalKeys'
import { getReasoningFromToolArgs } from '../../utils/toolTypeUtils'
import type { PendingApproval } from '../../lib/api'

// Reset the Zustand store before each test
beforeEach(() => {
  // Clear the store state
  useApprovalsStore.setState({ approvals: {} })
})

const TestComponent = () => {
  const { setApprovals, clearApprovals, hasApprovals } = useApprovalActions()
  const projectKey = createProjectApprovalKey(1)
  const approvals = useApprovals(projectKey)

  const addTestApproval = () => {
    const testApproval: PendingApproval = {
      tool_call_id: 'test-123',
      tool_name: 'edit_task_specification',
      tool_args: {
        edits: [{ find: 'old', replace: 'new' }],
        reasoning: 'Test approval'
      }
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
          {approval.tool_name}: {getReasoningFromToolArgs(approval)}
        </div>
      ))}
    </div>
  )
}

describe('ApprovalsStore', () => {
  it('provides approval state management', () => {
    render(<TestComponent />)

    expect(screen.getByTestId('approval-count')).toHaveTextContent('0')
    expect(screen.getByTestId('has-approvals')).toHaveTextContent('false')
  })

  it('allows adding and clearing approvals', () => {
    render(<TestComponent />)

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

  it('deduplicates approvals with same IDs', () => {
    const { result } = renderHook(() => useApprovalActions())
    const projectKey = createProjectApprovalKey(1)

    const testApproval: PendingApproval = {
      tool_call_id: 'test-123',
      tool_name: 'edit_task_specification',
      tool_args: { edits: [], reasoning: 'Test' }
    }

    // Set approvals twice with same data
    act(() => {
      result.current.setApprovals(projectKey, [testApproval])
    })

    const stateAfterFirst = useApprovalsStore.getState().approvals[projectKey]

    act(() => {
      result.current.setApprovals(projectKey, [testApproval])
    })

    const stateAfterSecond = useApprovalsStore.getState().approvals[projectKey]

    // Should be the same reference (no update occurred)
    expect(stateAfterFirst).toBe(stateAfterSecond)
  })

  it('updates when approval IDs change', () => {
    const { result } = renderHook(() => useApprovalActions())
    const projectKey = createProjectApprovalKey(1)

    const testApproval1: PendingApproval = {
      tool_call_id: 'test-123',
      tool_name: 'edit_task_specification',
      tool_args: { edits: [], reasoning: 'Test 1' }
    }

    const testApproval2: PendingApproval = {
      tool_call_id: 'test-456',
      tool_name: 'edit_task_specification',
      tool_args: { edits: [], reasoning: 'Test 2' }
    }

    act(() => {
      result.current.setApprovals(projectKey, [testApproval1])
    })

    expect(useApprovalsStore.getState().approvals[projectKey]).toHaveLength(1)

    act(() => {
      result.current.setApprovals(projectKey, [testApproval1, testApproval2])
    })

    expect(useApprovalsStore.getState().approvals[projectKey]).toHaveLength(2)
  })

  it('useAllApprovals returns all approvals', () => {
    const testApproval: PendingApproval = {
      tool_call_id: 'test-123',
      tool_name: 'edit_task_specification',
      tool_args: { edits: [], reasoning: 'Test' }
    }

    // Set up initial state
    useApprovalsStore.setState({
      approvals: {
        'project-1': [testApproval],
        'task-5': [{ ...testApproval, tool_call_id: 'test-456' }]
      }
    })

    const { result } = renderHook(() => useAllApprovals())

    expect(Object.keys(result.current)).toHaveLength(2)
    expect(result.current['project-1']).toHaveLength(1)
    expect(result.current['task-5']).toHaveLength(1)
  })
})
