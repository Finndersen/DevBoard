import type { ReactNode } from 'react'
import { statusColors } from '../../styles/designSystem'

interface StatusBadgeProps {
  children: ReactNode
  variant?: 'default' | 'success' | 'warning' | 'error' | 'info'
  size?: 'sm' | 'md'
}

const defaultVariantClasses = 'bg-gray-100 text-gray-800 dark:bg-white/[0.05] dark:text-gray-300'

const sizeClasses = {
  sm: 'px-2 py-0.5 text-xs',
  md: 'px-2.5 py-0.5 text-xs'
}

export default function StatusBadge({ children, variant = 'default', size = 'md' }: StatusBadgeProps) {
  const variantClasses = variant === 'default'
    ? defaultVariantClasses
    : `${statusColors[variant].bg} ${statusColors[variant].text}`

  const classes = `inline-flex items-center rounded-full font-medium ${variantClasses} ${sizeClasses[size]}`

  return (
    <span className={classes}>
      {children}
    </span>
  )
}
