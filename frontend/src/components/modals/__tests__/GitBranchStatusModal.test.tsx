import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { render } from '../../../test/utils'
import GitBranchStatusModal from '../GitBranchStatusModal'
import { apiClient } from '../../../lib/api'
import type { TaskGitStatus } from '../../../lib/api'

vi.mock('../../../lib/api', () => ({
  apiClient: {
    checkoutTaskToMain: vi.fn(),
    abortTaskRebase: vi.fn(),
    createTaskBranch: vi.fn(),
  },
}))

const baseGitStatus: TaskGitStatus = {
  branch_name: 'task/my-feature',
  branch_exists: true,
  base_branch: 'main',
  commits_ahead: 0,
  commits_behind: 0,
  can_merge: true,
  has_conflicts: false,
  worktree_slot: null,
  worktree_slot_path: null,
  main_repo_is_clean: true,
  main_repo_current_branch: 'main',
  rebase_in_progress: false,
  has_uncommitted_base_overlap: false,
  remote_fetch_failed: false,
  base_has_conflicting_uncommitted: false,
}

const missingBranchGitStatus: TaskGitStatus = {
  ...baseGitStatus,
  branch_exists: false,
}

describe('GitBranchStatusModal', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('does not render when gitStatus is null', () => {
    render(
      <GitBranchStatusModal
        isOpen={true}
        onClose={() => {}}
        taskId={1}
        gitStatus={null}
      />
    )
    expect(screen.queryByText('Branch Status')).not.toBeInTheDocument()
  })

  describe('when branch_exists is true', () => {
    it('shows normal status content', () => {
      render(
        <GitBranchStatusModal
          isOpen={true}
          onClose={() => {}}
          taskId={1}
          gitStatus={baseGitStatus}
        />
      )

      expect(screen.getByText('Up to date')).toBeInTheDocument()
      expect(screen.queryByText('Branch not found')).not.toBeInTheDocument()
      expect(screen.queryByText('Create Branch')).not.toBeInTheDocument()
    })

    it('shows checkout button when branch exists', () => {
      render(
        <GitBranchStatusModal
          isOpen={true}
          onClose={() => {}}
          taskId={1}
          gitStatus={baseGitStatus}
        />
      )

      expect(screen.getByRole('button', { name: 'Checkout' })).toBeInTheDocument()
    })
  })

  describe('when base_has_conflicting_uncommitted is true', () => {
    it('shows the conflicting uncommitted changes warning', () => {
      render(
        <GitBranchStatusModal
          isOpen={true}
          onClose={() => {}}
          taskId={1}
          gitStatus={{ ...baseGitStatus, base_has_conflicting_uncommitted: true }}
        />
      )

      expect(screen.getByText(/Main repo has uncommitted changes in files modified by this task/)).toBeInTheDocument()
    })

    it('shows the main repo conflict status badge', () => {
      render(
        <GitBranchStatusModal
          isOpen={true}
          onClose={() => {}}
          taskId={1}
          gitStatus={{ ...baseGitStatus, base_has_conflicting_uncommitted: true }}
        />
      )

      expect(screen.getByText('main repo conflict')).toBeInTheDocument()
    })

    it('does not show the warning when base_has_conflicting_uncommitted is false', () => {
      render(
        <GitBranchStatusModal
          isOpen={true}
          onClose={() => {}}
          taskId={1}
          gitStatus={baseGitStatus}
        />
      )

      expect(screen.queryByText(/Main repo has uncommitted changes in files modified by this task/)).not.toBeInTheDocument()
      expect(screen.queryByText('main repo conflict')).not.toBeInTheDocument()
    })
  })

  describe('when branch_exists is false', () => {
    it('shows branch missing warning', () => {
      render(
        <GitBranchStatusModal
          isOpen={true}
          onClose={() => {}}
          taskId={1}
          gitStatus={missingBranchGitStatus}
        />
      )

      expect(screen.getByText('Branch not found')).toBeInTheDocument()
      expect(screen.getByText(/does not exist/)).toBeInTheDocument()
      expect(screen.queryByText('Up to date')).not.toBeInTheDocument()
      expect(screen.queryByRole('button', { name: 'Checkout' })).not.toBeInTheDocument()
    })

    it('shows Create Branch button', () => {
      render(
        <GitBranchStatusModal
          isOpen={true}
          onClose={() => {}}
          taskId={1}
          gitStatus={missingBranchGitStatus}
        />
      )

      expect(screen.getByRole('button', { name: 'Create Branch' })).toBeInTheDocument()
      expect(screen.getByText('Create a new branch from main')).toBeInTheDocument()
    })

    it('calls createTaskBranch API and triggers status update on success', async () => {
      const user = userEvent.setup()
      const onStatusUpdate = vi.fn()
      const onClose = vi.fn()

      vi.mocked(apiClient.createTaskBranch).mockResolvedValue({ success: true, message: 'Branch created' })

      render(
        <GitBranchStatusModal
          isOpen={true}
          onClose={onClose}
          taskId={42}
          gitStatus={missingBranchGitStatus}
          onStatusUpdate={onStatusUpdate}
        />
      )

      await user.click(screen.getByRole('button', { name: 'Create Branch' }))

      await waitFor(() => {
        expect(apiClient.createTaskBranch).toHaveBeenCalledWith(42)
        expect(onStatusUpdate).toHaveBeenCalled()
        expect(onClose).toHaveBeenCalled()
      })
    })

    it('shows error message when createTaskBranch fails', async () => {
      const user = userEvent.setup()

      vi.mocked(apiClient.createTaskBranch).mockRejectedValue(new Error('git operation failed'))

      render(
        <GitBranchStatusModal
          isOpen={true}
          onClose={() => {}}
          taskId={42}
          gitStatus={missingBranchGitStatus}
        />
      )

      await user.click(screen.getByRole('button', { name: 'Create Branch' }))

      await waitFor(() => {
        expect(screen.getByText('git operation failed')).toBeInTheDocument()
      })
    })
  })
})
