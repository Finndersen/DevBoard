import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import DocumentEditApproval from '../approvals/documents/DocumentEditApproval'
import type { PendingApproval } from '../../lib/api'

const mockApproval: PendingApproval = {
  tool_call_id: 'test-123',
  tool_name: 'edit_task_specification',
  tool_args: {
    edits: [
      {
        old_string: 'old text',
        new_string: 'new text'
      }
    ],
    diff_preview: '- old text\n+ new text',
    reasoning: 'This change improves the task specification clarity'
  }
}

describe('DocumentEditApproval', () => {
  it('renders approval summary card', () => {
    const mockOnApproval = vi.fn()

    render(
      <DocumentEditApproval
        approval={mockApproval}
        onApproval={mockOnApproval}
      />
    )

    expect(screen.getByText('Edit Task Specification')).toBeInTheDocument()
    expect(screen.getByText('1 change')).toBeInTheDocument()
    expect(screen.getByText('This change improves the task specification clarity')).toBeInTheDocument()
  })

  it('shows Review button to open modal', () => {
    const mockOnApproval = vi.fn()

    render(
      <DocumentEditApproval
        approval={mockApproval}
        onApproval={mockOnApproval}
      />
    )

    const reviewButton = screen.getByRole('button', { name: /review/i })
    expect(reviewButton).toBeInTheDocument()
  })

  it('has quick approve and deny buttons', () => {
    const mockOnApproval = vi.fn()

    render(
      <DocumentEditApproval
        approval={mockApproval}
        onApproval={mockOnApproval}
      />
    )

    expect(screen.getByText('Quick Approve')).toBeInTheDocument()
    expect(screen.getByText('Quick Deny')).toBeInTheDocument()
  })

  it('calls onApproval when quick approve is clicked', () => {
    const mockOnApproval = vi.fn()

    render(
      <DocumentEditApproval
        approval={mockApproval}
        onApproval={mockOnApproval}
      />
    )

    fireEvent.click(screen.getByText('Quick Approve'))

    expect(mockOnApproval).toHaveBeenCalledWith('test-123', {
      approved: true
    })
  })

  it('calls onApproval when quick deny is clicked', () => {
    const mockOnApproval = vi.fn()

    render(
      <DocumentEditApproval
        approval={mockApproval}
        onApproval={mockOnApproval}
      />
    )

    fireEvent.click(screen.getByText('Quick Deny'))

    expect(mockOnApproval).toHaveBeenCalledWith('test-123', {
      approved: false
    })
  })

  it('opens modal when review button is clicked', () => {
    const mockOnApproval = vi.fn()

    render(
      <DocumentEditApproval
        approval={mockApproval}
        onApproval={mockOnApproval}
      />
    )

    fireEvent.click(screen.getByRole('button', { name: /review/i }))

    // Modal should be open and show modal content
    expect(screen.getByRole('dialog')).toBeInTheDocument()
    expect(screen.getByText('Review Changes: Task Specification')).toBeInTheDocument()
  })

  it('shows change summary for multiple edits', () => {
    const multiEditApproval: PendingApproval = {
      ...mockApproval,
      tool_args: {
        edits: [
          { old_string: 'text1', new_string: 'new1' },
          { old_string: 'text2', new_string: 'new2' },
          { old_string: 'text3', new_string: 'new3' }
        ],
        reasoning: 'Multiple changes'
      }
    }

    const mockOnApproval = vi.fn()

    render(
      <DocumentEditApproval
        approval={multiEditApproval}
        onApproval={mockOnApproval}
      />
    )

    expect(screen.getByText('3 changes')).toBeInTheDocument()
  })

  it('shows diff line count when only diff preview available', () => {
    const diffOnlyApproval: PendingApproval = {
      ...mockApproval,
      tool_args: {
        diff_preview: '- line1\n- line2\n+ newline1\n+ newline2\n+ newline3',
        reasoning: 'Diff changes'
      }
    }

    const mockOnApproval = vi.fn()

    render(
      <DocumentEditApproval
        approval={diffOnlyApproval}
        onApproval={mockOnApproval}
      />
    )

    expect(screen.getByText('+3 -2 lines')).toBeInTheDocument()
  })

  it('handles disabled state', () => {
    const mockOnApproval = vi.fn()

    render(
      <DocumentEditApproval
        approval={mockApproval}
        onApproval={mockOnApproval}
        disabled={true}
      />
    )

    const reviewButton = screen.getByRole('button', { name: /review/i })
    const approveButton = screen.getByRole('button', { name: /quick approve/i })
    const denyButton = screen.getByRole('button', { name: /quick deny/i })

    expect(reviewButton).toBeDisabled()
    expect(approveButton).toBeDisabled()
    expect(denyButton).toBeDisabled()
  })

  it('renders set_content tool with content summary', () => {
    const setContentApproval: PendingApproval = {
      tool_call_id: 'test-456',
      tool_name: 'set_task_specification_content',
      tool_args: {
        content: 'This is the initial content\nfor the task specification\nwith multiple lines',
        reasoning: 'Setting initial content for blank document'
      }
    }

    const mockOnApproval = vi.fn()

    render(
      <DocumentEditApproval
        approval={setContentApproval}
        onApproval={mockOnApproval}
      />
    )

    expect(screen.getByText('Set Task Specification')).toBeInTheDocument()
    expect(screen.getByText('3 lines, 74 characters')).toBeInTheDocument()
    expect(screen.getByText('Setting initial content for blank document')).toBeInTheDocument()
  })

  it('opens modal with content view for set_content tool', () => {
    const setContentApproval: PendingApproval = {
      tool_call_id: 'test-789',
      tool_name: 'set_implementation_plan_content',
      tool_args: {
        content: 'Implementation plan content here',
        reasoning: 'Initial plan'
      }
    }

    const mockOnApproval = vi.fn()

    render(
      <DocumentEditApproval
        approval={setContentApproval}
        onApproval={mockOnApproval}
      />
    )

    fireEvent.click(screen.getByRole('button', { name: /review/i }))

    // Modal should show content view instead of changes view
    expect(screen.getByRole('dialog')).toBeInTheDocument()
    expect(screen.getByText('Review Content: Implementation Plan')).toBeInTheDocument()
    expect(screen.getByText('Document Content:')).toBeInTheDocument()
  })
})