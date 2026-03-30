import { surfaces, borderColors } from '../../styles/designSystem'

interface DocumentContentViewerProps {
  content: string | null
  className?: string
}

export default function DocumentContentViewer({ content, className = '' }: DocumentContentViewerProps) {
  if (!content) {
    return (
      <div className="text-center py-8 text-gray-500 dark:text-gray-400">
        No content available
      </div>
    )
  }

  const lines = content.split('\n').length
  const chars = content.length

  return (
    <div className={`${surfaces.sunken} border ${borderColors.default} rounded-lg overflow-hidden ${className}`}>
      <div className={`${surfaces.sunken} px-4 py-2 border-b ${borderColors.default} flex items-center justify-between`}>
        <div className="flex items-center space-x-3">
          <span className="text-xs font-medium text-gray-600 dark:text-gray-400">
            Document Content
          </span>
          <span className="text-xs text-gray-500 dark:text-gray-500">
            {lines} lines, {chars} characters
          </span>
        </div>
      </div>
      <div className="p-4 max-h-96 overflow-y-auto">
        <pre className="font-mono text-xs text-gray-700 dark:text-gray-300 whitespace-pre-wrap">
          {content}
        </pre>
      </div>
    </div>
  )
}
