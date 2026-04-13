import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { PullRequestTab } from '../PullRequestTab'
import { countPRComments } from '../prUtils'
import { TaskStatus } from '../../../lib/api'
import type { GitHubPRStatusResponse, PRFeedbackResponse, PRDetailResponse } from '../../../lib/api'

const mockPrStatus: GitHubPRStatusResponse = {
  pr_number: 42,
  pr_url: 'https://github.com/owner/repo/pull/42',
  state: 'open',
  merged: false,
  mergeable_state: 'CLEAN',
  review_decision: 'APPROVED',
  ci_status: 'SUCCESS',
  comment_count: 3,
  repo_full_name: 'owner/repo',
}

const mockPrFeedback: PRFeedbackResponse = {
  reviews: [
    {
      id: 1,
      author: 'reviewer1',
      state: 'APPROVED',
      body: 'LGTM',
      submitted_at: '2026-04-01T10:00:00Z',
      comment_threads: [],
    },
  ],
  standalone_threads: [],
}

const mockPrDetail: PRDetailResponse = {
  ci_status: 'SUCCESS',
  checks: [
    { name: 'ci/backend-tests', state: 'SUCCESS', description: 'Build succeeded' },
    { name: 'ci/frontend-tests', state: 'SUCCESS', description: 'Build succeeded' },
    { name: 'ci/lint', state: 'FAILURE', description: 'Linting failed' },
  ],
  reviews: [],
  review_comment_count: 0,
}

