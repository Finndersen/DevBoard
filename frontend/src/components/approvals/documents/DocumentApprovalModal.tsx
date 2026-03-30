import { useEffect, useRef, type ReactNode } from 'react'
import { XMarkIcon, DocumentTextIcon } from '@heroicons/react/24/outline'
import { surfaces, borderColors, textColors } from '../../../styles/designSystem'

interface DocumentApprovalModalProps {
  isOpen: boolean
  onClose: () => void
  title: string
  children: ReactNode
  onApprove?: () => void
  onDeny?: () => void
  onConfirmDeny?: () => void
  showDenyFeedback?: boolean
}

export default function DocumentApprovalModal({
  isOpen,
  onClose,
  title,
  children,
  onApprove,
  onDeny,
  onConfirmDeny,
  showDenyFeedback = false
}: DocumentApprovalModalProps) {
  const modalRef = useRef<HTMLDivElement>(null)

  // Handle keyboard navigation
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (!isOpen) return

      switch (event.key) {
        case 'Escape':
          if (showDenyFeedback) {
            // Cancel deny feedback mode - handled by parent
            event.preventDefault()
          } else {
            onClose()
          }
          break
        case 'Enter':
          if (event.ctrlKey || event.metaKey) {
            event.preventDefault()
            if (showDenyFeedback && onConfirmDeny) {
              onConfirmDeny()
            } else if (onApprove) {
              onApprove()
            }
          }
          break
        case 'r':
          if ((event.ctrlKey || event.metaKey) && onDeny) {
            event.preventDefault()
            onDeny()
          }
          break
      }
    }

    if (isOpen) {
      document.addEventListener('keydown', handleKeyDown)
      // Prevent body scroll when modal is open
      document.body.style.overflow = 'hidden'

      // Focus the modal when it opens
      requestAnimationFrame(() => {
        modalRef.current?.focus()
      })
    }

    return () => {
      document.removeEventListener('keydown', handleKeyDown)
      document.body.style.overflow = 'unset'
    }
  }, [isOpen, onClose, onApprove, onDeny, onConfirmDeny, showDenyFeedback])

  // Handle click outside modal
  const handleBackdropClick = (event: React.MouseEvent) => {
    if (event.target === event.currentTarget) {
      onClose()
    }
  }

  if (!isOpen) {
    return null
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      onClick={handleBackdropClick}
      role="dialog"
      aria-modal="true"
      aria-labelledby="modal-title"
    >
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black bg-opacity-50 backdrop-blur-sm" />

      {/* Modal */}
      <div
        ref={modalRef}
        tabIndex={-1}
        className={`relative w-full max-w-6xl h-full max-h-[90vh] mx-4 ${surfaces.raised} rounded-lg shadow-2xl flex flex-col`}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className={`flex items-center justify-between p-6 border-b ${borderColors.default}`}>
          <div className="flex items-center space-x-3">
            <DocumentTextIcon className="w-6 h-6 text-blue-600 dark:text-blue-400" />
            <h2 id="modal-title" className={`text-xl font-semibold ${textColors.primary}`}>
              {title}
            </h2>
          </div>
          <button
            onClick={onClose}
            className="p-2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition-colors"
            aria-label="Close modal"
          >
            <XMarkIcon className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-auto p-6">
          {children}
        </div>
      </div>
    </div>
  )
}
