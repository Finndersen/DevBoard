import { useState, useEffect, useCallback } from 'react'
import { apiClient, type WorktreePoolStatus, type WorktreeSlot } from '../../lib/api'
import { Card, StatusBadge } from '../ui'
import { textColors } from '../../styles/designSystem'

interface WorktreeSlotsTabProps {
  codebaseId: string
}

export default function WorktreeSlotsTab({ codebaseId }: WorktreeSlotsTabProps) {
  const [poolStatus, setPoolStatus] = useState<WorktreePoolStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

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

  const renderSlotCard = (slot: WorktreeSlot) => {
    const isLocked = slot.status === 'locked'

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
              </div>
            </div>
          </div>

          {/* Path */}
          <div>
            <span className={`text-xs ${textColors.secondary} block mb-1`}>Path</span>
            <code className="text-xs font-mono bg-gray-100 dark:bg-gray-800 text-gray-800 dark:text-gray-200 px-2 py-1 rounded block truncate">
              {slot.path}
            </code>
          </div>

          {/* Details Grid */}
          <div className="space-y-2 text-xs">
            {slot.current_branch && (
              <div className="flex items-center justify-between">
                <span className={textColors.secondary}>Branch:</span>
                <code className="font-mono bg-gray-100 dark:bg-gray-800 text-gray-800 dark:text-gray-200 px-2 py-0.5 rounded">
                  {slot.current_branch}
                </code>
              </div>
            )}

            <div className="flex items-center justify-between">
              <span className={textColors.secondary}>Last used:</span>
              <span className={textColors.secondary}>
                {formatTimestamp(slot.last_used_at)}
              </span>
            </div>

            {isLocked && slot.locked_at && (
              <div className="flex items-center justify-between">
                <span className={textColors.secondary}>Locked since:</span>
                <span className={textColors.secondary}>
                  {formatTimestamp(slot.locked_at)}
                </span>
              </div>
            )}

            {isLocked && slot.locked_by_task && (
              <div className="pt-2 border-t border-gray-200 dark:border-gray-700">
                <span className={`${textColors.secondary} block mb-1`}>Locked by task:</span>
                <div className="bg-orange-50 dark:bg-orange-900/20 rounded p-2 space-y-1">
                  <div className="font-medium text-orange-700 dark:text-orange-300">
                    {slot.locked_by_task.title}
                  </div>
                  <div className="flex items-center justify-between text-orange-600 dark:text-orange-400">
                    <span>Task ID: {slot.locked_by_task.id}</span>
                    <code className="font-mono text-xs bg-orange-100 dark:bg-orange-900/30 px-1.5 py-0.5 rounded">
                      {slot.locked_by_task.branch}
                    </code>
                  </div>
                </div>
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
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
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

      {/* Slots Grid */}
      {poolStatus.slots.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {poolStatus.slots.map(renderSlotCard)}
        </div>
      ) : (
        <Card>
          <p className={`text-center ${textColors.secondary} py-8`}>
            No worktree slots found. Slots will be created automatically when tasks are started.
          </p>
        </Card>
      )}
    </div>
  )
}
