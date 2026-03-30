import type { ReactNode } from 'react'
import Alert from './Alert'
import { statusColors } from '../../styles/designSystem'

interface ErrorMessageProps {
  error: string | null
  retry?: () => void
  className?: string
  children?: ReactNode
}

const errorIcon = (
  <svg className="h-5 w-5 text-red-400" viewBox="0 0 20 20" fill="currentColor">
    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
  </svg>
)

export default function ErrorMessage({ error, retry, className = '', children }: ErrorMessageProps) {
  if (!error) return null

  return (
    <Alert variant="error" title="Error" icon={errorIcon} className={className}>
      <div>{error}</div>
      {(retry || children) && (
        <div className="mt-2">
          {retry && (
            <button
              type="button"
              onClick={retry}
              className={`${statusColors.error.bg} ${statusColors.error.text} text-sm font-medium px-2 py-1 rounded-md hover:bg-red-100 dark:hover:bg-red-900/40 transition-colors`}
            >
              Try again
            </button>
          )}
          {children}
        </div>
      )}
    </Alert>
  )
}
