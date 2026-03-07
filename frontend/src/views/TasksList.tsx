import { useState, useMemo, useCallback, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { PlusIcon, ListBulletIcon, FunnelIcon } from '@heroicons/react/24/outline'
import { useAllTasks, useProjects } from '../hooks'
import { useModal } from '../hooks/useModal'
import CreateTaskModal from '../components/modals/CreateTaskModal'
import { Button, Card, ErrorMessage } from '../components/ui'
import { textColors, loadingSpinner } from '../styles/designSystem'
import type { TaskListItem } from '../lib/api'
import ViewHeader from '../components/layout/ViewHeader'

const STATUS_COLUMNS = ['planning', 'implementing', 'pr_open', 'complete']

const STATUS_LABELS: Record<string, string> = {
  planning: 'Planning',
  implementing: 'Implementing',
  pr_open: 'PR Open',
  complete: 'Complete',
}

function getStatusColor(status: string) {
  switch (status.toLowerCase()) {
    case 'planning':
      return 'bg-blue-100 text-blue-800 dark:bg-blue-900/20 dark:text-blue-400'
    case 'implementing':
      return 'bg-purple-100 text-purple-800 dark:bg-purple-900/20 dark:text-purple-400'
    case 'pr_open':
      return 'bg-orange-100 text-orange-800 dark:bg-orange-900/20 dark:text-orange-400'
    case 'complete':
      return 'bg-green-100 text-green-800 dark:bg-green-900/20 dark:text-green-400'
    default:
      return 'bg-gray-100 text-gray-800 dark:bg-gray-900/20 dark:text-gray-400'
  }
}

export default function TasksList() {
  const [selectedProjectId, setSelectedProjectId] = useState<number | undefined>(undefined)
  const { data: tasks, loading: tasksLoading, error: tasksError, refetch: refetchTasks } = useAllTasks(selectedProjectId)
  const { data: projects } = useProjects()
  const createTaskModal = useModal()

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

  // Refetch tasks when modal closes (task may have been created)
  const handleTaskModalClose = useCallback(() => {
    createTaskModal.close()
    refetchTasks()
  }, [createTaskModal, refetchTasks])

  return (
    <div className="h-full flex flex-col overflow-hidden">
      <ViewHeader
        icon={ListBulletIcon}
        iconColor="text-indigo-600 dark:text-indigo-400"
        title="Tasks"
        count={tasks?.length ?? 0}
        actions={
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2">
              <FunnelIcon className="w-4 h-4 text-gray-500" />
              <select
                value={selectedProjectId ?? ''}
                onChange={handleProjectFilterChange}
                className="px-3 py-1.5 border border-gray-300 dark:border-gray-600 rounded-md text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-white min-w-[180px]"
              >
                <option value="">All Projects</option>
                {projects?.map(project => (
                  <option key={project.id} value={project.id}>
                    {project.name}
                  </option>
                ))}
              </select>
            </div>
            <Button onClick={createTaskModal.open} icon={<PlusIcon />}>
              New Task
            </Button>
          </div>
        }
      />

      <div className="flex-1 overflow-auto py-6 space-y-6">
      {tasksLoading ? (
        <div className="flex justify-center items-center h-64">
          <div className={loadingSpinner}></div>
        </div>
      ) : (
      <>
      {tasksError && <ErrorMessage error={tasksError} retry={refetchTasks} className="mb-4" />}

      {/* Kanban Board */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {STATUS_COLUMNS.map((status) => (
          <Card key={status} padding="xs" className="bg-gray-50 dark:bg-gray-800">
            <h3 className={`font-medium ${textColors.primary} mb-4 flex items-center justify-between`}>
              {STATUS_LABELS[status] ?? status}
              <span className="bg-gray-200 dark:bg-gray-700 text-gray-600 dark:text-gray-400 text-xs px-2 py-1 rounded-full">
                {taskGroups[status]?.length || 0}
              </span>
            </h3>

            <div className="space-y-3">
              {taskGroups[status]?.map((task) => (
                <Link
                  key={task.id}
                  to={`/tasks/${task.id}`}
                  className="block bg-white dark:bg-gray-700 rounded-lg p-3 shadow-sm hover:shadow-md transition-shadow border border-gray-200 dark:border-gray-600"
                >
                  <h4 className="font-medium text-gray-900 dark:text-white text-sm mb-2">
                    {task.title}
                  </h4>
                  <div className="flex items-center justify-between gap-2">
                    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${getStatusColor(task.status)}`}>
                      {task.status}
                    </span>
                    <span className="text-xs text-gray-500 dark:text-gray-400 truncate">
                      {task.project_name}
                    </span>
                  </div>
                </Link>
              ))}
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

      {/* Create Task Modal - no projectId means user must select one */}
      <CreateTaskModal
        isOpen={createTaskModal.isOpen}
        onClose={handleTaskModalClose}
      />
    </div>
  )
}
