import type { ReactNode } from 'react'

interface CardProps {
  children: ReactNode
  className?: string
  padding?: 'none' | 'sm' | 'md' | 'lg'
  hover?: boolean
}

const paddingClasses = {
  none: '',
  sm: 'p-4',
  md: 'p-6',
  lg: 'p-8'
}

export default function Card({ children, className = '', padding = 'md', hover = false }: CardProps) {
  const baseClasses = 'bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700'
  const hoverClasses = hover ? 'hover:shadow-md transition-shadow' : ''
  
  const classes = `${baseClasses} ${paddingClasses[padding]} ${hoverClasses} ${className}`

  return (
    <div className={classes}>
      {children}
    </div>
  )
}