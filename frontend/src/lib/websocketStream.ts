import type { ConversationEvent, ExecutionCompleteEvent } from './api'
import { webSocketManager } from '../services/WebSocketManager'

/**
 * Thrown when the WebSocket connection closes unexpectedly
 * (shared WS dropped before execution_complete was received).
 * Signals to the consumer that reconnection should be attempted.
 */
export class WebSocketDisconnectedError extends Error {
  constructor(code: number, reason: string) {
    super(`WebSocket disconnected unexpectedly (code=${code}, reason=${reason})`)
    this.name = 'WebSocketDisconnectedError'
  }
}

type WebSocketRawMessage = ConversationEvent | ExecutionCompleteEvent

/**
 * Create an AsyncGenerator that yields ConversationEvents from the shared WebSocket connection.
 *
 * Connects to the shared multiplexed WebSocket at /api/ws and filters events for
 * the specified conversation. The generator terminates when an execution_complete
 * event is received for this conversation.
 *
 * Handles execution_complete events internally — not yielded to consumers.
 * If execution status is "failed", throws an Error after the generator exits.
 *
 * @param conversationId - The conversation to stream events for
 */
export async function* createWebSocketEventStream(
  conversationId: number
): AsyncGenerator<ConversationEvent> {
  const buffer: ConversationEvent[] = []
  let resolveWait: (() => void) | null = null
  let done = false
  let completionEvent: ExecutionCompleteEvent | null = null
  let parseError: Error | null = null
  let serverClosed = false

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

    if (parsed.event_type === 'execution_complete') {
      completionEvent = parsed as ExecutionCompleteEvent
      done = true
      resolveWait?.()
      resolveWait = null
      return
    }

    buffer.push(parsed as ConversationEvent)
    resolveWait?.()
    resolveWait = null
  }

  let closeCode = 0
  let closeReason = ''

  const handleClose = (code: number, reason: string) => {
    // Shared WS dropped before execution_complete — treat as unexpected disconnect.
    if (!done) {
      serverClosed = true
      closeCode = code
      closeReason = reason
      resolveWait?.()
      resolveWait = null
    }
  }

  webSocketManager.connect(conversationId)
  webSocketManager.registerMessageHandler(conversationId, handleMessage)
  webSocketManager.registerCloseHandler(conversationId, handleClose)

  try {
    while (true) {
      if (parseError) {
        throw parseError
      }

      if (serverClosed) {
        throw new WebSocketDisconnectedError(closeCode, closeReason)
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
    webSocketManager.unregisterCloseHandler(conversationId, handleClose)
  }

  // Propagate execution failure as an error so the stream store shows error state
  if (completionEvent?.status === 'failed') {
    throw new Error(`Agent execution failed: ${completionEvent.error || 'Unknown error'}`)
  }
}
