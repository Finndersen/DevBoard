/**
 * Shared styling utilities for message components
 */

export const getMessageAlignment = (isUser: boolean) => 
  isUser ? 'justify-end' : 'justify-start'

export const getMessageContainerAlignment = (isUser: boolean) =>
  isUser ? 'items-end' : 'items-start'

export const getMessageBubbleClasses = (isUser: boolean, additionalClasses?: string) => {
  const baseClasses = 'rounded-lg px-3 py-2 text-sm'
  const colorClasses = isUser 
    ? 'bg-blue-600 text-white'
    : 'bg-gray-100 dark:bg-gray-700 text-gray-900 dark:text-white'
  
  return `${baseClasses} ${colorClasses} ${additionalClasses || ''}`
}

export const getPendingMessageBubbleClasses = (status: 'pending' | 'sent' | 'awaiting_approval' | 'failed') => {
  const baseClasses = 'rounded-lg px-3 py-2 text-sm text-white'
  
  switch (status) {
    case 'failed':
      return `${baseClasses} bg-red-500`
    case 'pending':
      return `${baseClasses} bg-blue-400 opacity-75`
    case 'awaiting_approval':
      return `${baseClasses} bg-blue-500 opacity-90`
    case 'sent':
    default:
      return `${baseClasses} bg-blue-600`
  }
}

export const getTimestampClasses = (isUser: boolean) =>
  isUser ? 'text-blue-100' : 'text-gray-500 dark:text-gray-400'

export const formatTimestamp = (timestamp: string) =>
  new Date(timestamp).toLocaleTimeString([], { 
    hour: '2-digit', 
    minute: '2-digit' 
  })

export const getStatusIcon = (status: 'pending' | 'sent' | 'awaiting_approval' | 'failed') => {
  switch (status) {
    case 'pending':
      return '⏳'
    case 'sent':
      return '📤'
    case 'awaiting_approval':
      return '⏸️'
    case 'failed':
      return '⚠️'
    default:
      return null
  }
}

/**
 * Get compact prose classes for markdown content in messages
 * @deprecated Use the Markdown component instead for better centralization
 */
export const getCompactProseClasses = (isUser: boolean) => {
  const baseClasses = 'prose prose-sm max-w-none'
  const compactClasses = '[&>*:first-child]:mt-0 [&>*:last-child]:mb-0 [&>p]:my-1 [&>p]:leading-snug [&>ul]:my-1 [&>ol]:my-1 [&>li]:my-0 [&>h1]:my-2 [&>h2]:my-2 [&>h3]:my-1 [&>h4]:my-1 [&>h5]:my-1 [&>h6]:my-1 [&>blockquote]:my-2 [&>pre]:my-2 leading-snug'
  const colorClasses = isUser ? 'prose-invert' : 'dark:prose-invert'
  
  return `${baseClasses} ${compactClasses} ${colorClasses}`
}