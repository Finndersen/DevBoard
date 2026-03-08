import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect, beforeEach, vi } from 'vitest'
import GitHubPRStatusBar from '../GitHubPRStatusBar'
import type { OpenPRsResponse, PRDetailResponse } from '../../../lib/api'

// Mock the hooks and API client
const mockRefetch = vi.fn()
const mockOpenTab = vi.fn()

vi.mock('../../../hooks/useGitHubPRs', () => ({
  useOpenPRs: vi.fn()
}))

vi.mock('../../../stores/uiStore', () => ({
  useUIStore: vi.fn((selector: (state: { openTab: typeof mockOpenTab }) => unknown) =>
    selector({ openTab: mockOpenTab })
  )
}))

vi.mock('../../../lib/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../../lib/api')>()
  return {
    ...actual,
    apiClient: {
      getPRDetail: vi.fn(),
    },
  }
})

import { useOpenPRs } from '../../../hooks/useGitHubPRs'
import { apiClient } from '../../../lib/api'

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
    },
  ],
  errors: [],
}

const mockDetailResponse: PRDetailResponse = {
  ci_status: 'success',
  checks: [{ name: 'ci/test', state: 'success', description: 'Tests passed' }],
  reviews: [{ author: 'reviewer1', state: 'APPROVED', body: 'LGTM' }],
  review_comment_count: 3,
}

describe('GitHubPRStatusBar', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(useOpenPRs).mockReturnValue({
      data: mockPRsResponse,
      loading: false,
      error: null,
      refetch: mockRefetch,
      setData: vi.fn(),
    })
  })

  it('renders PR pills with correct info', () => {
    render(<GitHubPRStatusBar />)

    expect(screen.getByText('DevBoard #1')).toBeInTheDocument()
    expect(screen.getByText('Fix authentication bug')).toBeInTheDocument()
    expect(screen.getByText('DevBoard #2')).toBeInTheDocument()
    expect(screen.getByText('Add dark mode')).toBeInTheDocument()
  })

  it('shows loading state when data is loading', () => {
    vi.mocked(useOpenPRs).mockReturnValue({
      data: null,
      loading: true,
      error: null,
      refetch: mockRefetch,
      setData: vi.fn(),
    })

    render(<GitHubPRStatusBar />)
    expect(screen.getByText('Loading PRs...')).toBeInTheDocument()
  })

  it('shows empty state when no PRs exist', () => {
    vi.mocked(useOpenPRs).mockReturnValue({
      data: { prs: [], errors: [] },
      loading: false,
      error: null,
      refetch: mockRefetch,
      setData: vi.fn(),
    })

    render(<GitHubPRStatusBar />)
    expect(screen.getByText('No open PRs')).toBeInTheDocument()
  })

  it('shows error warning when there are errors', () => {
    vi.mocked(useOpenPRs).mockReturnValue({
      data: { prs: [], errors: ['GitHub API error'] },
      loading: false,
      error: null,
      refetch: mockRefetch,
      setData: vi.fn(),
    })

    render(<GitHubPRStatusBar />)
    // Warning icon should be present (ExclamationTriangleIcon)
    const warningIcon = document.querySelector('[title="GitHub API error"]')
    expect(warningIcon).toBeInTheDocument()
  })

  it('refresh button calls refetch', () => {
    render(<GitHubPRStatusBar />)

    const refreshButton = screen.getByTitle('Refresh PRs')
    fireEvent.click(refreshButton)
    expect(mockRefetch).toHaveBeenCalledOnce()
  })

  it('open in GitHub button opens PR URL in new tab', () => {
    const windowOpen = vi.spyOn(window, 'open').mockImplementation(() => null)

    render(<GitHubPRStatusBar />)

    const openButtons = screen.getAllByTitle('Open in GitHub')
    fireEvent.click(openButtons[0])
    expect(windowOpen).toHaveBeenCalledWith('https://github.com/owner/DevBoard/pull/1', '_blank')

    windowOpen.mockRestore()
  })

  it('open task button calls openTab for PR with task association', () => {
    render(<GitHubPRStatusBar />)

    const taskButtons = screen.getAllByTitle('Open task')
    // Only PR #1 has a task association
    expect(taskButtons).toHaveLength(1)

    fireEvent.click(taskButtons[0])
    expect(mockOpenTab).toHaveBeenCalledWith({
      type: 'task',
      entityId: '42',
      title: 'Auth fix task',
    })
  })

  it('shows detail popover when PR pill is clicked', async () => {
    vi.mocked(apiClient.getPRDetail).mockResolvedValue(mockDetailResponse)

    render(<GitHubPRStatusBar />)

    // Click on the first PR's info area
    fireEvent.click(screen.getByText('DevBoard #1'))

    // Should show loading then detail
    await waitFor(() => {
      expect(screen.getByText('ci/test')).toBeInTheDocument()
      expect(screen.getByText('reviewer1')).toBeInTheDocument()
      expect(screen.getByText('3 review comments')).toBeInTheDocument()
    })

    expect(apiClient.getPRDetail).toHaveBeenCalledWith(10, 1)
  })

  it('renders correct status dot colors', () => {
    render(<GitHubPRStatusBar />)

    const dots = document.querySelectorAll('.rounded-full.w-2.h-2')
    // First PR: clean -> green
    expect(dots[0].className).toContain('bg-green-500')
    // Second PR: dirty -> red
    expect(dots[1].className).toContain('bg-red-500')
  })
})
