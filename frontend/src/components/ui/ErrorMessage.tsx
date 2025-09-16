import type { ReactNode } from 'react'

interface ErrorMessageProps {
  error: string | null
  retry?: () => void
  className?: string
  children?: ReactNode
}

export default function ErrorMessage({ error, retry, className = '', children }: ErrorMessageProps) {
  if (!error) return null

  return (
    <div className={`bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-md p-4 ${className}`}>
      <div className="flex">
        <div className="flex-shrink-0">
          <svg className="h-5 w-5 text-red-400" viewBox="0 0 20 20" fill="currentColor">
            <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
          </svg>
        </div>
        <div className="ml-3 flex-1">
          <h3 className="text-sm font-medium text-red-800 dark:text-red-400">
            Error
          </h3>
          <div className="mt-1 text-sm text-red-700 dark:text-red-300">
            {error}
          </div>
          {(retry || children) && (
            <div className="mt-2">
              {retry && (
                <button
                  type="button"
                  onClick={retry}
                  className="bg-red-50 dark:bg-red-900/20 text-red-800 dark:text-red-400 text-sm font-medium px-2 py-1 rounded-md hover:bg-red-100 dark:hover:bg-red-900/40 transition-colors"
                >
                  Try again
                </button>
              )}
              {children}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}