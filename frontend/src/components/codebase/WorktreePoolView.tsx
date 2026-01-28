import { useState, useEffect, useCallback } from 'react'
import { apiClient, type WorktreePoolStatus, type WorktreeSlot } from '../../lib/api'
import { Card, Button, StatusBadge } from '../ui'
import { textColors } from '../../styles/designSystem'
import { FolderOpenIcon, CommandLineIcon, ArrowPathIcon, TrashIcon, LockOpenIcon } from '@heroicons/react/24/outline'

interface WorktreePoolViewProps {
  codebaseId: number | string
}

export function WorktreePoolView({ codebaseId }: WorktreePoolViewProps) {
  const [poolStatus, setPoolStatus] = useState<WorktreePoolStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [deletingSlotId, setDeletingSlotId] = useState<number | null>(null)
  const [reconcilingPool, setReconcilingPool] = useState(false)

  const loadPoolStatus = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const status = await apiClient.getWorktreePoolStatus(codebaseId)
      setPoolStatus(status)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load worktree pool status')
    } finally {
      setLoading(false)
    }
  }, [codebaseId])

  useEffect(() => {
    loadPoolStatus()

    // Auto-refresh every 10 seconds
    const intervalId = setInterval(loadPoolStatus, 10000)

    return () => clearInterval(intervalId)
  }, [loadPoolStatus])

  const handleOpenInVSCode = (path: string) => {
    window.location.href = `vscode://file${path}`
  }

  const handleCopyPath = (path: string) => {
    navigator.clipboard.writeText(path)
    alert(`Path copied to clipboard: ${path}`)
  }

  const handleDeleteSlot = async (slotId: number, force: boolean = false) => {
    const confirmed = window.confirm(
      `Delete this worktree? This will remove the worktree directory from disk.${
        force ? ' (Force delete)' : ''
      }`
    )
    if (!confirmed) return

    setDeletingSlotId(slotId)
    try {
      await apiClient.deleteWorktreeSlot(slotId, force)
      await loadPoolStatus()
    } catch (err) {
      alert(`Failed to delete worktree: ${err instanceof Error ? err.message : 'Unknown error'}`)
    } finally {
      setDeletingSlotId(null)
    }
  }

  const handleReconcilePool = async () => {
    setReconcilingPool(true)
    try {
      await apiClient.reconcileWorktreePool(codebaseId)
      await loadPoolStatus()
      alert('Worktree pool reconciled successfully!')
    } catch (err) {
      alert(`Failed to reconcile pool: ${err instanceof Error ? err.message : 'Unknown error'}`)
    } finally {
      setReconcilingPool(false)
    }
  }

  const renderSlotCard = (slot: WorktreeSlot) => {
    const isLocked = slot.status === 'locked'
    const isDeleting = deletingSlotId === slot.id

    return (
      <Card key={slot.id} className="border border-gray-200 dark:border-gray-700">
        <div className="space-y-3">
          {/* Header */}
          <div className="flex items-start justify-between">
            <div className="flex-1">
              <div className="flex items-center space-x-2 mb-1">
                <h4 className={`text-sm font-semibold ${textColors.primary}`}>
                  {slot.is_main_repo ? 'Main Repository' : `Worktree ${slot.path.split('.worktree-')[1] || ''}`}
                </h4>
                <StatusBadge variant={isLocked ? 'warning' : 'success'} size="sm">
                  {isLocked ? '🔒 Locked' : '✓ Available'}
                </StatusBadge>
              </div>
              <code className="text-xs font-mono bg-gray-100 dark:bg-gray-800 px-2 py-0.5 rounded block truncate">
                {slot.path}
              </code>
            </div>
          </div>

          {/* Status Details */}
          <div className="space-y-1 text-xs">
            {slot.current_branch && (
              <div className="flex items-center justify-between">
                <span className={textColors.secondary}>Branch:</span>
                <code className="font-mono bg-gray-100 dark:bg-gray-800 px-2 py-0.5 rounded">
                  {slot.current_branch}
                </code>
              </div>
            )}

            {slot.last_used_at && (
              <div className="flex items-center justify-between">
                <span className={textColors.secondary}>Last used:</span>
                <span className={textColors.secondary}>
                  {new Date(slot.last_used_at).toLocaleString()}
                </span>
              </div>
            )}

            {/* Show locked task OR last used task (not both) */}
            {isLocked && slot.locked_by_task && (
              <div className="flex items-center justify-between">
                <span className={textColors.secondary}>Locked by:</span>
                <span className="text-orange-600 dark:text-orange-400 font-medium truncate ml-2" title={slot.locked_by_task.title}>
                  {slot.locked_by_task.title}
                </span>
              </div>
            )}

            {!isLocked && slot.last_used_by_task && (
              <div className="flex items-center justify-between">
                <span className={textColors.secondary}>Last used by:</span>
                <span className="text-blue-600 dark:text-blue-400 font-medium truncate ml-2" title={slot.last_used_by_task.title}>
                  {slot.last_used_by_task.title}
                </span>
              </div>
            )}

            {isLocked && slot.locked_at && (
              <div className="flex items-center justify-between">
                <span className={textColors.secondary}>Locked since:</span>
                <span className={textColors.secondary}>
                  {new Date(slot.locked_at).toLocaleString()}
                </span>
              </div>
            )}
          </div>

          {/* Actions */}
          <div className="flex space-x-2 pt-2 border-t border-gray-200 dark:border-gray-700">
            <Button
              onClick={() => handleOpenInVSCode(slot.path)}
              variant="secondary"
              size="sm"
              icon={<FolderOpenIcon className="w-3 h-3" />}
              className="flex-1"
            >
              Open
            </Button>
            <Button
              onClick={() => handleCopyPath(slot.path)}
              variant="secondary"
              size="sm"
              icon={<CommandLineIcon className="w-3 h-3" />}
              title="Copy path"
            />
            {!slot.is_main_repo && (
              <Button
                onClick={() => handleDeleteSlot(slot.id, isLocked)}
                variant="secondary"
                size="sm"
                icon={<TrashIcon className="w-3 h-3" />}
                disabled={isDeleting}
                loading={isDeleting}
                className="text-red-600 hover:text-red-700 dark:text-red-400 dark:hover:text-red-300"
                title="Delete worktree"
              />
            )}
          </div>
        </div>
      </Card>
    )
  }

  if (loading && !poolStatus) {
    return (
      <Card>
        <div className="animate-pulse space-y-4">
          <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-1/3"></div>
          <div className="h-20 bg-gray-200 dark:bg-gray-700 rounded"></div>
          <div className="h-20 bg-gray-200 dark:bg-gray-700 rounded"></div>
        </div>
      </Card>
    )
  }

  if (error) {
    return (
      <Card>
        <div className="text-red-600 dark:text-red-400">
          Error: {error}
          <Button
            onClick={loadPoolStatus}
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

  if (!poolStatus) {
    return null
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <Card>
        <div className="flex items-center justify-between">
          <div>
            <h2 className={`text-lg font-bold ${textColors.primary} mb-1`}>Worktree Pool</h2>
            <p className={`text-sm ${textColors.secondary}`}>
              {poolStatus.stats.total_slots} slot{poolStatus.stats.total_slots !== 1 ? 's' : ''} •{' '}
              {poolStatus.stats.available} available •{' '}
              {poolStatus.stats.locked} locked
            </p>
          </div>
          <div className="flex space-x-2">
            <Button
              onClick={loadPoolStatus}
              variant="secondary"
              size="sm"
              icon={<ArrowPathIcon className="w-4 h-4" />}
              disabled={loading}
            >
              Refresh
            </Button>
            <Button
              onClick={handleReconcilePool}
              variant="secondary"
              size="sm"
              icon={<LockOpenIcon className="w-4 h-4" />}
              loading={reconcilingPool}
              disabled={reconcilingPool}
            >
              Reconcile
            </Button>
          </div>
        </div>
      </Card>

      {/* Slots Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {poolStatus.slots.map(renderSlotCard)}
      </div>

      {poolStatus.slots.length === 0 && (
        <Card>
          <p className={`text-center ${textColors.secondary} py-8`}>
            No worktree slots found. Slots will be created automatically when needed.
          </p>
        </Card>
      )}
    </div>
  )
}
