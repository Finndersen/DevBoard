import { useState } from 'react'
import { ClipboardDocumentIcon, CheckIcon } from '@heroicons/react/24/outline'
import Modal from '../ui/Modal'
import Button from '../ui/Button'

interface SessionIdModalProps {
  isOpen: boolean
  onClose: () => void
  sessionId: string
  title?: string
  description?: string
}

export default function SessionIdModal({
  isOpen,
  onClose,
  sessionId,
  title = 'Session ID',
  description = 'This is the external session identifier for this conversation.'
}: SessionIdModalProps) {
  const [copied, setCopied] = useState(false)

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(sessionId)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch (error) {
      console.error('Failed to copy session ID:', error)
    }
  }

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={title}
      maxWidth="md"
    >
      <div className="space-y-4">
        <p className="text-sm text-gray-600 dark:text-gray-300">
          {description}
        </p>

        <div className="relative">
          <div className="bg-gray-50 dark:bg-gray-800 rounded-lg p-3 border border-gray-200 dark:border-gray-600">
            <code className="text-sm text-gray-800 dark:text-gray-200 break-all select-all">
              {sessionId}
            </code>
          </div>
          <button
            onClick={handleCopy}
            className="absolute top-2 right-2 p-2 bg-white dark:bg-white/[0.06] hover:bg-gray-100 dark:hover:bg-white/[0.12] rounded border border-gray-200 dark:border-gray-600 transition-colors"
            title={copied ? "Copied!" : "Copy to clipboard"}
          >
            {copied ? (
              <CheckIcon className="w-4 h-4 text-green-600 dark:text-green-400" />
            ) : (
              <ClipboardDocumentIcon className="w-4 h-4 text-gray-600 dark:text-gray-400" />
            )}
          </button>
        </div>

        <div className="flex justify-end">
          <Button variant="secondary" onClick={onClose}>
            Close
          </Button>
        </div>
      </div>
    </Modal>
  )
}
