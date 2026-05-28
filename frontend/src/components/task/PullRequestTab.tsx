import { useState } from 'react'
import { ArrowPathIcon, WrenchScrewdriverIcon, ChevronDownIcon, ChevronRightIcon, ArrowTopRightOnSquareIcon } from '@heroicons/react/24/outline'
import { TaskStatus } from '../../lib/api'
import type { GitHubPRStatusResponse, PRFeedbackResponse, PRDetailResponse, PRCheckItem } from '../../lib/api'
import { textColors, surfaces, borderColors, statusColors, loadingSpinner } from '../../styles/designSystem'
import { StatusIndicator, ReviewBadge } from '../github/PRStatusComponents'
import { CommentsTab } from './CommentsTab'
import { countPRComments } from './prUtils'

interface PullRequestTabProps {
  prStatus: GitHubPRStatusResponse | null
  prStatusLoading: boolean
  prFeedback: PRFeedbackResponse | null
  prDetail: PRDetailResponse | null
  prDetailLoading: boolean
  taskStatus: TaskStatus
  onRefreshPrStatus: () => void
  onResolveConflicts: () => void
  onSubmitComments: (message: string) => void
  isConversationStreaming: boolean
}

function CiCheckRow({ check }: { check: PRCheckItem }) {
  const state = check.state.toUpperCase()
  let icon: string
  let colorClass: string
  if (state === 'SUCCESS') {
    icon = '✓'
    colorClass = 'text-green-500'
  } else if (state === 'FAILURE' || state === 'ERROR') {
    icon = '✗'
    colorClass = 'text-red-500'
  } else {
    icon = '○'
    colorClass = 'text-yellow-500'
  }

  return (
    <div className={`flex items-center gap-3 px-4 py-2.5 border-b last:border-b-0 ${borderColors.default}`}>
      <span className={`text-sm font-bold flex-shrink-0 ${colorClass}`}>{icon}</span>
      <span className={`text-sm flex-1 ${textColors.primary}`}>{check.name}</span>
      {check.description && (
        <span className={`text-xs ${textColors.muted}`}>{check.description}</span>
      )}
    </div>
  )
}

function ciSummaryText(checks: PRCheckItem[]): { text: string; colorClass: string } {
  if (checks.length === 0) return { text: '', colorClass: textColors.muted }
  
  let passing = 0
  let failing = 0
  for (const check of checks) {
    const state = check.state.toUpperCase()
    if (state === 'SUCCESS') {
      passing++
    } else if (state === 'FAILURE' || state === 'ERROR') {
      failing++
    }
  }
  
  if (failing > 0) {
    return { text: `${failing}/${checks.length} failing`, colorClass: 'text-red-500' }
  }
  if (passing === checks.length) {
    return { text: `${passing}/${checks.length} passing`, colorClass: 'text-green-500' }
  }
  return { text: `${passing}/${checks.length} passing`, colorClass: 'text-yellow-500' }
}

function StatusOverviewBar({
  prStatus,
  prStatusLoading,
  taskStatus,
  onRefreshPrStatus,
  onResolveConflicts,
  isConversationStreaming,
}: {
  prStatus: GitHubPRStatusResponse | null
  prStatusLoading: boolean
  taskStatus: TaskStatus
  onRefreshPrStatus: () => void
  onResolveConflicts: () => void
  isConversationStreaming: boolean
}) {
  const isPrOpen = taskStatus === TaskStatus.PR_OPEN
  const isDirty = prStatus?.mergeable_state?.toUpperCase() === 'DIRTY'

  return (
    <div className={`flex items-center justify-between px-4 py-3 ${surfaces.sunken} border ${borderColors.default} rounded-lg`}>
      {prStatus ? (
        <div className="flex items-center gap-3 flex-wrap">
          <a
            href={prStatus.pr_url}
            target="_blank"
            rel="noopener noreferrer"
            className={`flex items-center gap-1 text-sm font-medium ${textColors.accent} hover:opacity-80 transition-opacity`}
            title="Open PR in GitHub"
          >
            #{prStatus.pr_number}
            <ArrowTopRightOnSquareIcon className="w-3 h-3 flex-shrink-0 opacity-60 hover:opacity-100" />
          </a>
          <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
            prStatus.merged
              ? `${statusColors.info.bg} ${statusColors.info.text}`
              : `${statusColors.success.bg} ${statusColors.success.text}`
          }`}>
            {prStatus.merged ? 'Merged' : prStatus.state}
          </span>
          <StatusIndicator
            mergeableState={prStatus.mergeable_state}
            ciStatus={prStatus.ci_status}
            reviewDecision={prStatus.review_decision}
          />
          <ReviewBadge decision={prStatus.review_decision} />
        </div>
      ) : prStatusLoading ? (
        <div className="flex items-center gap-2">
          <div className={loadingSpinner} style={{ width: "1rem", height: "1rem" }} />
          <span className={`text-sm ${textColors.muted}`}>Loading PR status…</span>
        </div>
      ) : (
        <span className={`text-sm ${textColors.muted}`}>No PR status available</span>
      )}

      {isPrOpen && (
        <div className="flex items-center gap-2 flex-shrink-0">
          {isDirty && (
            <button
              onClick={onResolveConflicts}
              disabled={isConversationStreaming}
              className={`flex items-center gap-1.5 px-2.5 py-1.5 text-xs border ${borderColors.default} rounded-md ${textColors.secondary} hover:bg-gray-100 dark:hover:bg-white/[0.08] disabled:opacity-50 disabled:cursor-not-allowed transition-colors`}
              title="Rebase branch"
            >
              <WrenchScrewdriverIcon className="w-3.5 h-3.5" />
              Rebase
            </button>
          )}
          <button
            onClick={onRefreshPrStatus}
            disabled={prStatusLoading}
            className={`flex items-center gap-1.5 px-2.5 py-1.5 text-xs border ${borderColors.default} rounded-md ${textColors.secondary} hover:bg-gray-100 dark:hover:bg-white/[0.08] disabled:opacity-50 disabled:cursor-not-allowed transition-colors`}
            title="Refresh PR status"
          >
            <ArrowPathIcon className={`w-3.5 h-3.5 ${prStatusLoading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>
      )}
    </div>
  )
}

