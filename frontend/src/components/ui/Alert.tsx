import type { ReactNode } from 'react'
import { statusColors } from '../../styles/designSystem'

interface AlertProps {
  variant: 'error' | 'warning' | 'info' | 'success'
  title?: string
  icon?: ReactNode
  padding?: string
  className?: string
  children?: ReactNode
}

export default function Alert({ variant, title, icon, padding = 'p-4', className = '', children }: AlertProps) {
  const colors = statusColors[variant]
  const classes = `border rounded-md ${padding} ${colors.bg} ${colors.border} ${colors.text} ${className}`

  return (
    <div className={classes}>
      <div className="flex">
        {icon && (
          <div className="flex-shrink-0 mr-3">
            {icon}
          </div>
        )}
        <div className="flex-1">
          {title && (
            <p className="text-sm font-medium">{title}</p>
          )}
          {children && (
            <div className={`text-sm ${title ? 'mt-1' : ''}`}>
              {children}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
