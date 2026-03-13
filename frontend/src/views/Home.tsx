import { Link } from 'react-router-dom'
import { FolderIcon, CodeBracketIcon, ListBulletIcon } from '@heroicons/react/24/outline'
import { useProjects } from '../hooks'
import { useCodebases } from '../hooks/useCodebases'
import { useAllTasks } from '../hooks/useTasks'
import { TaskStatus } from '../lib/api'
import { Card } from '../components/ui'

export default function Home() {
  const { data: projects } = useProjects()
  const { data: codebases } = useCodebases()
  const { data: tasks } = useAllTasks()

  const activeTasks = tasks?.filter(t => t.status !== TaskStatus.COMPLETE) ?? []

  return (
    <div className="space-y-8 h-full overflow-auto">
      {/* Welcome Header */}
      <div>
        <h1 className="text-3xl font-bold text-gray-900 dark:text-white">
          Welcome to DevBoard
        </h1>
        <p className="mt-2 text-gray-600 dark:text-gray-400">
          Your developer command center for managing projects, tasks, and codebases
        </p>
      </div>

      {/* Quick Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card className="p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-blue-100 dark:bg-blue-900/30 rounded-lg">
              <FolderIcon className="w-5 h-5 text-blue-600 dark:text-blue-400" />
            </div>
            <div>
              <p className="text-2xl font-bold text-gray-900 dark:text-white">
                {projects?.length ?? 0}
              </p>
              <p className="text-sm text-gray-500 dark:text-gray-400">Projects</p>
            </div>
          </div>
        </Card>
        <Card className="p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-indigo-100 dark:bg-indigo-900/30 rounded-lg">
              <ListBulletIcon className="w-5 h-5 text-indigo-600 dark:text-indigo-400" />
            </div>
            <div>
              <p className="text-2xl font-bold text-gray-900 dark:text-white">
                {activeTasks.length}
              </p>
              <p className="text-sm text-gray-500 dark:text-gray-400">Active Tasks</p>
            </div>
          </div>
        </Card>
        <Card className="p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-green-100 dark:bg-green-900/30 rounded-lg">
              <CodeBracketIcon className="w-5 h-5 text-green-600 dark:text-green-400" />
            </div>
            <div>
              <p className="text-2xl font-bold text-gray-900 dark:text-white">
                {codebases?.length ?? 0}
              </p>
              <p className="text-sm text-gray-500 dark:text-gray-400">Codebases</p>
            </div>
          </div>
        </Card>
      </div>

      {/* Navigation Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <Link to="/projects" className="block">
          <Card className="p-6 hover:shadow-lg transition-shadow cursor-pointer h-full" hover>
            <div className="flex items-center gap-3 mb-3">
              <div className="p-2 bg-blue-100 dark:bg-blue-900/30 rounded-lg">
                <FolderIcon className="w-6 h-6 text-blue-600 dark:text-blue-400" />
              </div>
              <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
                Projects
              </h2>
            </div>
            <p className="text-sm text-gray-600 dark:text-gray-400">
              Manage your development projects, specifications, and linked codebases
            </p>
          </Card>
        </Link>

        <Link to="/tasks" className="block">
          <Card className="p-6 hover:shadow-lg transition-shadow cursor-pointer h-full" hover>
            <div className="flex items-center gap-3 mb-3">
              <div className="p-2 bg-indigo-100 dark:bg-indigo-900/30 rounded-lg">
                <ListBulletIcon className="w-6 h-6 text-indigo-600 dark:text-indigo-400" />
              </div>
              <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
                Tasks
              </h2>
            </div>
            <p className="text-sm text-gray-600 dark:text-gray-400">
              View and manage all tasks across projects in a unified kanban board
            </p>
          </Card>
        </Link>

        <Link to="/codebases" className="block">
          <Card className="p-6 hover:shadow-lg transition-shadow cursor-pointer h-full" hover>
            <div className="flex items-center gap-3 mb-3">
              <div className="p-2 bg-green-100 dark:bg-green-900/30 rounded-lg">
                <CodeBracketIcon className="w-6 h-6 text-green-600 dark:text-green-400" />
              </div>
              <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
                Codebases
              </h2>
            </div>
            <p className="text-sm text-gray-600 dark:text-gray-400">
              Manage code repositories, architecture docs, and worktree configurations
            </p>
          </Card>
        </Link>
      </div>
    </div>
  )
}
