import type { ConversationEvent } from '../lib/api'

interface WebSocketConnection {
  ws: WebSocket
  conversationId: number
  reconnectAttempts: number
  reconnectTimeout: ReturnType<typeof setTimeout> | null
}

/**
 * Singleton WebSocket Manager
 * Manages multiple concurrent WebSocket connections for conversations.
 * Provides a push-based message routing system via registered callbacks,
 * which are consumed by createWebSocketEventStream() in websocketStream.ts.
 */
class WebSocketManager {
  private connections: Map<number, WebSocketConnection> = new Map()
  private messageHandlers: Map<number, Set<(data: string) => void>> = new Map()
  private readonly MAX_CONNECTIONS = 10
  private readonly MAX_RECONNECT_ATTEMPTS = 5
  private readonly BASE_RECONNECT_DELAY = 1000 // 1 second
  private readonly MAX_RECONNECT_DELAY = 30000 // 30 seconds

  /**
   * Ensure a WebSocket connection exists for the given conversation.
   * Creates a new connection if one does not already exist or is not open.
   */
  ensureConnected(conversationId: number): void {
    this.createConnection(conversationId)
  }

  /**
   * Register a handler to receive raw WebSocket message data for a conversation.
   * Multiple handlers can be registered for the same conversation.
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
   * Create or get existing WebSocket connection for a conversation.
   * Returns the WebSocket instance (mostly for internal use).
   */
  private createConnection(conversationId: number): WebSocket {
    // Return existing connection if available
    const existing = this.connections.get(conversationId)
    if (existing?.ws.readyState === WebSocket.OPEN) {
      return existing.ws
    }

    // Check connection limit
    if (this.connections.size >= this.MAX_CONNECTIONS) {
      console.warn('WebSocketManager: Connection limit reached, closing oldest connection')
      this.closeOldestConnection()
    }

    // Create new WebSocket connection
    const wsUrl = this.getWebSocketURL(conversationId)
    const ws = new WebSocket(wsUrl)

    const connection: WebSocketConnection = {
      ws,
      conversationId,
      reconnectAttempts: 0,
      reconnectTimeout: null
    }

    // Set up event handlers
    ws.onopen = () => {
      console.log(`WebSocketManager: Connected to conversation ${conversationId}`)
      connection.reconnectAttempts = 0
    }

    ws.onmessage = (event) => {
      this.routeMessage(conversationId, event.data)
    }

    ws.onerror = (error) => {
      console.error(`WebSocketManager: Error in conversation ${conversationId}:`, error)
    }

    ws.onclose = () => {
      console.log(`WebSocketManager: Disconnected from conversation ${conversationId}`)
      this.handleDisconnect(conversationId)
    }

    this.connections.set(conversationId, connection)
    return ws
  }

  /**
   * Close a specific connection
   */
  closeConnection(conversationId: number): void {
    const connection = this.connections.get(conversationId)
    if (connection) {
      if (connection.reconnectTimeout) {
        clearTimeout(connection.reconnectTimeout)
      }
      connection.ws.close()
      this.connections.delete(conversationId)
      this.messageHandlers.delete(conversationId)
    }
  }

  /**
   * Close all connections
   */
  closeAllConnections(): void {
    this.connections.forEach((connection) => {
      if (connection.reconnectTimeout) {
        clearTimeout(connection.reconnectTimeout)
      }
      connection.ws.close()
    })
    this.connections.clear()
    this.messageHandlers.clear()
  }

  /**
   * Route incoming WebSocket message to all registered handlers for the conversation.
   */
  private routeMessage(conversationId: number, data: string): void {
    const handlers = this.messageHandlers.get(conversationId)
    if (!handlers || handlers.size === 0) {
      return
    }
    handlers.forEach((handler) => {
      try {
        handler(data)
      } catch (error) {
        console.error(`WebSocketManager: Handler error for conversation ${conversationId}:`, error)
      }
    })
  }

  /**
   * Handle disconnect and attempt reconnection
   */
  private handleDisconnect(conversationId: number): void {
    const connection = this.connections.get(conversationId)
    if (!connection) return

    // Don't reconnect if we've exceeded max attempts
    if (connection.reconnectAttempts >= this.MAX_RECONNECT_ATTEMPTS) {
      console.error(`WebSocketManager: Max reconnect attempts reached for conversation ${conversationId}`)
      this.connections.delete(conversationId)
      return
    }

    // Calculate exponential backoff delay
    const delay = Math.min(
      this.BASE_RECONNECT_DELAY * Math.pow(2, connection.reconnectAttempts),
      this.MAX_RECONNECT_DELAY
    )

    console.log(`WebSocketManager: Reconnecting to conversation ${conversationId} in ${delay}ms (attempt ${connection.reconnectAttempts + 1})`)

    connection.reconnectTimeout = setTimeout(() => {
      connection.reconnectAttempts++
      this.createConnection(conversationId)
    }, delay)
  }

  /**
   * Close the oldest inactive connection
   */
  private closeOldestConnection(): void {
    let oldestConnection: WebSocketConnection | null = null

    this.connections.forEach((connection) => {
      if (connection.ws.readyState !== WebSocket.OPEN) {
        oldestConnection = connection
        return
      }
    })

    if (!oldestConnection) {
      oldestConnection = Array.from(this.connections.values())[0]
    }

    if (oldestConnection) {
      this.closeConnection((oldestConnection as WebSocketConnection).conversationId)
    }
  }

  /**
   * Get WebSocket URL for a conversation
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
   * Get connection status for a conversation
   */
  getConnectionStatus(conversationId: number): 'connected' | 'connecting' | 'disconnected' {
    const connection = this.connections.get(conversationId)
    if (!connection) return 'disconnected'

    switch (connection.ws.readyState) {
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
