import { useState, useMemo, useCallback, useEffect } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { PlusIcon, ListBulletIcon, FunnelIcon, ChatBubbleLeftIcon, ArrowPathIcon, ArrowTopRightOnSquareIcon } from '@heroicons/react/24/outline'
import { useAllTasks, useProjects, useRefetchOnViewActivation } from '../hooks'
import { useOpenPRs } from '../hooks/useGitHubPRs'
import { Button, Card, ErrorMessage } from '../components/ui'
import { textColors, loadingSpinner } from '../styles/designSystem'
import { TaskStatus } from '../lib/api'
import type { TaskListItem, OpenPRItem } from '../lib/api'
import ViewHeader from '../components/layout/ViewHeader'
import { StatusIndicator, ReviewBadge } from '../components/github/PRStatusComponents'
import { useUIStore } from '../stores/uiStore'

const STATUS_COLUMNS: TaskStatus[] = [TaskStatus.PLANNING, TaskStatus.IMPLEMENTING, TaskStatus.PR_OPEN, TaskStatus.COMPLETE]

const STATUS_LABELS: Record<TaskStatus, string> = {
  [TaskStatus.PLANNING]: 'Planning',
  [TaskStatus.IMPLEMENTING]: 'Implementing',
  [TaskStatus.PR_OPEN]: 'PR Open',
  [TaskStatus.COMPLETE]: 'Complete',
}

function getStatusColor(status: TaskStatus) {
  switch (status) {
    case TaskStatus.PLANNING:
      return 'bg-blue-100 text-blue-800 dark:bg-blue-900/20 dark:text-blue-400'
    case TaskStatus.IMPLEMENTING:
      return 'bg-purple-100 text-purple-800 dark:bg-purple-900/20 dark:text-purple-400'
    case TaskStatus.PR_OPEN:
      return 'bg-orange-100 text-orange-800 dark:bg-orange-900/20 dark:text-orange-400'
    case TaskStatus.COMPLETE:
      return 'bg-green-100 text-green-800 dark:bg-green-900/20 dark:text-green-400'
    default:
      return 'bg-gray-100 text-gray-800 dark:bg-gray-900/20 dark:text-gray-400'
  }
}

