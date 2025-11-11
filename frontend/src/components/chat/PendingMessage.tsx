import { ArrowPathIcon } from '@heroicons/react/24/outline'
import type { PendingMessage } from '../../contexts/PendingMessagesContext'
import { Button, Markdown } from '../ui'
import {
  getPendingMessageBubbleClasses,
  getTimestampClasses,
  formatTimestamp,
  getStatusIcon
} from '../../styles/messageStyles'

interface PendingMessageProps {
  message: PendingMessage
  onRetry?: (messageId: string) => void
}

export default function PendingMessageComponent({ message, onRetry }: PendingMessageProps) {
  // Pending messages are always from users and always the most recent, so never collapse them
  const isUser = true

  return (
    <div className="w-full">
      {/* Message bubble with pending status styling */}
      <div className={getPendingMessageBubbleClasses(message.status)}>
        <Markdown forceWhiteText={true}>
          {message.text_content}
        </Markdown>
        {/* Timestamp at bottom-right */}
        <div className="flex justify-end items-center gap-1 mt-1">
          <span className="text-xs text-blue-200 dark:text-blue-300">{formatTimestamp(message.timestamp)}</span>
          <span className="text-xs">{getStatusIcon(message.status)}</span>
        </div>
      </div>

      {/* Retry button for failed messages */}
      {message.status === 'failed' && onRetry && (
        <div className="mt-1 flex items-center space-x-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onRetry(message.id)}
            className="text-xs px-2 py-1 h-auto text-red-600 hover:text-red-700 dark:text-red-400 dark:hover:text-red-300"
          >
            <ArrowPathIcon className="w-3 h-3 mr-1" />
            Retry
          </Button>
          {message.error && (
            <span className="text-xs text-red-600 dark:text-red-400">
              {message.error}
            </span>
          )}
        </div>
      )}
    </div>
  )
}