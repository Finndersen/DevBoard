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
    <div className={`bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-white/[0.08] rounded-lg overflow-hidden ${className}`}>
      <div className="bg-gray-100 dark:bg-white/[0.05] px-4 py-2 border-b border-gray-200 dark:border-gray-600 flex items-center justify-between">
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
