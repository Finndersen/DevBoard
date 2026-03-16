import { useState, useEffect, useCallback } from 'react'
import { TrashIcon } from '@heroicons/react/24/outline'
import { apiClient, type WorktreePoolStatus, type WorktreeSlot } from '../../lib/api'
import { Card, StatusBadge, ConfirmDialog } from '../ui'
import { textColors } from '../../styles/designSystem'
import { useUIStore } from '../../stores/uiStore'

interface WorktreeSlotsTabProps {
  codebaseId: string
}

export default function WorktreeSlotsTab({ codebaseId }: WorktreeSlotsTabProps) {
  const { navigateTo } = useUIStore()
  const [poolStatus, setPoolStatus] = useState<WorktreePoolStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [deletingSlotId, setDeletingSlotId] = useState<number | null>(null)
  const [slotToDelete, setSlotToDelete] = useState<WorktreeSlot | null>(null)
  const [deleteError, setDeleteError] = useState<string | null>(null)

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
  }, [loadPoolStatus])

  const formatTimestamp = (timestamp: string | null): string => {
    if (!timestamp) return '-'
    return new Date(timestamp).toLocaleString()
  }

  const getSlotIdentifier = (slot: WorktreeSlot): string => {
    if (slot.is_main_repo) {
      return 'Main Repository'
    }
    const worktreeNumber = slot.path.split('.worktree-')[1]
    return worktreeNumber ? `Worktree #${worktreeNumber}` : 'Worktree'
  }

  const getDeleteTooltip = (slot: WorktreeSlot): string | undefined => {
    if (slot.status === 'locked') return 'Cannot delete: slot is locked by a task'
    if (slot.has_uncommitted_changes) return 'Cannot delete: worktree has uncommitted changes'
    return undefined
  }

  const handleDeleteConfirm = async () => {
    if (!slotToDelete) return
    setDeletingSlotId(slotToDelete.id)
    setDeleteError(null)
    try {
      await apiClient.deleteWorktreeSlot(slotToDelete.id)
      setSlotToDelete(null)
      await loadPoolStatus()
    } catch (err) {
      setDeleteError(err instanceof Error ? err.message : 'Failed to delete worktree slot')
    } finally {
      setDeletingSlotId(null)
    }
  }

  const renderSlotCard = (slot: WorktreeSlot) => {
    const isLocked = slot.status === 'locked'
    const isDeleteDisabled = isLocked || slot.has_uncommitted_changes || deletingSlotId === slot.id
    const deleteTooltip = getDeleteTooltip(slot)

    return (
      <Card key={slot.id} className="border border-gray-200 dark:border-gray-700">
        <div className="space-y-3">
          {/* Header with identifier and status */}
          <div className="flex items-start justify-between">
            <div className="flex-1">
              <div className="flex items-center space-x-2 mb-1">
                <h4 className={`text-sm font-semibold ${textColors.primary}`}>
                  {getSlotIdentifier(slot)}
                </h4>
                <StatusBadge variant={isLocked ? 'warning' : 'success'} size="sm">
                  {isLocked ? 'Locked' : 'Available'}
                </StatusBadge>
                {slot.has_uncommitted_changes && (
                  <StatusBadge variant="warning" size="sm">
                    {slot.uncommitted_change_count} uncommitted {slot.uncommitted_change_count === 1 ? 'change' : 'changes'}
                  </StatusBadge>
                )}
              </div>
            </div>
            {!slot.is_main_repo && (
              <button
                onClick={() => !isDeleteDisabled && setSlotToDelete(slot)}
                disabled={isDeleteDisabled}
                title={deleteTooltip}
                className="ml-2 p-1.5 rounded text-gray-400 hover:text-red-600 dark:hover:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:text-gray-400 disabled:hover:bg-transparent"
              >
                <TrashIcon className="w-4 h-4" />
              </button>
            )}
          </div>

          {/* Details */}
          <div className="space-y-2 text-xs">
            <div className="flex items-center justify-between gap-2">
              <span className={`shrink-0 ${textColors.secondary}`}>Path:</span>
              <code className="font-mono bg-gray-100 dark:bg-gray-800 text-gray-800 dark:text-gray-200 px-2 py-0.5 rounded truncate min-w-0">
                {slot.path}
              </code>
            </div>

            {slot.current_branch && (
              <div className="flex items-center justify-between gap-2">
                <span className={`shrink-0 ${textColors.secondary}`}>Branch:</span>
                <code className="font-mono bg-gray-100 dark:bg-gray-800 text-gray-800 dark:text-gray-200 px-2 py-0.5 rounded truncate min-w-0">
                  {slot.current_branch}
                </code>
              </div>
            )}

            <div className="flex items-center justify-between gap-2">
              <span className={`shrink-0 ${textColors.secondary}`}>Last used:</span>
              <span className={textColors.secondary}>{formatTimestamp(slot.last_used_at)}</span>
            </div>

            {isLocked && slot.locked_by_task && (
              <div className="flex items-center justify-between gap-2">
                <span className={`shrink-0 ${textColors.secondary}`}>Locked by:</span>
                <button
                  className="text-orange-600 dark:text-orange-400 hover:underline truncate min-w-0 text-left"
                  onClick={() => navigateTo({ type: 'task', entityId: String(slot.locked_by_task!.id), title: slot.locked_by_task!.title })}
                >
                  Task {slot.locked_by_task.id}: {slot.locked_by_task.title}
                </button>
              </div>
            )}

            {!isLocked && slot.last_used_by_task && (
              <div className="flex items-center justify-between gap-2">
                <span className={`shrink-0 ${textColors.secondary}`}>Last active task:</span>
                <button
                  className="text-blue-600 dark:text-blue-400 hover:underline truncate min-w-0 text-left"
                  onClick={() => navigateTo({ type: 'task', entityId: String(slot.last_used_by_task!.id), title: slot.last_used_by_task!.title })}
                >
                  Task {slot.last_used_by_task.id}: {slot.last_used_by_task.title}
                </button>
              </div>
            )}
          </div>
        </div>
      </Card>
    )
  }

  // Loading state
  if (loading && !poolStatus) {
    return (
      <div className="space-y-4">
        <Card>
          <div className="animate-pulse space-y-3">
            <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-1/3"></div>
            <div className="h-3 bg-gray-200 dark:bg-gray-700 rounded w-1/2"></div>
          </div>
        </Card>
        <div className="space-y-4">
          {[1, 2].map((i) => (
            <Card key={i}>
              <div className="animate-pulse space-y-3">
                <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-1/2"></div>
                <div className="h-8 bg-gray-200 dark:bg-gray-700 rounded"></div>
                <div className="h-3 bg-gray-200 dark:bg-gray-700 rounded w-3/4"></div>
              </div>
            </Card>
          ))}
        </div>
      </div>
    )
  }

  // Error state
  if (error) {
    return (
      <Card>
        <div className="text-center py-6">
          <p className="text-red-600 dark:text-red-400 mb-3">
            Failed to load worktree pool status
          </p>
          <p className={`text-sm ${textColors.secondary} mb-4`}>{error}</p>
          <button
            onClick={loadPoolStatus}
            className="px-4 py-2 text-sm font-medium text-blue-600 dark:text-blue-400 hover:text-blue-700 dark:hover:text-blue-300 border border-blue-600 dark:border-blue-400 rounded-md hover:bg-blue-50 dark:hover:bg-blue-900/20 transition-colors"
          >
            Retry
          </button>
        </div>
      </Card>
    )
  }

  if (!poolStatus) {
    return null
  }

  return (
    <div className="space-y-4">
      {/* Pool Statistics Summary */}
      <Card>
        <div className="flex items-center justify-between">
          <div>
            <h3 className={`text-sm font-semibold ${textColors.primary} mb-1`}>
              Worktree Pool Statistics
            </h3>
            <p className={`text-sm ${textColors.secondary}`}>
              Overview of worktree slot allocation for this codebase
            </p>
            <p className={`text-xs ${textColors.secondary} mt-1`}>
              Additional worktrees are created automatically on demand when new tasks need them.
            </p>
          </div>
          <div className="flex space-x-6">
            <div className="text-center">
              <div className={`text-2xl font-bold ${textColors.primary}`}>
                {poolStatus.stats.total_slots}
              </div>
              <div className={`text-xs ${textColors.secondary}`}>Total</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-green-600 dark:text-green-400">
                {poolStatus.stats.available}
              </div>
              <div className={`text-xs ${textColors.secondary}`}>Available</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-orange-600 dark:text-orange-400">
                {poolStatus.stats.locked}
              </div>
              <div className={`text-xs ${textColors.secondary}`}>Locked</div>
            </div>
          </div>
        </div>
      </Card>

      {/* Delete error */}
      {deleteError && (
        <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-md p-3">
          <p className="text-sm text-red-600 dark:text-red-400">{deleteError}</p>
        </div>
      )}

      {/* Slots List */}
      {poolStatus.slots.length > 0 ? (
        <div className="space-y-4">
          {poolStatus.slots.map(renderSlotCard)}
        </div>
      ) : (
        <Card>
          <p className={`text-center ${textColors.secondary} py-8`}>
            No worktree slots found. Slots will be created automatically when tasks are started.
          </p>
        </Card>
      )}

      {/* Delete Confirmation Dialog */}
      <ConfirmDialog
        isOpen={slotToDelete !== null}
        onClose={() => { setSlotToDelete(null); setDeleteError(null) }}
        onConfirm={handleDeleteConfirm}
        title="Delete Worktree"
        message="Are you sure you want to delete this worktree? The directory will be removed from disk."
        confirmText="Delete"
        variant="danger"
        loading={deletingSlotId !== null}
      />
    </div>
  )
}
