import { useMemo, type ReactNode } from 'react'
import { EventHandlerProvider } from '../../hooks/useConversationEventHandlers'
import type {
  ToolResultHandler,
  ToolResultMatcher,
  SystemEventHandler,
  SystemEventMatcher,
  StreamCompleteHandler
} from '../../hooks/useConversationEventHandlers'

interface ConversationEventHandlerProviderProps {
  children: ReactNode
}

/**
 * Provider component for conversation event handlers.
 * Must wrap conversation components that use useToolResultHandler, useSystemEventHandler, or useStreamCompleteHandler.
 *
 * @example
 * <ConversationEventHandlerProvider>
 *   <ConversationChat conversationId={123} />
 * </ConversationEventHandlerProvider>
 */
export default function ConversationEventHandlerProvider({ children }: ConversationEventHandlerProviderProps) {
  const registry = useMemo(() => ({
    toolResultHandlers: new Map<ToolResultMatcher, Set<ToolResultHandler>>(),
    systemEventHandlers: new Map<SystemEventMatcher, Set<SystemEventHandler>>(),
    streamCompleteHandlers: new Set<StreamCompleteHandler>()
  }), [])

  return (
    <EventHandlerProvider value={registry}>
      {children}
    </EventHandlerProvider>
  )
}
