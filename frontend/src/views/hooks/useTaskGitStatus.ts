import { useState, useEffect, useCallback, useRef } from 'react'
import type { TaskGitStatus, TaskBranchInfo, TaskDiffResponse } from '../../lib/api'
import { apiClient } from '../../lib/api'

interface UseTaskGitStatusParams {
  taskId: number | undefined
  codebaseId: number | null | undefined
  activeTab: string
}

interface UseTaskGitStatusResult {
  gitStatus: TaskGitStatus | null
  setGitStatus: (status: TaskGitStatus | null) => void
  showBranchStatusModal: boolean
  setShowBranchStatusModal: (show: boolean) => void
  branchStatusLoading: boolean
  branchInfo: TaskBranchInfo | null
  branchInfoLoading: boolean
  diffData: TaskDiffResponse | null
  diffLoading: boolean
  lastDiffUpdate: string | null
  diffRefreshTimeoutRef: React.MutableRefObject<ReturnType<typeof setTimeout> | null>
  diffInFlightRef: React.MutableRefObject<boolean>
  branchInfoInFlightRef: React.MutableRefObject<boolean>
  gitStatusInFlightRef: React.MutableRefObject<boolean>
  fetchTaskBranchInfo: () => Promise<void>
  fetchTaskDiff: (view: string) => Promise<void>
  handleDiffRefresh: (view: string) => Promise<void>
  handleOpenBranchStatusModal: () => Promise<void>
  refreshGitStatus: () => Promise<void>
}

export function useTaskGitStatus({ taskId, codebaseId, activeTab }: UseTaskGitStatusParams): UseTaskGitStatusResult {
  const [gitStatus, setGitStatus] = useState<TaskGitStatus | null>(null)
  const [showBranchStatusModal, setShowBranchStatusModal] = useState(false)
  const [branchStatusLoading, setBranchStatusLoading] = useState(false)
  const [branchInfo, setBranchInfo] = useState<TaskBranchInfo | null>(null)
  const [branchInfoLoading, setBranchInfoLoading] = useState(false)
  const [diffData, setDiffData] = useState<TaskDiffResponse | null>(null)
  const [diffLoading, setDiffLoading] = useState(false)
  const [lastDiffUpdate, setLastDiffUpdate] = useState<string | null>(null)

  const diffRefreshTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const branchInfoInFlightRef = useRef(false)
  const diffInFlightRef = useRef(false)
  const gitStatusInFlightRef = useRef(false)

  const fetchTaskBranchInfo = useCallback(async () => {
    if (!taskId || branchInfoInFlightRef.current) return
    branchInfoInFlightRef.current = true
    setBranchInfoLoading(true)
    try {
      const response = await apiClient.getTaskBranchInfo(taskId)
      setBranchInfo(response)
    } catch (error) {
      console.error('Failed to fetch task branch info:', error)
    } finally {
      setBranchInfoLoading(false)
      branchInfoInFlightRef.current = false
    }
  }, [taskId])

  const fetchTaskDiff = useCallback(async (view: string) => {
    if (!taskId || diffInFlightRef.current) return
    diffInFlightRef.current = true
    setDiffLoading(true)
    try {
      const response = await apiClient.getTaskDiff(taskId, view)
      setDiffData(response)
      setLastDiffUpdate(new Date().toISOString())
    } catch (error) {
      console.error('Failed to fetch task diff:', error)
    } finally {
      setDiffLoading(false)
      diffInFlightRef.current = false
    }
  }, [taskId])

  const handleDiffRefresh = useCallback(async (view: string) => {
    if (!taskId) return
    await fetchTaskBranchInfo()
    await fetchTaskDiff(view)
  }, [taskId, fetchTaskBranchInfo, fetchTaskDiff])

  const handleOpenBranchStatusModal = useCallback(async () => {
    if (!taskId) return
    setBranchStatusLoading(true)
    setShowBranchStatusModal(true)
    try {
      const status = await apiClient.getTaskGitStatus(taskId)
      setGitStatus(status)
    } catch (error) {
      console.error('Failed to fetch git status:', error)
      setGitStatus(null)
    } finally {
      setBranchStatusLoading(false)
    }
  }, [taskId])

  const refreshGitStatus = useCallback(async () => {
    if (!taskId || gitStatusInFlightRef.current) return
    gitStatusInFlightRef.current = true
    try {
      const status = await apiClient.getTaskGitStatus(taskId)
      setGitStatus(status)
    } catch (error) {
      console.error('Failed to refresh git status:', error)
    } finally {
      gitStatusInFlightRef.current = false
    }
  }, [taskId])

  // Auto-fetch branch info and initial diff when Changes tab is first opened
  useEffect(() => {
    if (activeTab === 'changes' && !branchInfo && !branchInfoLoading && codebaseId) {
      fetchTaskBranchInfo().then(() => {
        fetchTaskDiff('all')
      })
    }
  }, [activeTab, branchInfo, branchInfoLoading, codebaseId, fetchTaskBranchInfo, fetchTaskDiff])

  // Fetch git status on task load to show branch icon in header
  useEffect(() => {
    if (taskId && codebaseId) {
      apiClient.getTaskGitStatus(taskId)
        .then(status => setGitStatus(status))
        .catch(error => {
          console.error('Failed to fetch git status:', error)
          setGitStatus(null)
        })
    }
  }, [taskId, codebaseId])

  return {
    gitStatus,
    setGitStatus,
    showBranchStatusModal,
    setShowBranchStatusModal,
    branchStatusLoading,
    branchInfo,
    branchInfoLoading,
    diffData,
    diffLoading,
    lastDiffUpdate,
    diffRefreshTimeoutRef,
    diffInFlightRef,
    branchInfoInFlightRef,
    gitStatusInFlightRef,
    fetchTaskBranchInfo,
    fetchTaskDiff,
    handleDiffRefresh,
    handleOpenBranchStatusModal,
    refreshGitStatus,
  }
}
