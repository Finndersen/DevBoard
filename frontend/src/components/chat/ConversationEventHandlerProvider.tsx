import { useMemo, type ReactNode } from 'react'
import { EventHandlerProvider } from '../../hooks/useConversationEventHandlers'
import type {
  ToolResultHandler,
  SystemEventHandler,
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
    toolResultHandlers: new Set<ToolResultHandler>(),
    systemEventHandlers: new Set<SystemEventHandler>(),
    streamCompleteHandlers: new Set<StreamCompleteHandler>()
  }), [])

  return (
    <EventHandlerProvider value={registry}>
      {children}
    </EventHandlerProvider>
  )
}
