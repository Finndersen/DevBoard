import type { RichResultRendererProps } from './index'

interface EditTaskResultData {
  task_id: number
  title: string
  custom_fields: Record<string, unknown> | null
  specification_updated?: boolean
}

function isEditTaskResultData(data: unknown): data is EditTaskResultData {
  if (typeof data !== 'object' || data === null) return false
  const obj = data as Record<string, unknown>
  return typeof obj.task_id === 'number' && typeof obj.title === 'string'
}

export default function EditTaskResultRenderer({ data, toolCall }: RichResultRendererProps) {
  if (!isEditTaskResultData(data)) {
    return <div className="text-xs text-red-600 dark:text-red-400">Invalid edit_task result format</div>
  }

  const args = toolCall.tool_args ?? {}
  const updatedFields: { label: string; value: string }[] = []

  if (args.title != null) {
    updatedFields.push({ label: 'Title', value: data.title })
  }
  if (args.specification_content != null) {
    updatedFields.push({ label: 'Specification', value: data.specification_updated ? 'Updated' : 'Unchanged' })
  }
  if (args.custom_fields != null) {
    updatedFields.push({ label: 'Custom fields', value: 'Updated' })
  }

  return (
    <div className="space-y-1">
      {updatedFields.map(({ label, value }) => (
        <div key={label} className="flex gap-2 text-xs">
          <span className="text-gray-500 dark:text-gray-400 font-medium flex-shrink-0">{label}:</span>
          <span className="text-gray-900 dark:text-gray-200 truncate">{value}</span>
        </div>
      ))}
    </div>
  )
}
