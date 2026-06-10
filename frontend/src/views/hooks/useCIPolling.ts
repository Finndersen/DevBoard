import { useState, useEffect, useRef, useCallback } from 'react'
import { TaskStatus } from '../../lib/api'
import type { Task, PRDetailResponse, PRCheckItem } from '../../lib/api'
import { apiClient } from '../../lib/api'

const POLL_INTERVAL_MS = 30_000

export function formatCIFailureMessage(failingChecks: PRCheckItem[], prNumber: number): string {
  const checkLines = failingChecks.map(check =>
    check.description ? `- ${check.name}: ${check.description}` : `- ${check.name}`
  )
  return `The following CI checks are failing for PR #${prNumber}:\n\n${checkLines.join('\n')}\n\nPlease investigate and fix these CI failures.`
}

function getFailingChecks(checks: PRDetailResponse['checks']): PRDetailResponse['checks'] {
  return checks.filter(check => {
    const state = check.state.toUpperCase()
    return state === 'FAILURE' || state === 'ERROR'
  })
}

interface UseCIPollingParams {
  task: Task | null
  prDetail: PRDetailResponse | null
  isConversationStreaming: boolean
  onPRDetailUpdate: (detail: PRDetailResponse) => void
  onReportIssues: (message: string) => void
}

interface UseCIPollingReturn {
  autoResolve: boolean
  setAutoResolve: (value: boolean) => void
  reportCIIssues: () => void
}

export function useCIPolling({
  task,
  prDetail,
  isConversationStreaming,
  onPRDetailUpdate,
  onReportIssues,
}: UseCIPollingParams): UseCIPollingReturn {
  const [autoResolve, setAutoResolveState] = useState(false)
  const lastReportedKeyRef = useRef<string>('')

  // Stable refs for values read inside the polling callback — prevents the interval
  // from resetting on every render due to new callback/prop references.
  const onReportIssuesRef = useRef(onReportIssues)
  const onPRDetailUpdateRef = useRef(onPRDetailUpdate)
  const isConversationStreamingRef = useRef(isConversationStreaming)
  const autoResolveRef = useRef(autoResolve)
  // Tracks the latest prDetail from both the lazy-fetch and polling paths
  const prDetailRef = useRef(prDetail)
  const taskRef = useRef(task)

  // Update refs synchronously on each render so poll callback always reads fresh values
  onReportIssuesRef.current = onReportIssues
  onPRDetailUpdateRef.current = onPRDetailUpdate
  isConversationStreamingRef.current = isConversationStreaming
  autoResolveRef.current = autoResolve
  prDetailRef.current = prDetail
  taskRef.current = task

  const storageKey = task?.id ? `ci_auto_resolve_${task.id}` : null

  useEffect(() => {
    if (!storageKey) return
    const stored = localStorage.getItem(storageKey)
    setAutoResolveState(stored === 'true')
    lastReportedKeyRef.current = ''
  }, [storageKey])

  const setAutoResolve = useCallback((value: boolean) => {
    setAutoResolveState(value)
    if (storageKey) {
      localStorage.setItem(storageKey, String(value))
    }
  }, [storageKey])

  // Reset dedup key when task changes
  useEffect(() => {
    if (!task?.id) return
    lastReportedKeyRef.current = ''
  }, [task?.id])

  // Polling effect — only re-runs when the poll conditions change (not on callback identity changes)
  useEffect(() => {
    if (!task?.codebase_id || !task?.github_pr_number || task.status !== TaskStatus.PR_OPEN) {
      return
    }

    const codbaseId = task.codebase_id
    const prNumber = task.github_pr_number

    const poll = async () => {
      try {
        const detail = await apiClient.getPRDetail(codbaseId, prNumber)
        prDetailRef.current = detail
        onPRDetailUpdateRef.current(detail)

        const failingChecks = getFailingChecks(detail.checks)
        if (failingChecks.length > 0 && autoResolveRef.current && !isConversationStreamingRef.current) {
          const failingNames = failingChecks.map(c => c.name).sort().join('|')
          if (failingNames !== lastReportedKeyRef.current) {
            lastReportedKeyRef.current = failingNames
            onReportIssuesRef.current(formatCIFailureMessage(failingChecks, prNumber))
          }
        }
      } catch (error) {
        console.error('Failed to poll PR detail:', error)
      }
    }

    const intervalId = setInterval(poll, POLL_INTERVAL_MS)
    return () => clearInterval(intervalId)
  }, [task?.codebase_id, task?.github_pr_number, task?.status])

  // reportCIIssues reads from refs so it's stable and works with both lazy-fetched and polled data
  const reportCIIssues = useCallback(() => {
    const detail = prDetailRef.current
    const currentTask = taskRef.current
    if (!detail || !currentTask?.github_pr_number) return

    const failingChecks = getFailingChecks(detail.checks)
    if (failingChecks.length === 0) return

    onReportIssuesRef.current(formatCIFailureMessage(failingChecks, currentTask.github_pr_number))
    // Reset dedup so a subsequent auto-report can fire if failures persist
    lastReportedKeyRef.current = ''
  }, [])

  return { autoResolve, setAutoResolve, reportCIIssues }
}
