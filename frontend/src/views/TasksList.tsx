import { useState, useMemo, useCallback, useEffect, useRef } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { PlusIcon, ListBulletIcon, FunnelIcon, ChatBubbleLeftIcon, ArrowPathIcon, ArrowTopRightOnSquareIcon, CheckCircleIcon } from '@heroicons/react/24/outline'
import { useAllTasks, useProjects, useRefetchOnViewActivation, useTaskCounts, useArchivedTasks } from '../hooks'
import { Button, Card, ErrorMessage } from '../components/ui'
import { textColors, loadingSpinner, borderColors, statusColors, surfaces, hoverColors, projectColors, initiativeColors } from '../styles/designSystem'
import { TaskStatus } from '../lib/api'
import type { TaskListItem, Project } from '../lib/api'
import { useGithubStore } from '../stores/githubStore'
import ViewHeader from '../components/layout/ViewHeader'
import { StatusIndicator, ReviewBadge } from '../components/github/PRStatusComponents'
import { useUIStore } from '../stores/uiStore'

const ACTIVE_STATUS_COLUMNS: TaskStatus[] = [TaskStatus.PLANNING, TaskStatus.IMPLEMENTING, TaskStatus.PR_OPEN, TaskStatus.MERGED]

const STATUS_LABELS: Partial<Record<TaskStatus, string>> = {
  [TaskStatus.PLANNING]: 'Planning',
  [TaskStatus.IMPLEMENTING]: 'Implementing',
  [TaskStatus.PR_OPEN]: 'PR Open',
  [TaskStatus.MERGED]: 'Merged',
}

