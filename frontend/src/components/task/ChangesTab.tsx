import type { TaskBranchInfo, TaskDiffResponse, PRFeedbackResponse } from '../../lib/api'
import type { CodeReviewStatus } from '../../views/hooks/useCodeReviewStatus'
import AllFilesDiffViewer from '../documents/AllFilesDiffViewer'

interface ChangesTabProps {
  branchInfo: TaskBranchInfo | null
  diffData: TaskDiffResponse | null
  diffLoading: boolean
  branchInfoLoading: boolean
  lastDiffUpdate: string | null
  prFeedback: PRFeedbackResponse | null
  onRefresh: (view: string) => Promise<void>
  onSubmitComments: (message: string) => void
  codeReviewStatus?: CodeReviewStatus
  onAutoReview?: () => void
  isStreaming: boolean
}

export function ChangesTab({
  branchInfo,
  diffData,
  diffLoading,
  branchInfoLoading,
  lastDiffUpdate,
  prFeedback,
  onRefresh,
  onSubmitComments,
  codeReviewStatus,
  onAutoReview,
  isStreaming,
}: ChangesTabProps) {
  return (
    <div className="h-full overflow-hidden">
      <AllFilesDiffViewer
        branchInfo={branchInfo}
        diffResponse={diffData}
        loading={diffLoading || branchInfoLoading}
        onRefresh={onRefresh}
        lastUpdated={lastDiffUpdate}
        onSubmitComments={onSubmitComments}
        prFeedback={prFeedback}
        codeReviewStatus={codeReviewStatus}
        onAutoReview={onAutoReview}
        isStreaming={isStreaming}
      />
    </div>
  )
}
