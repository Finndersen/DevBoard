export interface StatusInfo {
  icon: string
  colorClass: string
  tooltip: string
}

export function getStatusInfo(mergeableState: string | null, ciStatus: string | null): StatusInfo {
  // Merge conflicts take highest priority
  if (mergeableState?.toUpperCase() === 'DIRTY') {
    return { icon: '⇄', colorClass: 'text-red-500', tooltip: 'Has merge conflicts' }
  }

  // CI failure/error
  if (ciStatus?.toUpperCase() === 'FAILURE' || ciStatus?.toUpperCase() === 'ERROR') {
    return { icon: '✗', colorClass: 'text-red-500', tooltip: 'CI checks failing' }
  }

  // CI pending
  if (ciStatus?.toUpperCase() === 'PENDING' || ciStatus?.toUpperCase() === 'EXPECTED') {
    return { icon: '○', colorClass: 'text-yellow-500', tooltip: 'CI checks pending' }
  }

  // PR is in the merge queue
  if (mergeableState?.toUpperCase() === 'QUEUED') {
    return { icon: '⏎', colorClass: 'text-blue-500', tooltip: 'Queued for merge' }
  }

  // Branch behind or blocked (no CI issue but not ready)
  if (mergeableState?.toUpperCase() === 'BEHIND') {
    return { icon: '↓', colorClass: 'text-yellow-500', tooltip: 'Branch is behind base' }
  }
  if (mergeableState?.toUpperCase() === 'BLOCKED') {
    return { icon: '⊘', colorClass: 'text-yellow-500', tooltip: 'Blocked by branch protection' }
  }

  // All good
  if (mergeableState?.toUpperCase() === 'CLEAN' && ciStatus?.toUpperCase() === 'SUCCESS') {
    return { icon: '✓', colorClass: 'text-green-500', tooltip: 'Ready to merge' }
  }

  // CI passing but merge state not clean/known
  if (ciStatus?.toUpperCase() === 'SUCCESS') {
    return { icon: '✓', colorClass: 'text-green-500', tooltip: 'CI checks passing' }
  }

  // Unknown / no CI configured
  return { icon: '○', colorClass: 'text-gray-400', tooltip: 'Status unknown' }
}

export function StatusIndicator({ mergeableState, ciStatus }: { mergeableState: string | null; ciStatus: string | null }) {
  const { icon, colorClass, tooltip } = getStatusInfo(mergeableState, ciStatus)
  return (
    <span className={`text-sm font-bold flex-shrink-0 leading-none ${colorClass}`} title={tooltip}>
      {icon}
    </span>
  )
}

export function ReviewBadge({ decision }: { decision: string | null }) {
  if (!decision) return null
  switch (decision) {
    case 'APPROVED':
      return <span className="text-xs px-1.5 py-0.5 rounded-full bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400" title="Approved">Approved</span>
    case 'CHANGES_REQUESTED':
      return <span className="text-xs px-1.5 py-0.5 rounded-full bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400" title="Changes requested">Changes</span>
    case 'REVIEW_REQUIRED':
      return <span className="text-xs px-1.5 py-0.5 rounded-full bg-yellow-100 dark:bg-yellow-900/30 text-yellow-700 dark:text-yellow-400" title="Review required">Review needed</span>
    default:
      return null
  }
}
