import type { ConversationEvent } from '../lib/api'

/**
 * Singleton WebSocket Manager
 *
 * Manages per-execution WebSocket connections. Each execution gets a fresh
 * connection that the server closes after sending execution_completed.
 * No auto-reconnection — server-initiated close is the expected lifecycle.
 */
class WebSocketManager {
  private connections: Map<number, WebSocket> = new Map()
  private messageHandlers: Map<number, Set<(data: string) => void>> = new Map()
  private closeHandlers: Map<number, Set<(code: number, reason: string) => void>> = new Map()

  /**
   * Open a fresh WebSocket connection for a conversation execution.
   * Closes any existing connection for the same conversation first.
   */
  connect(conversationId: number): void {
    // Close any existing connection before opening a new one
    this.closeConnection(conversationId)

    const wsUrl = this.getWebSocketURL(conversationId)
    const ws = new WebSocket(wsUrl)

    ws.onopen = () => {
      console.log(`WebSocketManager: Connected to conversation ${conversationId}`)
    }

    ws.onmessage = (event) => {
      this.routeMessage(conversationId, event.data)
    }

    ws.onerror = (error) => {
      console.error(`WebSocketManager: Error in conversation ${conversationId}:`, error)
    }

    ws.onclose = (event) => {
      console.log(`WebSocketManager: Connection closed for conversation ${conversationId} (code=${event.code}, reason=${event.reason})`)
      this.connections.delete(conversationId)
      // Notify close handlers (e.g., websocketStream needs to know)
      const handlers = this.closeHandlers.get(conversationId)
      if (handlers) {
        handlers.forEach((handler) => {
          try {
            handler(event.code, event.reason)
          } catch (error) {
            console.error(`WebSocketManager: Close handler error for conversation ${conversationId}:`, error)
          }
        })
      }
    }

    this.connections.set(conversationId, ws)
  }

  /**
   * Register a handler to receive raw WebSocket message data for a conversation.
   */
  registerMessageHandler(conversationId: number, handler: (data: string) => void): void {
    if (!this.messageHandlers.has(conversationId)) {
      this.messageHandlers.set(conversationId, new Set())
    }
    this.messageHandlers.get(conversationId)!.add(handler)
  }

  /**
   * Unregister a previously registered message handler.
   */
  unregisterMessageHandler(conversationId: number, handler: (data: string) => void): void {
    this.messageHandlers.get(conversationId)?.delete(handler)
  }

  /**
   * Register a handler for WebSocket close events.
   */
  registerCloseHandler(conversationId: number, handler: (code: number, reason: string) => void): void {
    if (!this.closeHandlers.has(conversationId)) {
      this.closeHandlers.set(conversationId, new Set())
    }
    this.closeHandlers.get(conversationId)!.add(handler)
  }

  /**
   * Unregister a close handler.
   */
  unregisterCloseHandler(conversationId: number, handler: (code: number, reason: string) => void): void {
    this.closeHandlers.get(conversationId)?.delete(handler)
  }

  /**
   * Close a specific connection. Does not trigger reconnection.
   */
  closeConnection(conversationId: number): void {
    const ws = this.connections.get(conversationId)
    if (ws) {
      ws.close()
      this.connections.delete(conversationId)
    }
    this.messageHandlers.delete(conversationId)
    this.closeHandlers.delete(conversationId)
  }

  /**
   * Close all connections.
   */
  closeAllConnections(): void {
    this.connections.forEach((ws) => ws.close())
    this.connections.clear()
    this.messageHandlers.clear()
    this.closeHandlers.clear()
  }

  /**
   * Route incoming WebSocket message to all registered handlers.
   */
  private routeMessage(conversationId: number, data: string): void {
    const handlers = this.messageHandlers.get(conversationId)
    if (!handlers || handlers.size === 0) return
    handlers.forEach((handler) => {
      try {
        handler(data)
      } catch (error) {
        console.error(`WebSocketManager: Handler error for conversation ${conversationId}:`, error)
      }
    })
  }

  /**
   * Get WebSocket URL for a conversation.
   */
  private getWebSocketURL(conversationId: number): string {
    const baseURL = import.meta.env.VITE_API_BASE_URL || ''
    if (baseURL) {
      const protocol = baseURL.startsWith('https') ? 'wss' : 'ws'
      const host = baseURL.replace(/^https?:\/\//, '')
      return `${protocol}://${host}/api/conversations/${conversationId}/ws`
    }
    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
    return `${protocol}://${window.location.host}/api/conversations/${conversationId}/ws`
  }

  /**
   * Get connection status for a conversation.
   */
  getConnectionStatus(conversationId: number): 'connected' | 'connecting' | 'disconnected' {
    const ws = this.connections.get(conversationId)
    if (!ws) return 'disconnected'

    switch (ws.readyState) {
      case WebSocket.OPEN:
        return 'connected'
      case WebSocket.CONNECTING:
        return 'connecting'
      default:
        return 'disconnected'
    }
  }
}

// Export singleton instance
export const webSocketManager = new WebSocketManager()

// Re-export ConversationEvent for backwards compatibility
export type { ConversationEvent }
