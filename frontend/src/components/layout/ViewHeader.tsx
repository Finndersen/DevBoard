import type { ComponentType, ReactNode } from 'react'

interface ViewHeaderProps {
  icon: ComponentType<{ className?: string }>
  iconColor?: string
  title: string
  count?: number
  actions?: ReactNode
}

export default function ViewHeader({
  icon: Icon,
  iconColor = 'text-blue-600 dark:text-blue-400',
  title,
  count,
  actions,
}: ViewHeaderProps) {
  return (
    <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-gray-700 flex-shrink-0">
      <div className="flex items-center gap-3">
        <Icon className={`w-6 h-6 ${iconColor}`} />
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">{title}</h1>
        {count !== undefined && (
          <span className="text-sm text-gray-500 dark:text-gray-400">({count})</span>
        )}
      </div>
      {actions && <div>{actions}</div>}
    </div>
  )
}
