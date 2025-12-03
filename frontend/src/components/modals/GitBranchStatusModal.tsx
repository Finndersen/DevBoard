import { useState, useCallback } from 'react'
import Modal from '../ui/Modal'
import Button from '../ui/Button'
import type { TaskGitStatus } from '../../lib/api'
import { apiClient } from '../../lib/api'

interface GitBranchStatusModalProps {
  isOpen: boolean
  onClose: () => void
  taskId: number
  gitStatus: TaskGitStatus | null
  onStatusUpdate?: () => void
}

export default function GitBranchStatusModal({
  isOpen,
  onClose,
  taskId,
  gitStatus,
  onStatusUpdate
}: GitBranchStatusModalProps) {
  const [rebaseLoading, setRebaseLoading] = useState(false)
  const [checkoutLoading, setCheckoutLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleRebase = useCallback(async () => {
    if (!gitStatus?.branch_name) return

    setRebaseLoading(true)
    setError(null)

    try {
      await apiClient.rebaseTaskBranch(taskId)
      onStatusUpdate?.()
      onClose()
    } catch (err) {
      if (err instanceof Error) {
        // Check for conflict error (409 status)
        if (err.message.includes('409')) {
          setError('Rebase encountered conflicts and was aborted. Please resolve conflicts manually.')
        } else {
          setError(err.message)
        }
      } else {
        setError('Failed to rebase branch')
      }
    } finally {
      setRebaseLoading(false)
    }
  }, [taskId, gitStatus, onStatusUpdate, onClose])

  const handleCheckoutToMain = useCallback(async () => {
    if (!gitStatus?.branch_name) return

    setCheckoutLoading(true)
    setError(null)

    try {
      await apiClient.checkoutTaskToMain(taskId)
      onStatusUpdate?.()
      onClose()
    } catch (err) {
      if (err instanceof Error) {
        setError(err.message)
      } else {
        setError('Failed to checkout to main repository')
      }
    } finally {
      setCheckoutLoading(false)
    }
  }, [taskId, gitStatus, onStatusUpdate, onClose])

  if (!gitStatus) return null

  const canRebase = gitStatus.commits_behind > 0 && !gitStatus.has_conflicts
  const canCheckoutToMain = gitStatus.main_repo_is_clean

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Branch Status"
      maxWidth="xl"
    >
      <div className="space-y-4">
        {/* Branch Info */}
        <div className="space-y-3">
          <div className="flex justify-between items-center">
            <span className="text-sm text-gray-500 dark:text-gray-400">Branch</span>
            <span className="font-mono text-sm text-gray-900 dark:text-white">
              {gitStatus.branch_name || 'No branch'}
            </span>
          </div>

          <div className="flex justify-between items-center">
            <span className="text-sm text-gray-500 dark:text-gray-400">Base Branch</span>
            <span className="font-mono text-sm text-gray-900 dark:text-white">
              {gitStatus.base_branch}
            </span>
          </div>

          {gitStatus.worktree_slot_path && (
            <div className="flex justify-between items-center">
              <span className="text-sm text-gray-500 dark:text-gray-400 flex-shrink-0">Worktree</span>
              <span className="font-mono text-xs text-gray-700 dark:text-gray-300 ml-4 text-right break-all">
                {gitStatus.worktree_slot_path}
              </span>
            </div>
          )}

          {/* Commits ahead/behind */}
          <div className="flex justify-between items-center">
            <span className="text-sm text-gray-500 dark:text-gray-400">Status</span>
            <div className="flex items-center space-x-2">
              {gitStatus.commits_ahead > 0 && (
                <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200">
                  {gitStatus.commits_ahead} ahead
                </span>
              )}
              {gitStatus.commits_behind > 0 && (
                <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200">
                  {gitStatus.commits_behind} behind
                </span>
              )}
              {gitStatus.commits_ahead === 0 && gitStatus.commits_behind === 0 && (
                <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-200">
                  Up to date
                </span>
              )}
            </div>
          </div>

          {gitStatus.has_conflicts && (
            <div className="flex items-center p-2 rounded bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-300">
              <svg className="w-4 h-4 mr-2 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
              </svg>
              <span className="text-sm">Predicted merge conflicts</span>
            </div>
          )}
        </div>

        {/* Error message */}
        {error && (
          <div className="p-3 rounded bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-300 text-sm">
            {error}
          </div>
        )}

        {/* Actions */}
        <div className="border-t border-gray-200 dark:border-gray-700 pt-4 space-y-3">
          {/* Rebase button - show when behind */}
          {gitStatus.commits_behind > 0 && (
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-900 dark:text-white">Rebase onto base branch</p>
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  Update branch with latest changes from {gitStatus.base_branch}
                </p>
              </div>
              <Button
                variant="secondary"
                size="sm"
                onClick={handleRebase}
                loading={rebaseLoading}
                disabled={!canRebase || checkoutLoading}
                title={gitStatus.has_conflicts ? 'Predicted merge conflicts' : undefined}
              >
                Rebase
              </Button>
            </div>
          )}

          {/* Checkout to main button */}
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-900 dark:text-white">Checkout to main repository</p>
              <p className="text-xs text-gray-500 dark:text-gray-400">
                Switch main repo to this branch
              </p>
            </div>
            <Button
              variant="secondary"
              size="sm"
              onClick={handleCheckoutToMain}
              loading={checkoutLoading}
              disabled={!canCheckoutToMain || rebaseLoading}
              title={!gitStatus.main_repo_is_clean ? 'Main repo has uncommitted changes' : undefined}
            >
              Checkout
            </Button>
          </div>
        </div>

        {/* Close button */}
        <div className="flex justify-end pt-2">
          <Button
            variant="ghost"
            onClick={onClose}
            disabled={rebaseLoading || checkoutLoading}
          >
            Close
          </Button>
        </div>
      </div>
    </Modal>
  )
}