const defaultProps = {
  prStatus: mockPrStatus,
  prStatusLoading: false,
  prFeedback: mockPrFeedback,
  prDetail: mockPrDetail,
  prDetailLoading: false,
  taskStatus: TaskStatus.PR_OPEN,
  onRefreshPrStatus: vi.fn(),
  onResolveConflicts: vi.fn(),
  onSubmitComments: vi.fn(),
  isConversationStreaming: false,
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('PullRequestTab', () => {
  describe('Status Overview Bar', () => {
    it('renders PR number as link', () => {
      render(<PullRequestTab {...defaultProps} />)
      const link = screen.getByRole('link', { name: '#42' })
      expect(link).toHaveAttribute('href', 'https://github.com/owner/repo/pull/42')
      expect(link).toHaveAttribute('target', '_blank')
    })

    it('renders Open badge when PR not merged', () => {
      render(<PullRequestTab {...defaultProps} />)
      expect(screen.getByText('open')).toBeInTheDocument()
    })

    it('renders Merged badge when PR is merged', () => {
      const mergedStatus = { ...mockPrStatus, merged: true, state: 'closed' }
      render(<PullRequestTab {...defaultProps} prStatus={mergedStatus} />)
      expect(screen.getByText('Merged')).toBeInTheDocument()
    })

    it('shows loading state when prStatus is null and loading', () => {
      render(<PullRequestTab {...defaultProps} prStatus={null} prStatusLoading={true} />)
      expect(screen.getByText('Loading PR status…')).toBeInTheDocument()
    })

    it('shows no status message when prStatus is null and not loading', () => {
      render(<PullRequestTab {...defaultProps} prStatus={null} prStatusLoading={false} />)
      expect(screen.getByText('No PR status available')).toBeInTheDocument()
    })

    it('shows Refresh button for PR_OPEN tasks', () => {
      render(<PullRequestTab {...defaultProps} taskStatus={TaskStatus.PR_OPEN} />)
      expect(screen.getByRole('button', { name: /refresh/i })).toBeInTheDocument()
    })

    it('hides Refresh button for COMPLETE tasks', () => {
      render(<PullRequestTab {...defaultProps} taskStatus={TaskStatus.COMPLETE} />)
      expect(screen.queryByRole('button', { name: /refresh/i })).not.toBeInTheDocument()
    })

    it('calls onRefreshPrStatus when Refresh is clicked', () => {
      const onRefreshPrStatus = vi.fn()
      render(<PullRequestTab {...defaultProps} onRefreshPrStatus={onRefreshPrStatus} />)
      fireEvent.click(screen.getByRole('button', { name: /refresh/i }))
      expect(onRefreshPrStatus).toHaveBeenCalledOnce()
    })

    it('shows Rebase button when mergeable_state is DIRTY', () => {
      const dirtyStatus = { ...mockPrStatus, mergeable_state: 'DIRTY' }
      render(<PullRequestTab {...defaultProps} prStatus={dirtyStatus} taskStatus={TaskStatus.PR_OPEN} />)
      expect(screen.getByRole('button', { name: /rebase/i })).toBeInTheDocument()
    })

    it('hides Rebase button when mergeable_state is CLEAN', () => {
      render(<PullRequestTab {...defaultProps} prStatus={mockPrStatus} />)
      expect(screen.queryByRole('button', { name: /rebase/i })).not.toBeInTheDocument()
    })

    it('disables Rebase button when conversation is streaming', () => {
      const dirtyStatus = { ...mockPrStatus, mergeable_state: 'DIRTY' }
      render(<PullRequestTab {...defaultProps} prStatus={dirtyStatus} isConversationStreaming={true} />)
      expect(screen.getByRole('button', { name: /rebase/i })).toBeDisabled()
    })

    it('calls onResolveConflicts when Rebase is clicked', () => {
      const onResolveConflicts = vi.fn()
      const dirtyStatus = { ...mockPrStatus, mergeable_state: 'DIRTY' }
      render(<PullRequestTab {...defaultProps} prStatus={dirtyStatus} onResolveConflicts={onResolveConflicts} />)
      fireEvent.click(screen.getByRole('button', { name: /rebase/i }))
      expect(onResolveConflicts).toHaveBeenCalledOnce()
    })
  })

  describe('CI Checks Section', () => {
    it('renders CI check names', () => {
      render(<PullRequestTab {...defaultProps} />)
      expect(screen.getByText('ci/backend-tests')).toBeInTheDocument()
      expect(screen.getByText('ci/frontend-tests')).toBeInTheDocument()
      expect(screen.getByText('ci/lint')).toBeInTheDocument()
    })

    it('renders CI check descriptions', () => {
      render(<PullRequestTab {...defaultProps} />)
      expect(screen.getAllByText('Build succeeded')).toHaveLength(2)
      expect(screen.getByText('Linting failed')).toBeInTheDocument()
    })

    it('shows loading state when prDetailLoading', () => {
      render(<PullRequestTab {...defaultProps} prDetail={null} prDetailLoading={true} />)
      expect(screen.getByText('Loading CI checks…')).toBeInTheDocument()
    })

    it('shows empty state when no CI checks', () => {
      const emptyDetail = { ...mockPrDetail, checks: [] }
      render(<PullRequestTab {...defaultProps} prDetail={emptyDetail} />)
      expect(screen.getByText('No CI checks')).toBeInTheDocument()
    })

    it('shows summary with failing count', () => {
      render(<PullRequestTab {...defaultProps} />)
      expect(screen.getByText('1/3 failing')).toBeInTheDocument()
    })

    it('shows passing summary when all checks pass', () => {
      const allPassingDetail = {
        ...mockPrDetail,
        checks: [
          { name: 'ci/test', state: 'SUCCESS', description: null },
          { name: 'ci/lint', state: 'SUCCESS', description: null },
        ],
      }
      render(<PullRequestTab {...defaultProps} prDetail={allPassingDetail} />)
      expect(screen.getByText('2/2 passing')).toBeInTheDocument()
    })

    it('collapses CI checks when header is clicked', () => {
      render(<PullRequestTab {...defaultProps} />)
      expect(screen.getByText('ci/backend-tests')).toBeInTheDocument()
      fireEvent.click(screen.getByText('CI Checks'))
      expect(screen.queryByText('ci/backend-tests')).not.toBeInTheDocument()
    })

    it('expands CI checks when header is clicked again', () => {
      render(<PullRequestTab {...defaultProps} />)
      fireEvent.click(screen.getByText('CI Checks'))
      fireEvent.click(screen.getByText('CI Checks'))
      expect(screen.getByText('ci/backend-tests')).toBeInTheDocument()
    })
  })

  describe('Reviews & Comments Section', () => {
    it('renders reviews when prFeedback has content', () => {
      render(<PullRequestTab {...defaultProps} />)
      expect(screen.getByText('@reviewer1')).toBeInTheDocument()
      expect(screen.getByText('LGTM')).toBeInTheDocument()
    })

    it('shows empty state when prFeedback is null', () => {
      render(<PullRequestTab {...defaultProps} prFeedback={null} />)
      expect(screen.getByText('No reviews or comments yet')).toBeInTheDocument()
    })

    it('shows empty state when prFeedback has no comments', () => {
      const emptyFeedback: PRFeedbackResponse = { reviews: [], standalone_threads: [] }
      render(<PullRequestTab {...defaultProps} prFeedback={emptyFeedback} />)
      expect(screen.getByText('No reviews or comments yet')).toBeInTheDocument()
    })

    it('shows comment count badge', () => {
      render(<PullRequestTab {...defaultProps} />)
      // countPRComments: 1 review with body → 1
      expect(screen.getByText('1')).toBeInTheDocument()
    })
  })
})

describe('countPRComments', () => {
  it('counts reviews with body', () => {
    const feedback: PRFeedbackResponse = {
      reviews: [
        { id: 1, author: 'a', state: 'APPROVED', body: 'good', submitted_at: null, comment_threads: [] },
        { id: 2, author: 'b', state: 'COMMENTED', body: '   ', submitted_at: null, comment_threads: [] },
      ],
      standalone_threads: [],
    }
    expect(countPRComments(feedback)).toBe(1)
  })

  it('counts review comment threads and replies', () => {
    const feedback: PRFeedbackResponse = {
      reviews: [
        {
          id: 1,
          author: 'a',
          state: 'CHANGES_REQUESTED',
          body: '',
          submitted_at: null,
          comment_threads: [
            {
              original: { id: 10, author: 'a', body: 'fix this', path: 'src/foo.ts', line: 5, diff_hunk: null, created_at: null, in_reply_to_id: null },
              replies: [
                { id: 11, author: 'b', body: 'done', path: 'src/foo.ts', line: 5, diff_hunk: null, created_at: null, in_reply_to_id: 10 },
              ],
            },
          ],
        },
      ],
      standalone_threads: [],
    }
    expect(countPRComments(feedback)).toBe(2)
  })

  it('counts standalone threads and replies', () => {
    const feedback: PRFeedbackResponse = {
      reviews: [],
      standalone_threads: [
        {
          original: { id: 20, author: 'a', body: 'general comment', path: '', line: null, diff_hunk: null, created_at: null, in_reply_to_id: null },
          replies: [],
        },
        {
          original: { id: 21, author: 'b', body: 'another', path: '', line: null, diff_hunk: null, created_at: null, in_reply_to_id: null },
          replies: [
            { id: 22, author: 'c', body: 'reply', path: '', line: null, diff_hunk: null, created_at: null, in_reply_to_id: 21 },
          ],
        },
      ],
    }
    expect(countPRComments(feedback)).toBe(3)
  })
})
