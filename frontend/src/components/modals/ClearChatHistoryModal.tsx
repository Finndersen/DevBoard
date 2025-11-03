import type { ReactNode } from 'react'
import Modal from '../ui/Modal'
import Button from '../ui/Button'

interface ClearChatHistoryModalProps {
  isOpen: boolean
  onClose: () => void
  onConfirm: () => void | Promise<void>
  loading?: boolean
  title?: string
  children?: ReactNode
}

export default function ClearChatHistoryModal({
  isOpen,
  onClose,
  onConfirm,
  loading = false,
  title = 'Clear Chat History',
  children
}: ClearChatHistoryModalProps) {
  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={title}
      maxWidth="sm"
    >
      <div className="space-y-4">
        {children || (
          <p className="text-gray-600 dark:text-gray-300">
            Are you sure you want to clear all conversation history? This action cannot be undone.
          </p>
        )}

        <div className="flex justify-end space-x-3">
          <Button
            variant="secondary"
            onClick={onClose}
            disabled={loading}
          >
            Cancel
          </Button>
          <Button
            variant="primary"
            onClick={onConfirm}
            loading={loading}
          >
            Clear History
          </Button>
        </div>
      </div>
    </Modal>
  )
}
