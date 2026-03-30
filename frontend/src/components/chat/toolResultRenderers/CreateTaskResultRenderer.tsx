/**
 * Rich renderer for create_task tool results.
 * Displays task details with a clickable link to navigate to the created task.
 */

import { useNavigate } from 'react-router-dom'

import type { RichResultRendererProps } from './index'
import { surfaces, statusColors } from '../../../styles/designSystem'

/**
 * Expected data shape from the create_task tool.
 */
interface CreateTaskResultData {
  task_id: number
  title: string
  status: string
  branch_name: string
  base_branch: string
  codebase_name: string
}

/**
 * Type guard to validate the data shape.
 */
function isCreateTaskResultData(data: unknown): data is CreateTaskResultData {
  if (typeof data !== 'object' || data === null) {
    return false
  }

  const obj = data as Record<string, unknown>
  return (
    typeof obj.task_id === 'number' &&
    typeof obj.title === 'string' &&
    typeof obj.status === 'string' &&
    typeof obj.branch_name === 'string' &&
    typeof obj.base_branch === 'string' &&
    typeof obj.codebase_name === 'string'
  )
}

export default function CreateTaskResultRenderer({ data }: RichResultRendererProps) {
  const navigate = useNavigate()

  if (!isCreateTaskResultData(data)) {
    return (
      <div className="text-xs text-red-600 dark:text-red-400">
        Invalid task data format
      </div>
    )
  }

  const handleNavigate = (e: React.MouseEvent) => {
    e.stopPropagation()
    navigate(`/tasks/${data.task_id}`)
  }

  return (
    <div className="text-xs space-y-2">
      <div className="flex items-center gap-2">
        <svg
          className="w-4 h-4 text-green-600 dark:text-green-400 flex-shrink-0"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
        </svg>
        <span className="text-green-700 dark:text-green-300 font-medium">
          Task created successfully
        </span>
      </div>

      <div className="pl-6 space-y-1 text-gray-700 dark:text-gray-300">
        <div>
          <span className="text-gray-500 dark:text-gray-400">Title: </span>
          {data.title}
        </div>
        <div>
          <span className="text-gray-500 dark:text-gray-400">Status: </span>
          {data.status}
        </div>
        <div>
          <span className="text-gray-500 dark:text-gray-400">Branch: </span>
          <code className={`${surfaces.sunken} px-1 rounded`}>{data.branch_name}</code>
        </div>
        <div>
          <span className="text-gray-500 dark:text-gray-400">Codebase: </span>
          {data.codebase_name}
        </div>
      </div>

      <div className="pl-6 pt-1">
        <span
          role="link"
          tabIndex={0}
          onClick={handleNavigate}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              e.preventDefault()
              handleNavigate(e as unknown as React.MouseEvent)
            }
          }}
          className={`inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium text-blue-700 dark:text-blue-300 ${statusColors.info.bg} border ${statusColors.info.border} rounded hover:bg-blue-100 dark:hover:bg-blue-900/50 transition-colors cursor-pointer`}
        >
          <svg
            className="w-3.5 h-3.5"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" />
          </svg>
          Open Task #{data.task_id}
        </span>
      </div>
    </div>
  )
}
