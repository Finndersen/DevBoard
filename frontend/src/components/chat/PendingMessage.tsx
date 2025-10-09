import { ArrowPathIcon } from '@heroicons/react/24/outline'
import type { PendingMessage } from '../../contexts/PendingMessagesContext'
import { Button, Markdown } from '../ui'
import {
  getMessageAlignment,
  getMessageContainerAlignment,
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
  // Pending messages are always from users
  const isUser = true
  
  return (
    <div className={`flex ${getMessageAlignment(isUser)}`}>
      <div className={`max-w-[80%] flex flex-col ${getMessageContainerAlignment(isUser)}`}>
        {/* Message bubble with pending status styling */}
        <div className={getPendingMessageBubbleClasses(message.status)}>
          <Markdown forceWhiteText={true}>
            {message.text_content}
          </Markdown>
          
          {/* Timestamp and status */}
          <div className={`text-xs mt-1 opacity-70 flex items-center justify-between ${getTimestampClasses(isUser)}`}>
            <span>{formatTimestamp(message.timestamp)}</span>
            <span className="ml-2 flex items-center">
              {getStatusIcon(message.status)}
            </span>
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
    </div>
  )
}