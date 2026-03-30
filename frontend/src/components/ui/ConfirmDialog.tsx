import type { ReactNode } from 'react'
import { useEffect, useRef } from 'react'
import { ExclamationTriangleIcon } from '@heroicons/react/24/outline'
import { statusColors } from '../../styles/designSystem'

interface ConfirmDialogProps {
  isOpen: boolean
  onClose: () => void
  onConfirm: () => void
  title: string
  message: ReactNode
  confirmText?: string
  cancelText?: string
  variant?: 'danger' | 'warning' | 'info'
  loading?: boolean
}

const variantConfig = {
  danger: {
    icon: 'text-red-600 dark:text-red-500',
    iconBg: statusColors.error.icon,
    confirmButton: 'bg-red-600 hover:bg-red-700 focus:ring-red-500 text-white'
  },
  warning: {
    icon: 'text-yellow-600 dark:text-yellow-500',
    iconBg: statusColors.warning.icon,
    confirmButton: 'bg-yellow-600 hover:bg-yellow-700 focus:ring-yellow-500 text-white'
  },
  info: {
    icon: 'text-blue-600 dark:text-blue-500',
    iconBg: statusColors.info.icon,
    confirmButton: 'bg-blue-600 hover:bg-blue-700 focus:ring-blue-500 text-white'
  }
}

export default function ConfirmDialog({
  isOpen,
  onClose,
  onConfirm,
  title,
  message,
  confirmText = 'Confirm',
  cancelText = 'Cancel',
  variant = 'danger',
  loading = false
}: ConfirmDialogProps) {
  const dialogRef = useRef<HTMLDivElement>(null)
  const cancelButtonRef = useRef<HTMLButtonElement>(null)
  const config = variantConfig[variant]

  // Focus trap and Escape key handling
  useEffect(() => {
    if (!isOpen) return

    // Focus the cancel button by default (safe choice)
    cancelButtonRef.current?.focus()

    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose()
      }
    }

    const handleTabKey = (e: KeyboardEvent) => {
      if (e.key !== 'Tab' || !dialogRef.current) return

      const focusableElements = dialogRef.current.querySelectorAll<HTMLElement>(
        'button:not([disabled]), [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
      )
      const firstElement = focusableElements[0]
      const lastElement = focusableElements[focusableElements.length - 1]

      if (e.shiftKey && document.activeElement === firstElement) {
        e.preventDefault()
        lastElement?.focus()
      } else if (!e.shiftKey && document.activeElement === lastElement) {
        e.preventDefault()
        firstElement?.focus()
      }
    }

    document.addEventListener('keydown', handleEscape)
    document.addEventListener('keydown', handleTabKey)

    return () => {
      document.removeEventListener('keydown', handleEscape)
      document.removeEventListener('keydown', handleTabKey)
    }
  }, [isOpen, onClose])

  if (!isOpen) return null

  return (
    <div
      className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50"
      role="dialog"
      aria-modal="true"
      aria-labelledby="confirm-dialog-title"
      aria-describedby="confirm-dialog-description"
      onClick={(e) => {
        // Close if clicking the backdrop
        if (e.target === e.currentTarget) {
          onClose()
        }
      }}
    >
      <div
        ref={dialogRef}
        className="bg-white dark:bg-gray-800 rounded-lg max-w-md w-full p-6 shadow-xl"
      >
        {/* Icon and Title */}
        <div className="flex items-start space-x-4 mb-4">
          <div className={`flex-shrink-0 w-12 h-12 rounded-full ${config.iconBg} flex items-center justify-center`}>
            <ExclamationTriangleIcon className={`w-6 h-6 ${config.icon}`} />
          </div>
          <div className="flex-1">
            <h3
              id="confirm-dialog-title"
              className="text-lg font-semibold text-gray-900 dark:text-white"
            >
              {title}
            </h3>
            <div
              id="confirm-dialog-description"
              className="mt-2 text-sm text-gray-600 dark:text-gray-400"
            >
              {message}
            </div>
          </div>
        </div>

        {/* Actions */}
        <div className="flex items-center justify-end space-x-3 mt-6">
          <button
            ref={cancelButtonRef}
            onClick={onClose}
            disabled={loading}
            className="inline-flex items-center justify-center px-4 py-2 text-sm font-medium rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-white/[0.06] text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-white/[0.12] focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {cancelText}
          </button>
          <button
            onClick={onConfirm}
            disabled={loading}
            className={`inline-flex items-center justify-center px-4 py-2 text-sm font-medium rounded-md border border-transparent focus:outline-none focus:ring-2 focus:ring-offset-2 transition-colors disabled:opacity-50 disabled:cursor-not-allowed ${config.confirmButton}`}
            aria-label={`${confirmText} (destructive action)`}
          >
            {loading && (
              <svg className="w-4 h-4 mr-2 animate-spin" fill="none" viewBox="0 0 24 24">
                <circle
                  className="opacity-25"
                  cx="12"
                  cy="12"
                  r="10"
                  stroke="currentColor"
                  strokeWidth="4"
                />
                <path
                  className="opacity-75"
                  fill="currentColor"
                  d="m4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                />
              </svg>
            )}
            {confirmText}
          </button>
        </div>
      </div>
    </div>
  )
}
