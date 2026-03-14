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
  onTriggerRebase?: () => void
  isStreaming?: boolean
}

export default function GitBranchStatusModal({
  isOpen,
  onClose,
  taskId,
  gitStatus,
  onStatusUpdate,
  onTriggerRebase,
  isStreaming = false
}: GitBranchStatusModalProps) {
  const [checkoutLoading, setCheckoutLoading] = useState(false)
  const [abortLoading, setAbortLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleRebase = useCallback(() => {
    onTriggerRebase?.()
    onClose()
  }, [onTriggerRebase, onClose])

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

  const handleAbortRebase = useCallback(async () => {
    setAbortLoading(true)
    setError(null)

    try {
      await apiClient.abortTaskRebase(taskId)
      onStatusUpdate?.()
    } catch (err) {
      if (err instanceof Error) {
        setError(err.message)
      } else {
        setError('Failed to abort rebase')
      }
    } finally {
      setAbortLoading(false)
    }
  }, [taskId, onStatusUpdate])

  if (!gitStatus) return null

  // Allow rebase even with potential conflicts - agent will resolve them
  const canRebase = gitStatus.commits_behind > 0 && !gitStatus.rebase_in_progress
  const isAlreadyInMainRepo = gitStatus.main_repo_current_branch === gitStatus.branch_name
  const canCheckoutToMain = gitStatus.main_repo_is_clean && !isAlreadyInMainRepo && !gitStatus.rebase_in_progress

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Branch Status"
      maxWidth="xl"
    >
      <div className="space-y-4">
        {/* Rebase in progress indicator */}
        {gitStatus.rebase_in_progress && (
          <div className="flex items-center p-3 rounded bg-amber-50 dark:bg-amber-900/20 text-amber-700 dark:text-amber-300">
            <svg className="w-5 h-5 mr-2 flex-shrink-0 animate-spin" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            <div className="flex-1">
              <span className="text-sm font-medium">Rebase in progress</span>
              <p className="text-xs mt-0.5">Agent is resolving conflicts or the rebase was interrupted</p>
            </div>
            {!isStreaming && (
              <Button
                variant="secondary"
                size="sm"
                onClick={handleAbortRebase}
                loading={abortLoading}
                className="ml-3"
              >
                Abort Rebase
              </Button>
            )}
          </div>
        )}

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
              {gitStatus.has_conflicts && (
                <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200">
                  conflicts
                </span>
              )}
              {gitStatus.has_uncommitted_base_overlap && (
                <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200">
                  overlap
                </span>
              )}
              {gitStatus.remote_fetch_failed && (
                <span
                  className="inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-400"
                  title="Remote was unreachable — showing local state"
                >
                  <svg className="w-3 h-3 mr-0.5" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                  </svg>
                  stale
                </span>
              )}
            </div>
          </div>
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
          {gitStatus.commits_behind > 0 && !gitStatus.rebase_in_progress && (
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-900 dark:text-white">
                    {gitStatus.has_conflicts || gitStatus.has_uncommitted_base_overlap ? 'Rebase onto base branch & resolve conflicts' : 'Rebase onto base branch'}
                  </p>
                  <p className="text-xs text-gray-500 dark:text-gray-400">
                    Update branch with latest changes from {gitStatus.base_branch}{gitStatus.has_conflicts || gitStatus.has_uncommitted_base_overlap ? ' — agent will resolve conflicts' : ''}
                  </p>
                </div>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={handleRebase}
                  disabled={!canRebase || checkoutLoading || isStreaming}
                  title={isStreaming ? 'Agent is currently running' : undefined}
                >
                  Rebase
                </Button>
              </div>
              {/* Warning for potential conflicts - but allow proceeding */}
              {(gitStatus.has_conflicts || gitStatus.has_uncommitted_base_overlap) && (
                <div className="flex items-center p-2 rounded bg-amber-50 dark:bg-amber-900/20 text-amber-700 dark:text-amber-300">
                  <svg className="w-4 h-4 mr-2 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                  </svg>
                  <span className="text-sm">
                    {gitStatus.has_conflicts
                      ? 'Potential merge conflicts detected — agent will resolve them'
                      : 'Uncommitted changes overlap with base branch changes — agent will resolve conflicts'}
                  </span>
                </div>
              )}
            </div>
          )}

          {/* Checkout to main button - hide if already in main repo */}
          {isAlreadyInMainRepo ? (
            <div className="flex items-center p-2 rounded bg-blue-50 dark:bg-blue-900/20 text-blue-700 dark:text-blue-300">
              <svg className="w-4 h-4 mr-2 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
              </svg>
              <span className="text-sm">Branch is checked out in main repository</span>
            </div>
          ) : (
            <div className="space-y-2">
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
                  disabled={!canCheckoutToMain || isStreaming}
                >
                  Checkout
                </Button>
              </div>
              {!gitStatus.main_repo_is_clean && (
                <div className="flex items-center p-2 rounded bg-amber-50 dark:bg-amber-900/20 text-amber-700 dark:text-amber-300">
                  <svg className="w-4 h-4 mr-2 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                  </svg>
                  <span className="text-sm">Main repo has uncommitted changes</span>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Close button */}
        <div className="flex justify-end pt-2">
          <Button
            variant="ghost"
            onClick={onClose}
            disabled={checkoutLoading || abortLoading}
          >
            Close
          </Button>
        </div>
      </div>
    </Modal>
  )
}
