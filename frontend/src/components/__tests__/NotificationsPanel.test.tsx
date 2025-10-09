import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { BrowserRouter } from 'react-router-dom'
import NotificationsPanel from '../notifications/NotificationsPanel'
import { ApprovalsProvider } from '../../contexts/ApprovalsContext'
import type { PendingApproval } from '../../lib/api'

const localStorageMock = {
  getItem: vi.fn(),
  setItem: vi.fn(),
  removeItem: vi.fn(),
  clear: vi.fn(),
}
Object.defineProperty(window, 'localStorage', {
  value: localStorageMock
})

const mockApproval: PendingApproval = {
  tool_call_id: 'test-123',
  tool_name: 'edit_task_specification',
  tool_args: {
    edits: [{ find: 'old', replace: 'new' }],
    reasoning: 'Update task specification'
  }
}

const renderWithProviders = (component: React.ReactElement) => {
  return render(
    <BrowserRouter>
      <ApprovalsProvider>
        {component}
      </ApprovalsProvider>
    </BrowserRouter>
  )
}

describe('NotificationsPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorageMock.getItem.mockReturnValue(null)
  })

  it('renders bell icon with no badge when there are no approvals', () => {
    renderWithProviders(<NotificationsPanel />)

    const bellButton = screen.getByRole('button', { name: /notifications/i })
    expect(bellButton).toBeInTheDocument()
    expect(screen.queryByText(/^\d+$/)).not.toBeInTheDocument()
  })

  it('shows notification count badge when there are pending approvals', () => {
    const approvalsData = {
      'project-1': [mockApproval]
    }
    localStorageMock.getItem.mockReturnValue(JSON.stringify(approvalsData))

    renderWithProviders(<NotificationsPanel />)

    expect(screen.getByText('1')).toBeInTheDocument()
  })

  it('opens panel when bell icon is clicked', () => {
    renderWithProviders(<NotificationsPanel />)

    const bellButton = screen.getByRole('button', { name: /notifications/i })
    fireEvent.click(bellButton)

    expect(screen.getByText(/Notifications \(/)).toBeInTheDocument()
    expect(screen.getByText('No notifications')).toBeInTheDocument()
  })

  it('closes panel when clicking outside', async () => {
    renderWithProviders(<NotificationsPanel />)

    const bellButton = screen.getByRole('button', { name: /notifications/i })
    fireEvent.click(bellButton)
    expect(screen.getByText(/Notifications \(/)).toBeInTheDocument()

    fireEvent.mouseDown(document.body)

    await waitFor(() => {
      expect(screen.queryByText('No notifications')).not.toBeInTheDocument()
    })
  })

  it('displays pending approvals in the panel', () => {
    const implementationPlanApproval: PendingApproval = {
      tool_call_id: 'test-456',
      tool_name: 'edit_implementation_plan',
      tool_args: {
        edits: [{ find: 'old', replace: 'new' }],
        reasoning: 'Update implementation plan'
      }
    }

    const approvalsData = {
      'project-1': [mockApproval],
      'task-5': [implementationPlanApproval]
    }
    localStorageMock.getItem.mockReturnValue(JSON.stringify(approvalsData))

    renderWithProviders(<NotificationsPanel />)

    const bellButton = screen.getByRole('button', { name: /notifications/i })
    fireEvent.click(bellButton)

    expect(screen.getByText('Project 1')).toBeInTheDocument()
    expect(screen.getByText('Task 5')).toBeInTheDocument()
    expect(screen.getByText(/Task Specification/)).toBeInTheDocument()
    expect(screen.getByText(/Implementation Plan/)).toBeInTheDocument()
  })

  it('shows correct total count with multiple approvals', () => {
    const approvalsData = {
      'project-1': [mockApproval, { ...mockApproval, tool_call_id: 'test-789' }],
      'task-5': [{ ...mockApproval, tool_call_id: 'test-456' }]
    }
    localStorageMock.getItem.mockReturnValue(JSON.stringify(approvalsData))

    renderWithProviders(<NotificationsPanel />)

    expect(screen.getByText('3')).toBeInTheDocument()
  })

  it('displays document type and reasoning for each approval', () => {
    const approvalsData = {
      'project-1': [mockApproval]
    }
    localStorageMock.getItem.mockReturnValue(JSON.stringify(approvalsData))

    renderWithProviders(<NotificationsPanel />)

    const bellButton = screen.getByRole('button', { name: /notifications/i })
    fireEvent.click(bellButton)

    expect(screen.getByText(/Task Specification/)).toBeInTheDocument()
    expect(screen.getByText(/Update task specification/)).toBeInTheDocument()
  })
})