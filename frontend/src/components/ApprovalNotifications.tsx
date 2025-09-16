import { useApprovals } from '../contexts/ApprovalsContext'
import { ExclamationTriangleIcon } from '@heroicons/react/24/outline'
import { Link } from 'react-router-dom'

export default function ApprovalNotifications() {
  const { state } = useApprovals()
  
  // Get all approval keys that have pending approvals
  const pendingKeys = Object.keys(state.approvals).filter(
    key => state.approvals[key] && state.approvals[key].length > 0
  )

  if (pendingKeys.length === 0) {
    return null
  }

  const getTotalApprovals = () => {
    return pendingKeys.reduce((total, key) => {
      return total + (state.approvals[key]?.length || 0)
    }, 0)
  }

  const getNavigationUrl = (key: string) => {
    if (key.startsWith('project-')) {
      const projectId = key.replace('project-', '')
      return `/projects/${projectId}`
    } else if (key.startsWith('task-')) {
      const taskId = key.replace('task-', '')
      return `/tasks/${taskId}`
    }
    return '/'
  }

  const getDisplayName = (key: string) => {
    if (key.startsWith('project-')) {
      const projectId = key.replace('project-', '')
      return `Project ${projectId}`
    } else if (key.startsWith('task-')) {
      const taskId = key.replace('task-', '')
      return `Task ${taskId}`
    }
    return key
  }

  const totalApprovals = getTotalApprovals()

  return (
    <div className="bg-orange-50 dark:bg-orange-900/20 border-l-4 border-orange-400 p-4 mb-4">
      <div className="flex">
        <div className="flex-shrink-0">
          <ExclamationTriangleIcon className="h-5 w-5 text-orange-400" aria-hidden="true" />
        </div>
        <div className="ml-3">
          <h3 className="text-sm font-medium text-orange-800 dark:text-orange-200">
            {totalApprovals} Pending Approval{totalApprovals !== 1 ? 's' : ''}
          </h3>
          <div className="mt-2 text-sm text-orange-700 dark:text-orange-300">
            <p>You have document edit approvals awaiting your decision:</p>
            <ul className="mt-1 list-disc list-inside">
              {pendingKeys.map(key => {
                const approvals = state.approvals[key] || []
                const count = approvals.length
                return (
                  <li key={key}>
                    <Link
                      to={getNavigationUrl(key)}
                      className="underline hover:text-orange-600 dark:hover:text-orange-200"
                    >
                      {getDisplayName(key)}: {count} approval{count !== 1 ? 's' : ''}
                    </Link>
                  </li>
                )
              })}
            </ul>
          </div>
        </div>
      </div>
    </div>
  )
}