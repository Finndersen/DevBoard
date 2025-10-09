import type { ReactNode } from 'react'

interface CardProps {
  children: ReactNode
  className?: string
  padding?: 'none' | 'xs' | 'sm' | 'md' | 'lg'
  hover?: boolean
  onClick?: () => void
}

const paddingClasses = {
  none: '',
  xs: 'p-3',
  sm: 'p-4',
  md: 'p-6',
  lg: 'p-8'
}

export default function Card({ children, className = '', padding = 'md', hover = false, onClick }: CardProps) {
  const baseClasses = 'bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700'
  const hoverClasses = hover ? 'hover:shadow-md transition-shadow' : ''
  const cursorClasses = onClick ? 'cursor-pointer' : ''

  const classes = `${baseClasses} ${paddingClasses[padding]} ${hoverClasses} ${cursorClasses} ${className}`

  return (
    <div className={classes} onClick={onClick}>
      {children}
    </div>
  )
}