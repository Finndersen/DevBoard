import type { ReactNode } from 'react'
import { surfaces, borderColors } from '../../styles/designSystem'

interface ConfigurationSectionProps {
  title: string
  children: ReactNode
  isFirst?: boolean
}

export function ConfigurationSection({ title, children, isFirst = false }: ConfigurationSectionProps) {
  return (
    <>
      <div className={`px-6 py-3 ${surfaces.sunken} ${
        isFirst
          ? `border-b ${borderColors.default}`
          : `border-y ${borderColors.default}`
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