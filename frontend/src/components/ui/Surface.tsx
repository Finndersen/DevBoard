import type { ElementType, ReactNode } from 'react'
import { surfaces, borderColors } from '../../styles/designSystem'

interface SurfaceProps {
  variant: 'raised' | 'sunken'
  padding?: 'none' | 'xs' | 'sm' | 'md' | 'lg'
  rounded?: boolean
  border?: boolean
  className?: string
  children?: ReactNode
  as?: ElementType
  onClick?: () => void
}

const paddingClasses = {
  none: '',
  xs: 'p-3',
  sm: 'p-4',
  md: 'p-6',
  lg: 'p-8'
}

export default function Surface({
  variant,
  padding = 'none',
  rounded = true,
  border = true,
  className = '',
  children,
  as: Tag = 'div',
  onClick
}: SurfaceProps) {
  const variantClasses = variant === 'raised'
    ? `${surfaces.raised} shadow-sm`
    : surfaces.sunken

  const classes = [
    variantClasses,
    paddingClasses[padding],
    rounded ? 'rounded-lg' : '',
    border ? `border ${borderColors.default}` : '',
    className
  ].filter(Boolean).join(' ')

  return (
    <Tag className={classes} onClick={onClick}>
      {children}
    </Tag>
  )
}
