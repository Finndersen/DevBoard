import { useState, useEffect } from 'react'
import { apiClient, type TaskGitStatus } from '../../lib/api'
import { Card, Button, StatusBadge } from '../ui'
import { textColors } from '../../styles/designSystem'
import { FolderOpenIcon, CommandLineIcon, ArrowPathIcon } from '@heroicons/react/24/outline'

interface TaskGitStatusPanelProps {
  taskId: number | string
}

export function TaskGitStatusPanel({ taskId }: TaskGitStatusPanelProps) {
  const [gitStatus, setGitStatus] = useState<TaskGitStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [merging, setMerging] = useState(false)
  const [deletingBranch, setDeletingBranch] = useState(false)

  const loadGitStatus = async () => {
    setLoading(true)
    setError(null)
    try {
      const status = await apiClient.getTaskGitStatus(taskId)
      setGitStatus(status)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load git status')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadGitStatus()
  }, [taskId])

  const handleOpenInVSCode = () => {
    if (gitStatus?.worktree_slot?.path) {
      // Open path in VS Code using vscode:// protocol
      window.location.href = `vscode://file${gitStatus.worktree_slot.path}`
    }
  }

  const handleOpenTerminal = () => {
    // This would require backend support to open terminal
    // For now, just copy path to clipboard
    if (gitStatus?.worktree_slot?.path) {
      navigator.clipboard.writeText(gitStatus.worktree_slot.path)
      alert(`Path copied to clipboard: ${gitStatus.worktree_slot.path}`)
    }
  }

  const handleMergeBranch = async () => {
    if (!gitStatus) return

    const confirmed = window.confirm(
      `Merge branch "${gitStatus.branch_name}" into "${gitStatus.base_branch}"?`
    )
    if (!confirmed) return

    setMerging(true)
    try {
      await apiClient.mergeTaskBranch(taskId, {
        target_branch: gitStatus.base_branch,
        delete_branch: false,
      })
      alert('Branch merged successfully!')
      loadGitStatus()
    } catch (err) {
      alert(`Failed to merge branch: ${err instanceof Error ? err.message : 'Unknown error'}`)
    } finally {
      setMerging(false)
    }
  }

  const handleDeleteBranch = async () => {
    if (!gitStatus) return

    const confirmed = window.confirm(
      `Delete branch "${gitStatus.branch_name}"? This cannot be undone.`
    )
    if (!confirmed) return

    setDeletingBranch(true)
    try {
      await apiClient.deleteTaskBranch(taskId, false)
      alert('Branch deleted successfully!')
      loadGitStatus()
    } catch (err) {
      alert(`Failed to delete branch: ${err instanceof Error ? err.message : 'Unknown error'}`)
    } finally {
      setDeletingBranch(false)
    }
  }

  if (loading) {
    return (
      <Card>
        <div className="animate-pulse">
          <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-1/3 mb-3"></div>
          <div className="h-3 bg-gray-200 dark:bg-gray-700 rounded w-2/3 mb-2"></div>
          <div className="h-3 bg-gray-200 dark:bg-gray-700 rounded w-1/2"></div>
        </div>
      </Card>
    )
  }

  if (error) {
    return (
      <Card>
        <div className="text-red-600 dark:text-red-400 text-sm">
          Error: {error}
          <Button
            onClick={loadGitStatus}
            variant="secondary"
            size="sm"
            className="ml-2"
          >
            Retry
          </Button>
        </div>
      </Card>
    )
  }

  if (!gitStatus) {
    return null
  }

  return (
    <Card>
      <div className="space-y-4">
        {/* Header */}
        <div className="flex items-center justify-between">
          <h3 className={`text-sm font-semibold ${textColors.primary}`}>Git Information</h3>
          <Button
            onClick={loadGitStatus}
            variant="ghost"
            size="sm"
            icon={<ArrowPathIcon className="w-3 h-3" />}
            title="Refresh"
          />
        </div>

        {/* Branch Info */}
        <div className="space-y-2 text-sm">
          <div className="flex items-center justify-between">
            <span className={textColors.secondary}>Branch:</span>
            <code className="font-mono text-xs bg-gray-100 dark:bg-gray-800 px-2 py-0.5 rounded">
              {gitStatus.branch_name}
            </code>
          </div>

          <div className="flex items-center justify-between">
            <span className={textColors.secondary}>Base:</span>
            <code className="font-mono text-xs bg-gray-100 dark:bg-gray-800 px-2 py-0.5 rounded">
              {gitStatus.base_branch}
            </code>
          </div>

          {gitStatus.branch_exists && (
            <div className="flex items-center justify-between">
              <span className={textColors.secondary}>Status:</span>
              <div className="flex items-center space-x-2">
                {gitStatus.commits_ahead > 0 && (
                  <span className="text-xs text-green-600 dark:text-green-400">
                    ↑ {gitStatus.commits_ahead} ahead
                  </span>
                )}
                {gitStatus.commits_behind > 0 && (
                  <span className="text-xs text-orange-600 dark:text-orange-400">
                    ↓ {gitStatus.commits_behind} behind
                  </span>
                )}
                {gitStatus.commits_ahead === 0 && gitStatus.commits_behind === 0 && (
                  <span className="text-xs text-gray-500">Up to date</span>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Worktree Info */}
        {gitStatus.worktree_slot && (
          <div className="border-t border-gray-200 dark:border-gray-700 pt-3 space-y-2">
            <div className="text-sm">
              <span className={`${textColors.secondary} block mb-1`}>Workspace:</span>
              <code className="font-mono text-xs bg-gray-100 dark:bg-gray-800 px-2 py-1 rounded block truncate">
                {gitStatus.worktree_slot.path}
              </code>
            </div>

            <div className="flex items-center justify-between text-sm">
              <span className={textColors.secondary}>Status:</span>
              <StatusBadge variant={gitStatus.worktree_slot.locked ? 'warning' : 'success'}>
                {gitStatus.worktree_slot.locked ? '🔒 Locked' : '✓ Available'}
              </StatusBadge>
            </div>

            {gitStatus.worktree_slot.locked && gitStatus.worktree_slot.locked_since && (
              <div className="flex items-center justify-between text-xs">
                <span className={textColors.secondary}>Since:</span>
                <span className={textColors.secondary}>
                  {new Date(gitStatus.worktree_slot.locked_since).toLocaleString()}
                </span>
              </div>
            )}

            {/* Workspace Actions */}
            <div className="flex space-x-2 pt-2">
              <Button
                onClick={handleOpenInVSCode}
                variant="secondary"
                size="sm"
                icon={<FolderOpenIcon className="w-4 h-4" />}
                className="flex-1"
              >
                Open in VS Code
              </Button>
              <Button
                onClick={handleOpenTerminal}
                variant="secondary"
                size="sm"
                icon={<CommandLineIcon className="w-4 h-4" />}
                title="Copy path"
              />
            </div>
          </div>
        )}

        {/* Branch Actions */}
        {gitStatus.branch_exists && (
          <div className="border-t border-gray-200 dark:border-gray-700 pt-3">
            <div className="flex space-x-2">
              <Button
                onClick={handleMergeBranch}
                variant="primary"
                size="sm"
                disabled={!gitStatus.can_merge || merging}
                loading={merging}
                className="flex-1"
              >
                Merge to {gitStatus.base_branch}
              </Button>
              <Button
                onClick={handleDeleteBranch}
                variant="secondary"
                size="sm"
                disabled={deletingBranch}
                loading={deletingBranch}
                className="text-red-600 hover:text-red-700 dark:text-red-400 dark:hover:text-red-300"
              >
                Delete Branch
              </Button>
            </div>

            {gitStatus.has_conflicts && (
              <div className="mt-2 text-xs text-orange-600 dark:text-orange-400">
                ⚠️ Branch has conflicts - please resolve before merging
              </div>
            )}
          </div>
        )}
      </div>
    </Card>
  )
}
