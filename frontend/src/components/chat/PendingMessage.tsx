import { ArrowPathIcon } from '@heroicons/react/24/outline'
import type { PendingMessage } from '../../contexts/PendingMessagesContext'
import { Button, Markdown } from '../ui'
import {
  getPendingMessageBubbleClasses,
  getStatusIcon
} from '../../styles/messageStyles'

interface PendingMessageProps {
  message: PendingMessage
  onRetry?: (messageId: string) => void
}

export default function PendingMessageComponent({ message, onRetry }: PendingMessageProps) {
  return (
    <div className="flex flex-col w-full">
      <div className="flex w-full justify-end">
        {/* Message bubble with pending status styling and content-based width */}
        <div className={`${getPendingMessageBubbleClasses(message.status)} max-w-full min-w-[200px]`}>
          <Markdown forceWhiteText={true}>
            {message.text_content}
          </Markdown>
          {/* Status icon at bottom-right */}
          <div className="flex justify-end items-center mt-1">
            <span className="text-xs">{getStatusIcon(message.status)}</span>
          </div>
        </div>
      </div>

      {/* Retry button for failed messages */}
      {message.status === 'failed' && onRetry && (
        <div className="mt-1 flex items-center space-x-2 justify-end">
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