import type { ReactNode } from 'react'
import Surface from './Surface'

interface CardProps {
  children: ReactNode
  className?: string
  padding?: 'none' | 'xs' | 'sm' | 'md' | 'lg'
  hover?: boolean
  onClick?: () => void
}

export default function Card({ children, className = '', padding = 'md', hover = false, onClick }: CardProps) {
  const hoverClasses = hover ? 'hover:shadow-md transition-shadow' : ''
  const cursorClasses = onClick ? 'cursor-pointer' : ''
  const extraClasses = [hoverClasses, cursorClasses, className].filter(Boolean).join(' ')

  return (
    <Surface variant="raised" padding={padding} className={extraClasses} onClick={onClick}>
      {children}
    </Surface>
  )
}
