import type { ConversationEvent } from './api'
import { webSocketManager } from '../services/WebSocketManager'

interface ExecutionLifecycleEvent {
  event_type: 'execution_lifecycle'
  event: 'execution_started' | 'execution_completed'
  status: 'completed' | 'interrupted' | 'failed' | null
  error: string | null
}

type WebSocketRawMessage = ConversationEvent | ExecutionLifecycleEvent

/**
 * Create an AsyncGenerator that yields ConversationEvents from a WebSocket connection.
 *
 * Bridges push-based WebSocket messages to a pull-based async generator, allowing the
 * existing startStream() / processConversationStream() pipeline to work unchanged.
 *
 * Handles execution_lifecycle events internally:
 * - execution_started: ignored (no consumer action needed)
 * - execution_completed: terminates the generator. If status is "failed", throws an Error.
 *
 * @param conversationId - The conversation to connect to
 */
export async function* createWebSocketEventStream(
  conversationId: number
): AsyncGenerator<ConversationEvent> {
  const buffer: ConversationEvent[] = []
  let resolveWait: (() => void) | null = null
  let done = false
  let completionStatus: ExecutionLifecycleEvent | null = null
  let parseError: Error | null = null

  const handleMessage = (data: string) => {
    let parsed: WebSocketRawMessage
    try {
      parsed = JSON.parse(data) as WebSocketRawMessage
    } catch (e) {
      parseError = e instanceof Error ? e : new Error('WebSocket message parse error')
      resolveWait?.()
      resolveWait = null
      return
    }

    if (parsed.event_type === 'execution_lifecycle') {
      if ((parsed as ExecutionLifecycleEvent).event === 'execution_completed') {
        completionStatus = parsed as ExecutionLifecycleEvent
        done = true
        resolveWait?.()
        resolveWait = null
      }
      // lifecycle events are not yielded to consumers
      return
    }

    buffer.push(parsed as ConversationEvent)
    resolveWait?.()
    resolveWait = null
  }

  webSocketManager.ensureConnected(conversationId)
  webSocketManager.registerMessageHandler(conversationId, handleMessage)

  try {
    while (true) {
      if (parseError) {
        throw parseError
      }

      if (buffer.length > 0) {
        yield buffer.shift()!
      } else if (done) {
        break
      } else {
        await new Promise<void>((r) => {
          resolveWait = r
        })
      }
    }
  } finally {
    webSocketManager.unregisterMessageHandler(conversationId, handleMessage)
  }

  // Propagate execution failure as an error so the stream store shows error state
  if (completionStatus?.status === 'failed') {
    throw new Error(`Agent execution failed: ${completionStatus.error || 'Unknown error'}`)
  }
}