function getStatusColor(status: TaskStatus) {
  switch (status) {
    case TaskStatus.PLANNING:
      return 'bg-blue-100 text-blue-800 dark:bg-blue-900/20 dark:text-blue-400'
    case TaskStatus.IMPLEMENTING:
      return 'bg-purple-100 text-purple-800 dark:bg-purple-900/20 dark:text-purple-400'
    case TaskStatus.PR_OPEN:
      return 'bg-orange-100 text-orange-800 dark:bg-orange-900/20 dark:text-orange-400'
    case TaskStatus.MERGED:
    case TaskStatus.COMPLETE:
      return 'bg-green-100 text-green-800 dark:bg-green-900/20 dark:text-green-400'
    default:
      return 'bg-gray-100 text-gray-800 dark:bg-gray-900/20 dark:text-gray-400'
  }
}

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
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
  const [activeTab, setActiveTab] = useState<'active' | 'archived'>('active')
  const [archivedPage, setArchivedPage] = useState(1)
  const archivedLoadedRef = useRef(false)

  const { data: tasks, loading: tasksLoading, error: tasksError, refetch: refetchTasks } = useAllTasks(selectedProjectId)
  const { data: projects } = useProjects()
  const fetchAll = useGithubStore(s => s.fetchAll)
  const openPRItems = useGithubStore(s => s.openPRItems)
  const { data: taskCounts, refetch: refetchCounts } = useTaskCounts(selectedProjectId)
  const { data: archivedData, loading: archivedLoading, refetch: refetchArchived } = useArchivedTasks(selectedProjectId, archivedPage)
  const { createAndOpenDraft } = useUIStore()
  const [refreshing, setRefreshing] = useState(false)

  const handleRefresh = useCallback(async () => {
    setRefreshing(true)
    try {
      await Promise.all([refetchTasks(), fetchAll(true), refetchCounts()])
      if (archivedLoadedRef.current) {
        await refetchArchived()
      }
    } finally {
      setRefreshing(false)
    }
  }, [refetchTasks, fetchAll, refetchCounts, refetchArchived])

  useRefetchOnViewActivation([refetchTasks, refetchCounts])

  const prByTaskId = useMemo(() => {
    const map = new Map<number, { mergeable_state: string | null; ci_status: string | null; review_decision: string | null; pr_url: string; pr_number: number; comment_count: number }>()
    for (const item of openPRItems) {
      if (item.associated_task) {
        map.set(item.associated_task.task_id, item.pr_status)
      }
    }
    return map
  }, [openPRItems])

  // Refetch active tasks and counts when project filter changes
  useEffect(() => {
    refetchTasks()
  }, [selectedProjectId, refetchTasks])

  useEffect(() => {
    refetchCounts()
  }, [selectedProjectId, refetchCounts])

  // Refetch archived when page or project changes (only once tab has been opened)
  useEffect(() => {
    if (!archivedLoadedRef.current) return
    refetchArchived()
  }, [archivedPage, selectedProjectId, refetchArchived])

  // Group projects into top-level and initiatives for the filter dropdown
  const { topLevelProjects, initiativesByParentId } = useMemo(() => {
    if (!projects) return { topLevelProjects: [] as Project[], initiativesByParentId: new Map<number, Project[]>() }
    const topLevel = projects.filter(p => !p.parent_project_id)
    const byParent = new Map<number, Project[]>()
    for (const p of projects) {
      if (p.parent_project_id) {
        const arr = byParent.get(p.parent_project_id) ?? []
        arr.push(p)
        byParent.set(p.parent_project_id, arr)
      }
    }
    return { topLevelProjects: topLevel, initiativesByParentId: byParent }
  }, [projects])

  // Group active tasks by status
  const taskGroups = useMemo(() => {
    if (!tasks) return {} as Record<string, TaskListItem[]>
    const groups = tasks.reduce((acc, task) => {
      const status = task.status
      if (!acc[status]) acc[status] = []
      acc[status].push(task)
      return acc
    }, {} as Record<string, TaskListItem[]>)

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
    setArchivedPage(1)
  }, [])

  const handleCreateTask = useCallback(() => {
    createAndOpenDraft('task')
  }, [createAndOpenDraft])

  const handleTabChange = useCallback((tab: 'active' | 'archived') => {
    setActiveTab(tab)
    if (tab === 'archived' && !archivedLoadedRef.current) {
      archivedLoadedRef.current = true
      refetchArchived()
    }
  }, [refetchArchived])

  const activeTaskCount = tasks?.length ?? 0
  const archivedCount = taskCounts?.[TaskStatus.COMPLETE] ?? 0
  const totalArchivedPages = archivedData ? Math.ceil(archivedData.total / archivedData.page_size) : 0

  return (
    <div className="h-full flex flex-col overflow-hidden">
      <ViewHeader
        icon={ListBulletIcon}
        iconColor="text-indigo-600 dark:text-indigo-400"
        title="Tasks"
        count={activeTaskCount}
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
                {topLevelProjects.flatMap(project => [
                  <option key={`project-${project.id}`} value={project.id}>◆ {project.name}</option>,
                  ...(initiativesByParentId.get(project.id)?.map(initiative => (
                    <option key={`initiative-${initiative.id}`} value={initiative.id}>  ▸ {initiative.name}</option>
                  )) ?? []),
                ])}
              </select>
            </div>
            <Button onClick={handleCreateTask} icon={<PlusIcon />}>
              New Task
            </Button>
          </div>
        }
      />

      {/* Tab bar */}
      <div className={`border-b ${borderColors.default} px-6 flex-shrink-0`}>
        <nav className="flex">
          {(['active', 'archived'] as const).map(tab => (
            <button
              key={tab}
              onClick={() => handleTabChange(tab)}
              className={`px-4 py-2 text-sm border-b-2 transition-colors ${
                activeTab === tab
                  ? `${borderColors.focus} ${textColors.accent}`
                  : `border-transparent ${textColors.secondary}`
              }`}
            >
              <span>{tab === 'active' ? 'Active' : 'Archived'}</span>
              <span className="ml-1.5 bg-gray-100 dark:bg-white/[0.1] text-gray-600 dark:text-gray-400 text-xs px-1.5 py-0.5 rounded-full">
                {tab === 'active' ? activeTaskCount : archivedCount}
              </span>
            </button>
          ))}
        </nav>
      </div>

      {/* Active tab — kanban */}
      {activeTab === 'active' && (
        <div className="flex-1 flex flex-col overflow-hidden py-6 min-h-0">
          {tasksLoading && !tasks ? (
            <div className="flex justify-center items-center h-64">
              <div className={loadingSpinner}></div>
            </div>
          ) : (
            <>
              {tasksError && <ErrorMessage error={tasksError} retry={refetchTasks} className="mb-4" />}

              <div className="flex-1 min-h-0 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                {ACTIVE_STATUS_COLUMNS.map((status) => (
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
                                {task.initiative_id ? (
                                  <span className={`text-xs px-1.5 py-0.5 rounded-full font-medium shrink-0 max-w-[100px] truncate ${initiativeColors.badge}`} title={task.initiative_name ?? undefined}>
                                    ▸ {task.initiative_name}
                                  </span>
                                ) : (
                                  <span className={`text-xs px-1.5 py-0.5 rounded-full font-medium shrink-0 max-w-[100px] truncate ${projectColors.badge}`} title={task.project_name}>
                                    ◆ {task.project_name}
                                  </span>
                                )}
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
      )}

      {/* Archived tab — paginated table */}
      {activeTab === 'archived' && (
        <div className="flex-1 flex flex-col overflow-hidden min-h-0">
          {archivedLoading && !archivedData ? (
            <div className="flex justify-center items-center h-64">
              <div className={loadingSpinner}></div>
            </div>
          ) : (
            <>
              <div className="flex-1 overflow-auto min-h-0">
                <table className="w-full text-sm">
                  <thead className={`sticky top-0 ${surfaces.raised}`}>
                    <tr className={`border-b ${borderColors.default}`}>
                      <th className="w-8 py-2 pl-4" />
                      <th className={`py-2 px-3 text-left text-xs font-medium ${textColors.muted}`}>#ID</th>
                      <th className={`py-2 px-3 text-left text-xs font-medium ${textColors.muted}`}>Title</th>
                      <th className={`py-2 px-3 text-left text-xs font-medium ${textColors.muted}`}>Project</th>
                      <th className={`py-2 px-3 text-left text-xs font-medium ${textColors.muted}`}>Completed</th>
                    </tr>
                  </thead>
                  <tbody>
                    {archivedData?.items.map(task => (
                      <tr
                        key={task.id}
                        onClick={() => navigate(`/tasks/${task.id}`)}
                        className={`border-b ${borderColors.default} ${hoverColors.subtle} cursor-pointer`}
                      >
                        <td className="w-8 py-3 pl-4">
                          <CheckCircleIcon className={`w-4 h-4 ${statusColors.success.text}`} />
                        </td>
                        <td className={`py-3 px-3 ${textColors.muted}`}>#{task.id}</td>
                        <td className={`py-3 px-3 ${textColors.primary}`}>{task.title}</td>
                        <td className={`py-3 px-3 ${textColors.secondary}`}>
                          {task.initiative_id ? (
                            <span>
                              {task.project_name}
                              <span className={`ml-1 text-xs px-1.5 py-0.5 rounded-full font-medium ${initiativeColors.badge}`}>
                                ▸ {task.initiative_name}
                              </span>
                            </span>
                          ) : task.project_name}
                        </td>
                        <td className={`py-3 px-3 ${textColors.muted}`}>{formatDate(task.updated_at)}</td>
                      </tr>
                    ))}
                    {(!archivedData || archivedData.items.length === 0) && !archivedLoading && (
                      <tr>
                        <td colSpan={5} className="py-12 text-center text-gray-400 dark:text-gray-500 italic text-sm">
                          No archived tasks
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>

              {archivedData && archivedData.total > archivedData.page_size && (
                <div className={`flex-shrink-0 flex items-center justify-between px-4 py-3 border-t ${borderColors.default}`}>
                  <span className={`text-sm ${textColors.muted}`}>
                    Page {archivedPage} of {totalArchivedPages} · {archivedData.total} tasks
                  </span>
                  <div className="flex items-center gap-1">
                    <button
                      disabled={archivedPage === 1}
                      onClick={() => setArchivedPage(p => p - 1)}
                      className={`px-3 py-1 text-sm border ${borderColors.input} rounded disabled:opacity-40 ${hoverColors.subtle} ${textColors.secondary} transition-colors`}
                    >
                      ← Prev
                    </button>
                    {Array.from({ length: Math.min(totalArchivedPages, 5) }, (_, i) => {
                      const page = i + 1
                      return (
                        <button
                          key={page}
                          onClick={() => setArchivedPage(page)}
                          className={`px-3 py-1 text-sm border rounded transition-colors ${
                            archivedPage === page
                              ? `${borderColors.focus} ${statusColors.info.bg} ${statusColors.info.text}`
                              : `${borderColors.input} ${hoverColors.subtle} ${textColors.secondary}`
                          }`}
                        >
                          {page}
                        </button>
                      )
                    })}
                    <button
                      disabled={archivedPage === totalArchivedPages}
                      onClick={() => setArchivedPage(p => p + 1)}
                      className={`px-3 py-1 text-sm border ${borderColors.input} rounded disabled:opacity-40 ${hoverColors.subtle} ${textColors.secondary} transition-colors`}
                    >
                      Next →
                    </button>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  )
}
