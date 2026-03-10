import { useConversationStore } from '../stores/conversationStore'
import type { ConversationEvent } from '../lib/api'

interface WebSocketConnection {
  ws: WebSocket
  conversationId: number
  reconnectAttempts: number
  reconnectTimeout: ReturnType<typeof setTimeout> | null
}

/**
 * Singleton WebSocket Manager
 * Manages multiple concurrent WebSocket connections for conversations
 */
class WebSocketManager {
  private connections: Map<number, WebSocketConnection> = new Map()
  private readonly MAX_CONNECTIONS = 10
  private readonly MAX_RECONNECT_ATTEMPTS = 5
  private readonly BASE_RECONNECT_DELAY = 1000 // 1 second
  private readonly MAX_RECONNECT_DELAY = 30000 // 30 seconds

  /**
   * Create or get existing WebSocket connection for a conversation
   */
  createConnection(conversationId: number): WebSocket {
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
  }

  /**
   * Route incoming WebSocket message to appropriate handler
   */
  private routeMessage(conversationId: number, data: string): void {
    try {
      const event: ConversationEvent = JSON.parse(data)

      // Add event to conversation store
      const { addMessage, setIsTyping } = useConversationStore.getState()

      // For message events from agent, clear typing indicator
      if (event.event_type === 'message' && event.role === 'agent') {
        setIsTyping(conversationId, false)
      }

      addMessage(conversationId, event)
    } catch (error) {
      console.error('WebSocketManager: Failed to parse message:', error)
    }
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
    // Find oldest connection based on last activity
    let oldestConnection: WebSocketConnection | null = null

    this.connections.forEach((connection) => {
      // For simplicity, we'll close any connection that's not OPEN
      if (connection.ws.readyState !== WebSocket.OPEN) {
        oldestConnection = connection
        return
      }
    })

    if (!oldestConnection) {
      // If all connections are open, close the first one (arbitrary)
      oldestConnection = Array.from(this.connections.values())[0]
    }

    if (oldestConnection) {
      this.closeConnection(oldestConnection.conversationId)
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
