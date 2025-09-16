import type { ReactNode } from 'react'

interface StatusBadgeProps {
  children: ReactNode
  variant?: 'default' | 'success' | 'warning' | 'error' | 'info'
  size?: 'sm' | 'md'
}

const variantClasses = {
  default: 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300',
  success: 'bg-green-100 text-green-800 dark:bg-green-900/20 dark:text-green-400',
  warning: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/20 dark:text-yellow-400',
  error: 'bg-red-100 text-red-800 dark:bg-red-900/20 dark:text-red-400',
  info: 'bg-blue-100 text-blue-800 dark:bg-blue-900/20 dark:text-blue-400'
}

const sizeClasses = {
  sm: 'px-2 py-0.5 text-xs',
  md: 'px-2.5 py-0.5 text-xs'
}

export default function StatusBadge({ children, variant = 'default', size = 'md' }: StatusBadgeProps) {
  const classes = `inline-flex items-center rounded-full font-medium ${variantClasses[variant]} ${sizeClasses[size]}`

  return (
    <span className={classes}>
      {children}
    </span>
  )
}