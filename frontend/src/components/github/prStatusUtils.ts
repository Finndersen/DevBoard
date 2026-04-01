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

export interface ReviewInfo {
  icon: string
  colorClass: string
  tooltip: string
}

export function getReviewInfo(decision: string | null): ReviewInfo | null {
  if (!decision) return null
  switch (decision.toUpperCase()) {
    case 'APPROVED':
      return { icon: '✔', colorClass: 'text-green-500', tooltip: 'Approved' }
    case 'CHANGES_REQUESTED':
      return { icon: '✎', colorClass: 'text-red-500', tooltip: 'Changes requested' }
    case 'REVIEW_REQUIRED':
      return { icon: '◷', colorClass: 'text-yellow-500', tooltip: 'Review required' }
    default:
      return null
  }
}
