import type { ConversationMessage } from '../../lib/api'
import {
  getMessageAlignment,
  getMessageContainerAlignment,
  getMessageBubbleClasses,
  getTimestampClasses,
  formatTimestamp
} from '../../styles/messageStyles'
import { Markdown } from '../ui'

interface ConversationMessageProps {
  message: ConversationMessage
}

export default function ConversationMessageComponent({ message }: ConversationMessageProps) {
  const isUser = message.role === 'user'
  
  return (
    <div className={`flex ${getMessageAlignment(isUser)}`}>
      <div className={`max-w-[80%] flex flex-col ${getMessageContainerAlignment(isUser)}`}>
        {/* Message bubble */}
        <div className={getMessageBubbleClasses(isUser)}>
          <Markdown forceWhiteText={isUser}>
            {message.text_content}
          </Markdown>
          
          {/* Timestamp */}
          <div className={`text-xs mt-1 opacity-70 ${getTimestampClasses(isUser)}`}>
            {formatTimestamp(message.timestamp)}
          </div>
        </div>
      </div>
    </div>
  )
}