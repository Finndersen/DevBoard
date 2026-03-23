import type { ConversationEvent } from '../lib/api'

/**
 * Singleton WebSocket Manager
 *
 * Manages a single shared WebSocket connection to /api/ws.
 * All conversation executions share this one connection.
 * Each message includes a conversation_id to route events to the correct handlers.
 */
class WebSocketManager {
  private ws: WebSocket | null = null
  private messageHandlers: Map<number, Set<(data: string) => void>> = new Map()
  private closeHandlers: Map<number, Set<(code: number, reason: string) => void>> = new Map()
  private activeConversations: Set<number> = new Set()

  /**
   * Mark a conversation as active and open the shared connection if not already open.
   */
  connect(conversationId: number): void {
    this.activeConversations.add(conversationId)
    if (!this.ws || this.ws.readyState === WebSocket.CLOSED || this.ws.readyState === WebSocket.CLOSING) {
      this.openSharedConnection()
    }
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
   * Remove a conversation's handlers and close the shared connection if no conversations remain active.
   */
  closeConnection(conversationId: number): void {
    this.activeConversations.delete(conversationId)
    this.messageHandlers.delete(conversationId)
    this.closeHandlers.delete(conversationId)
    if (this.activeConversations.size === 0 && this.ws) {
      this.ws.close()
      this.ws = null
    }
  }

  /**
   * Close all connections and clear all state.
   */
  closeAllConnections(): void {
    this.ws?.close()
    this.ws = null
    this.activeConversations.clear()
    this.messageHandlers.clear()
    this.closeHandlers.clear()
  }

  /**
   * Get connection status for a conversation.
   */
  getConnectionStatus(conversationId: number): 'connected' | 'connecting' | 'disconnected' {
    if (!this.activeConversations.has(conversationId) || !this.ws) return 'disconnected'
    switch (this.ws.readyState) {
      case WebSocket.OPEN:
        return 'connected'
      case WebSocket.CONNECTING:
        return 'connecting'
      default:
        return 'disconnected'
    }
  }

  private openSharedConnection(): void {
    const wsUrl = this.getWebSocketURL()
    this.ws = new WebSocket(wsUrl)

    this.ws.onopen = () => {
      console.log('WebSocketManager: Shared connection opened')
    }

    this.ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data as string) as { conversation_id: number }
        this.routeMessage(data.conversation_id, event.data as string)
      } catch (error) {
        console.error('WebSocketManager: Failed to parse message:', error)
      }
    }

    this.ws.onerror = (error) => {
      console.error('WebSocketManager: Shared connection error:', error)
    }

    this.ws.onclose = (event) => {
      console.log(`WebSocketManager: Shared connection closed (code=${event.code}, reason=${event.reason})`)
      this.ws = null
      this.activeConversations.forEach((conversationId) => {
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
      })
    }
  }

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

  private getWebSocketURL(): string {
    const baseURL = import.meta.env.VITE_API_BASE_URL || ''
    if (baseURL) {
      const protocol = baseURL.startsWith('https') ? 'wss' : 'ws'
      const host = baseURL.replace(/^https?:\/\//, '')
      return `${protocol}://${host}/api/ws`
    }
    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
    return `${protocol}://${window.location.host}/api/ws`
  }
}

// Export singleton instance
export const webSocketManager = new WebSocketManager()

// Re-export ConversationEvent for backwards compatibility
export type { ConversationEvent }
