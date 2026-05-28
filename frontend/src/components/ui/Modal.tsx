import type { ReactNode } from 'react'
import { surfaces, textColors } from '../../styles/designSystem'

interface ModalProps {
  isOpen: boolean
  onClose: () => void
  title: ReactNode
  children: ReactNode
  maxWidth?: 'sm' | 'md' | 'lg' | 'xl' | '2xl' | '3xl' | '4xl' | '6xl' | '7xl' | 'screen'
  scrollable?: boolean
}

const maxWidthClasses = {
  sm: 'max-w-sm',
  md: 'max-w-md',
  lg: 'max-w-lg',
  xl: 'max-w-xl',
  '2xl': 'max-w-2xl',
  '3xl': 'max-w-3xl',
  '4xl': 'max-w-4xl',
  '6xl': 'max-w-6xl',
  '7xl': 'max-w-7xl',
  screen: 'max-w-[80vw]'
}

export default function Modal({ isOpen, onClose, title, children, maxWidth = 'md', scrollable = true }: ModalProps) {
  if (!isOpen) return null

  return (
    <div className={`fixed inset-0 ${surfaces.overlay} flex items-center justify-center p-4 z-50`}>
      <div className={`${surfaces.raised} rounded-lg ${maxWidthClasses[maxWidth]} w-full p-6 max-h-[90vh] flex flex-col`}>
        <div className="flex justify-between items-center mb-4">
          <h3 className={`text-lg font-medium ${textColors.primary} flex-1 min-w-0`}>
            {title}
          </h3>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors"
            aria-label="Close modal"
          >
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <div className={`flex-1 min-h-0 ${scrollable ? 'overflow-auto' : 'overflow-hidden flex flex-col'}`}>
          {children}
        </div>
      </div>
    </div>
  )
}