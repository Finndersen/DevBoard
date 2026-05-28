import { statusColors } from '../../styles/designSystem'
import { getStatusInfo } from './prStatusUtils'

export function StatusIndicator({
  mergeableState,
  ciStatus,
  reviewDecision,
}: {
  mergeableState: string | null
  ciStatus: string | null
  reviewDecision?: string | null
}) {
  const { icon, colorClass, tooltip } = getStatusInfo(mergeableState, ciStatus, reviewDecision)
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
      return <span className={`text-xs px-1.5 py-0.5 rounded-full ${statusColors.success.bg} ${statusColors.success.text}`} title="Approved">Approved</span>
    case 'CHANGES_REQUESTED':
      return <span className={`text-xs px-1.5 py-0.5 rounded-full ${statusColors.error.bg} ${statusColors.error.text}`} title="Changes requested">Changes</span>
    case 'REVIEW_REQUIRED':
      return <span className={`text-xs px-1.5 py-0.5 rounded-full ${statusColors.warning.bg} ${statusColors.warning.text}`} title="Review required">Review needed</span>
    default:
      return null
  }
}
