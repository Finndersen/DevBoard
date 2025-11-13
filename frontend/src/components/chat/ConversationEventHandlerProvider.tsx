import { useMemo, type ReactNode } from 'react'
import { EventHandlerProvider } from '../../hooks/useConversationEventHandlers'
import type {
  ToolResultHandler,
  ToolResultMatcher,
  SystemEventHandler,
  SystemEventMatcher
} from '../../hooks/useConversationEventHandlers'

interface ConversationEventHandlerProviderProps {
  children: ReactNode
}

/**
 * Provider component for conversation event handlers.
 * Must wrap conversation components that use useToolResultHandler or useSystemEventHandler.
 *
 * @example
 * <ConversationEventHandlerProvider>
 *   <ConversationChat conversationId={123} />
 * </ConversationEventHandlerProvider>
 */
export default function ConversationEventHandlerProvider({ children }: ConversationEventHandlerProviderProps) {
  const registry = useMemo(() => ({
    toolResultHandlers: new Map<ToolResultMatcher, Set<ToolResultHandler>>(),
    systemEventHandlers: new Map<SystemEventMatcher, Set<SystemEventHandler>>()
  }), [])

  return (
    <EventHandlerProvider value={registry}>
      {children}
    </EventHandlerProvider>
  )
}