export default function TasksList() {
  const location = useLocation()
  const navigate = useNavigate()
  const [selectedProjectId, setSelectedProjectId] = useState<number | undefined>(() => {
    const param = new URLSearchParams(location.search).get('project_id')
    if (!param) return undefined
    const parsed = Number(param)
    return Number.isNaN(parsed) ? undefined : parsed
  })
  const { data: tasks, loading: tasksLoading, error: tasksError, refetch: refetchTasks } = useAllTasks(selectedProjectId)
  const { data: projects } = useProjects()
  const { data: openPRsData, refetch: refetchOpenPRs } = useOpenPRs()
  const { createAndOpenDraft } = useUIStore()
  const [refreshing, setRefreshing] = useState(false)

  const handleRefresh = useCallback(async () => {
    setRefreshing(true)
    try {
      await Promise.all([refetchTasks(), refetchOpenPRs()])
    } finally {
      setRefreshing(false)
    }
  }, [refetchTasks, refetchOpenPRs])

  useRefetchOnViewActivation([refetchTasks, refetchOpenPRs])

  const prByTaskId = useMemo(() => {
    const map = new Map<number, OpenPRItem>()
    if (openPRsData) {
      for (const pr of openPRsData.prs) {
        if (pr.task_id !== null) {
          map.set(pr.task_id, pr)
        }
      }
    }
    return map
  }, [openPRsData])

  // Refetch when project filter changes
  useEffect(() => {
    refetchTasks()
  }, [selectedProjectId, refetchTasks])

  // Group tasks by status
  const taskGroups = useMemo(() => {
    if (!tasks) return {} as Record<string, TaskListItem[]>
    const groups = tasks.reduce((acc, task) => {
      const status = task.status
      if (!acc[status]) acc[status] = []
      acc[status].push(task)
      return acc
    }, {} as Record<string, TaskListItem[]>)

    // Sort tasks within each group by created_at descending
    Object.keys(groups).forEach(status => {
      groups[status].sort((a, b) =>
        new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
      )
    })

    return groups
  }, [tasks])

  const handleProjectFilterChange = useCallback((e: React.ChangeEvent<HTMLSelectElement>) => {
    const value = e.target.value
    setSelectedProjectId(value ? Number(value) : undefined)
  }, [])

  // Handler to open new task modal
  const handleCreateTask = useCallback(() => {
    createAndOpenDraft('task')
  }, [createAndOpenDraft])

  return (
    <div className="h-full flex flex-col overflow-hidden">
      <ViewHeader
        icon={ListBulletIcon}
        iconColor="text-indigo-600 dark:text-indigo-400"
        title="Tasks"
        count={tasks?.length ?? 0}
        actions={
          <div className="flex items-center gap-3">
            <button
              onClick={handleRefresh}
              disabled={refreshing}
              className="p-1.5 text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-md transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              title="Refresh"
              aria-label="Refresh tasks"
            >
              <ArrowPathIcon className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
            </button>
            <div className="flex items-center gap-2">
              <FunnelIcon className="w-4 h-4 text-gray-500" />
              <select
                value={selectedProjectId ?? ''}
                onChange={handleProjectFilterChange}
                className="px-3 py-1.5 border border-gray-300 dark:border-gray-600 rounded-md text-sm bg-white dark:bg-white/[0.06] text-gray-900 dark:text-white min-w-[180px]"
              >
                <option value="">All Projects</option>
                {projects?.map(project => (
                  <option key={project.id} value={project.id}>
                    {project.name}
                  </option>
                ))}
              </select>
            </div>
            <Button onClick={handleCreateTask} icon={<PlusIcon />}>
              New Task
            </Button>
          </div>
        }
      />

      <div className="flex-1 flex flex-col overflow-hidden py-6 min-h-0">
      {tasksLoading && !tasks ? (
        <div className="flex justify-center items-center h-64">
          <div className={loadingSpinner}></div>
        </div>
      ) : (
      <>
      {tasksError && <ErrorMessage error={tasksError} retry={refetchTasks} className="mb-4" />}

      {/* Kanban Board */}
      <div className="flex-1 min-h-0 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {STATUS_COLUMNS.map((status) => (
          <Card key={status} padding="xs" className="bg-gray-50 dark:bg-gray-800 flex flex-col overflow-hidden">
            <h3 className={`font-medium ${textColors.primary} mb-4 flex items-center justify-between flex-shrink-0`}>
              {STATUS_LABELS[status] ?? status}
              <span className="bg-gray-200 dark:bg-white/[0.06] text-gray-600 dark:text-gray-400 text-xs px-2 py-1 rounded-full">
                {taskGroups[status]?.length || 0}
              </span>
            </h3>

            <div className="space-y-3 overflow-y-auto flex-1 min-h-0">
              {taskGroups[status]?.map((task) => {
                const pr = status === TaskStatus.PR_OPEN ? prByTaskId.get(task.id) : undefined
                return (
                  <div
                    key={task.id}
                    onClick={() => navigate(`/tasks/${task.id}`)}
                    className="block bg-white dark:bg-white/[0.06] rounded-lg p-3 shadow-sm hover:shadow-md transition-shadow border border-gray-200 dark:border-gray-600 cursor-pointer"
                  >
                    <h4 className="font-medium text-gray-900 dark:text-white text-sm mb-2">
                      {task.title}
                    </h4>
                    <div className="flex items-center justify-between gap-2">
                      <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${getStatusColor(task.status)}`}>
                        {task.status}
                      </span>
                      <div className="flex items-center gap-1.5 min-w-0">
                        <span className={`text-xs shrink-0 ${textColors.muted}`}>#{task.id}</span>
                        <span className="text-xs text-gray-500 dark:text-gray-400 truncate">
                          {task.project_name}
                        </span>
                      </div>
                    </div>
                    {pr && (
                      <div className="flex items-center gap-2 mt-2 flex-wrap">
                        <StatusIndicator
                          mergeableState={pr.mergeable_state}
                          ciStatus={pr.ci_status}
                          reviewDecision={pr.review_decision}
                        />
                        <a
                          href={pr.pr_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          onClick={e => e.stopPropagation()}
                          className="flex items-center gap-1 text-xs text-blue-600 dark:text-blue-400 hover:underline"
                          title="Open PR in GitHub"
                        >
                          #{pr.pr_number}
                          <ArrowTopRightOnSquareIcon className="w-2.5 h-2.5 flex-shrink-0 opacity-60 hover:opacity-100" />
                        </a>
                        <ReviewBadge decision={pr.review_decision} />
                        {pr.comment_count > 0 && (
                          <span className="flex items-center gap-0.5 text-xs text-gray-400 dark:text-gray-500" title={`${pr.comment_count} comment${pr.comment_count !== 1 ? 's' : ''}`}>
                            <ChatBubbleLeftIcon className="w-3 h-3" />
                            {pr.comment_count}
                          </span>
                        )}
                      </div>
                    )}
                  </div>
                )
              })}
              {!taskGroups[status]?.length && (
                <p className="text-sm text-gray-400 dark:text-gray-500 italic text-center py-4">
                  No tasks
                </p>
              )}
            </div>
          </Card>
        ))}
      </div>

      </>
      )}
      </div>

    </div>
  )
}
