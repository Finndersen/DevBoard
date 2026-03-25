import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect, beforeEach, vi } from 'vitest'
import GitHubPRDropdown from '../GitHubPRDropdown'
import type { OpenPRsResponse } from '../../../lib/api'

const mockRefetch = vi.fn()
const mockNavigateTo = vi.fn()

vi.mock('../../../stores/uiStore', () => ({
  useUIStore: vi.fn((selector: (state: { navigateTo: typeof mockNavigateTo }) => unknown) =>
    selector({ navigateTo: mockNavigateTo })
  )
}))

const mockPRsResponse: OpenPRsResponse = {
  prs: [
    {
      pr_number: 1,
      title: 'Fix authentication bug',
      repo_full_name: 'owner/DevBoard',
      codebase_id: 10,
      pr_url: 'https://github.com/owner/DevBoard/pull/1',
      mergeable_state: 'clean',
      task_id: 42,
      task_title: 'Auth fix task',
      review_decision: 'APPROVED',
      ci_status: 'SUCCESS',
      comment_count: 5,
      updated_at: '2026-03-01T12:00:00Z',
    },
    {
      pr_number: 2,
      title: 'Add dark mode',
      repo_full_name: 'owner/DevBoard',
      codebase_id: 10,
      pr_url: 'https://github.com/owner/DevBoard/pull/2',
      mergeable_state: 'dirty',
      task_id: null,
      task_title: null,
      review_decision: 'CHANGES_REQUESTED',
      ci_status: 'FAILURE',
      comment_count: 0,
      updated_at: '2026-02-28T10:00:00Z',
    },
  ],
  errors: [],
}

function openDropdown() {
  fireEvent.click(screen.getByLabelText('Pull Requests'))
}

const defaultProps = {
  data: mockPRsResponse,
  loading: false,
  refetch: mockRefetch,
}

describe('GitHubPRDropdown', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders trigger button with badge count', () => {
    render(<GitHubPRDropdown {...defaultProps} />)

    const badge = screen.getByText('2')
    expect(badge).toBeInTheDocument()
  })

  it('shows PR list when dropdown is opened', () => {
    render(<GitHubPRDropdown {...defaultProps} />)

    openDropdown()

    expect(screen.getByText('Fix authentication bug')).toBeInTheDocument()
    expect(screen.getByText('Add dark mode')).toBeInTheDocument()
    expect(screen.getByText(/DevBoard #1/)).toBeInTheDocument()
    expect(screen.getByText(/DevBoard #2/)).toBeInTheDocument()
  })

  it('shows loading state when data is loading', () => {
    render(<GitHubPRDropdown data={null} loading={true} refetch={mockRefetch} />)

    openDropdown()

    expect(screen.getByText('Loading PRs...')).toBeInTheDocument()
  })

  it('shows empty state when no PRs exist', () => {
    render(<GitHubPRDropdown data={{ prs: [], errors: [] }} loading={false} refetch={mockRefetch} />)

    openDropdown()

    expect(screen.getByText('No open PRs')).toBeInTheDocument()
  })

  it('shows error warning icon in header', () => {
    render(<GitHubPRDropdown data={{ prs: [], errors: ['GitHub API error'] }} loading={false} refetch={mockRefetch} />)

    openDropdown()

    const warningIcon = document.querySelector('[title="GitHub API error"]')
    expect(warningIcon).toBeInTheDocument()
  })

  it('refresh button calls refetch with force refresh', () => {
    render(<GitHubPRDropdown {...defaultProps} />)

    openDropdown()

    const refreshButton = screen.getByTitle('Refresh PRs')
    fireEvent.click(refreshButton)
    expect(mockRefetch).toHaveBeenCalledWith(true)
  })

  it('open in GitHub button opens PR URL in new tab', () => {
    const windowOpen = vi.spyOn(window, 'open').mockImplementation(() => null)

    render(<GitHubPRDropdown {...defaultProps} />)

    openDropdown()

    const openButtons = screen.getAllByTitle('Open in GitHub')
    fireEvent.click(openButtons[0])
    expect(windowOpen).toHaveBeenCalledWith('https://github.com/owner/DevBoard/pull/1', '_blank')

    windowOpen.mockRestore()
  })

  it('open task button calls navigateTo for PR with task association', () => {
    render(<GitHubPRDropdown {...defaultProps} />)

    openDropdown()

    const taskButtons = screen.getAllByTitle('Open task')
    // Only PR #1 has a task association
    expect(taskButtons).toHaveLength(1)

    fireEvent.click(taskButtons[0])
    expect(mockNavigateTo).toHaveBeenCalledWith({
      type: 'task',
      entityId: '42',
      title: 'Auth fix task',
    })
  })

  it('shows review badges and comment count', () => {
    render(<GitHubPRDropdown {...defaultProps} />)
    openDropdown()

    expect(screen.getByText('Approved')).toBeInTheDocument()
    expect(screen.getByText('Changes')).toBeInTheDocument()
    // First PR has 5 comments
    expect(screen.getByText('5')).toBeInTheDocument()
  })

  it('shows combined status indicator with correct tooltips', () => {
    render(<GitHubPRDropdown {...defaultProps} />)
    openDropdown()

    // First PR: CLEAN + SUCCESS -> "Ready to merge"
    const readyIndicator = screen.getByTitle('Ready to merge')
    expect(readyIndicator).toBeInTheDocument()
    expect(readyIndicator.className).toContain('text-green-500')

    // Second PR: DIRTY -> "Has merge conflicts" (takes priority over CI failure)
    const conflictIndicator = screen.getByTitle('Has merge conflicts')
    expect(conflictIndicator).toBeInTheDocument()
    expect(conflictIndicator.className).toContain('text-red-500')
  })

  it('shows queued indicator for PR in merge queue', () => {
    const queuedData: OpenPRsResponse = {
      prs: [
        {
          pr_number: 3,
          title: 'Queued PR',
          repo_full_name: 'owner/DevBoard',
          codebase_id: 10,
          pr_url: 'https://github.com/owner/DevBoard/pull/3',
          mergeable_state: 'QUEUED',
          task_id: null,
          task_title: null,
          review_decision: 'APPROVED',
          ci_status: 'SUCCESS',
          comment_count: 0,
          updated_at: '2026-03-01T12:00:00Z',
        },
      ],
      errors: [],
    }

    render(<GitHubPRDropdown data={queuedData} loading={false} refetch={mockRefetch} />)
    openDropdown()

    const queuedIndicator = screen.getByTitle('Queued for merge')
    expect(queuedIndicator).toBeInTheDocument()
    expect(queuedIndicator.className).toContain('text-blue-500')
  })
})
