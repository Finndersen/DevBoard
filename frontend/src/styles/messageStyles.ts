/**
 * Shared styling utilities for message components
 */
import { textColors, borderColors, colors } from './designSystem'

export const getMessageAlignment = (_isUser: boolean) =>
  'justify-start'

export const getMessageContainerAlignment = (_isUser: boolean) =>
  'items-start'

export const getUserMessageClasses = (additionalClasses?: string) => {
  return `w-full px-3 py-2 text-sm bg-gray-100 dark:bg-white/[0.06] border ${borderColors.default} ${textColors.primary} ${additionalClasses || ''}`
}

export const getMessageBubbleClasses = (isUser: boolean, additionalClasses?: string) => {
  if (isUser) {
    return getUserMessageClasses(additionalClasses)
  }
  const baseClasses = 'rounded-lg px-3 py-1.5 text-sm'
  const colorClasses = `${colors.gray[100]} ${textColors.primary}`

  return `${baseClasses} ${colorClasses} ${additionalClasses || ''}`
}

export const getPendingMessageBubbleClasses = (status: 'pending' | 'sent' | 'awaiting_approval' | 'failed') => {
  const baseClasses = `w-full px-3 py-2 text-sm ${textColors.primary}`

  switch (status) {
    case 'failed':
      return `${baseClasses} bg-red-500/10 dark:bg-red-500/10`
    case 'pending':
      return `${baseClasses} bg-gray-100 dark:bg-white/[0.06] opacity-75`
    case 'awaiting_approval':
      return `${baseClasses} bg-gray-100 dark:bg-white/[0.06] opacity-90`
    case 'sent':
    default:
      return `${baseClasses} bg-gray-100 dark:bg-white/[0.06]`
  }
}

export const getTimestampClasses = (_isUser: boolean) =>
  'text-gray-500 dark:text-gray-400'

export const formatTimestamp = (timestamp: string) =>
  new Date(timestamp).toLocaleTimeString([], {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  })

export const formatDuration = (durationMs: number) => {
  if (durationMs < 1000) {
    return `${Math.round(durationMs)}ms`
  }
  return `${(durationMs / 1000).toFixed(1)}s`
}

/**
 * Returns "Xs" or "Xms" delay string between two timestamps, or null if no previous timestamp.
 */
export const formatDelay = (currentTimestamp: string, previousTimestamp: string | null): string | null => {
  if (!previousTimestamp) return null
  const diffMs = new Date(currentTimestamp).getTime() - new Date(previousTimestamp).getTime()
  if (diffMs < 0) return null
  return formatDuration(diffMs)
}

/**
 * Returns "HH:MM:SS (Xs)" for display alongside message events.
 * Returns just "HH:MM:SS" if no previous timestamp.
 */
export const formatEventTiming = (timestamp: string, previousTimestamp: string | null): string => {
  const time = new Date(timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
  const delay = formatDelay(timestamp, previousTimestamp)
  return delay ? `${time} (${delay})` : time
}

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