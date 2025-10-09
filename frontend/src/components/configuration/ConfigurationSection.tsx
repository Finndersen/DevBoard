import type { ReactNode } from 'react'

interface ConfigurationSectionProps {
  title: string
  children: ReactNode
  isFirst?: boolean
}

export function ConfigurationSection({ title, children, isFirst = false }: ConfigurationSectionProps) {
  return (
    <>
      <div className={`px-6 py-3 bg-gray-50 dark:bg-gray-800 ${
        isFirst 
          ? 'border-b border-gray-200 dark:border-gray-700' 
          : 'border-y border-gray-200 dark:border-gray-700'
      }`}>
        <h4 className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">
          {title}
        </h4>
      </div>
      <div className="divide-y divide-gray-200 dark:divide-gray-700">
        {children}
      </div>
    </>
  )
}