function CiChecksSection({
  prDetail,
  prDetailLoading,
}: {
  prDetail: PRDetailResponse | null
  prDetailLoading: boolean
}) {
  const [expanded, setExpanded] = useState(true)
  const checks = prDetail?.checks ?? []
  const { text: summaryText, colorClass: summaryColor } = ciSummaryText(checks)

  return (
    <div>
      <button
        onClick={() => setExpanded(e => !e)}
        className={`flex items-center gap-2 w-full text-left mb-3 ${textColors.secondary} hover:text-gray-900 dark:hover:text-gray-100 transition-colors`}
      >
        {expanded
          ? <ChevronDownIcon className="w-4 h-4 flex-shrink-0" />
          : <ChevronRightIcon className="w-4 h-4 flex-shrink-0" />
        }
        <span className={`text-sm font-medium ${textColors.primary}`}>CI Checks</span>
        {summaryText && (
          <span className={`text-xs ${summaryColor}`}>{summaryText}</span>
        )}
      </button>

      {expanded && (
        <div className={`border ${borderColors.default} rounded-lg overflow-hidden`}>
          {prDetailLoading ? (
            <div className="flex items-center gap-2 px-4 py-3">
              <div className={loadingSpinner} style={{ width: "1rem", height: "1rem" }} />
              <span className={`text-sm ${textColors.muted}`}>Loading CI checks…</span>
            </div>
          ) : checks.length === 0 ? (
            <div className={`px-4 py-3 text-sm ${textColors.muted}`}>No CI checks</div>
          ) : (
            checks.map((check, i) => <CiCheckRow key={i} check={check} />)
          )}
        </div>
      )}
    </div>
  )
}

function ReviewsSection({
  prFeedback,
  onSubmitComments,
}: {
  prFeedback: PRFeedbackResponse | null
  onSubmitComments: (message: string) => void
}) {
  const count = prFeedback ? countPRComments(prFeedback) : 0

  return (
    <div>
      <div className="flex items-center gap-2 mb-3">
        <span className={`text-sm font-medium ${textColors.primary}`}>Reviews &amp; Comments</span>
        {count > 0 && (
          <span className={`text-xs px-1.5 py-0.5 rounded-full ${surfaces.sunken} ${textColors.muted}`}>
            {count}
          </span>
        )}
      </div>

      {prFeedback && count > 0 ? (
        <CommentsTab prFeedback={prFeedback} onSubmitComments={onSubmitComments} />
      ) : (
        <p className={`text-sm ${textColors.muted}`}>No reviews or comments yet</p>
      )}
    </div>
  )
}

export function PullRequestTab({
  prStatus,
  prStatusLoading,
  prFeedback,
  prDetail,
  prDetailLoading,
  taskStatus,
  onRefreshPrStatus,
  onResolveConflicts,
  onSubmitComments,
  isConversationStreaming,
}: PullRequestTabProps) {
  return (
    <div className="h-full overflow-y-auto space-y-6 p-1">
      <StatusOverviewBar
        prStatus={prStatus}
        prStatusLoading={prStatusLoading}
        taskStatus={taskStatus}
        onRefreshPrStatus={onRefreshPrStatus}
        onResolveConflicts={onResolveConflicts}
        isConversationStreaming={isConversationStreaming}
      />
      <CiChecksSection
        prDetail={prDetail}
        prDetailLoading={prDetailLoading}
      />
      <ReviewsSection
        prFeedback={prFeedback}
        onSubmitComments={onSubmitComments}
      />
    </div>
  )
}
