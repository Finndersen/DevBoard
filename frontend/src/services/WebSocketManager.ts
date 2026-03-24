import type { ConversationEvent } from '../lib/api'

type WebSocketEventHandler = (conversationId: number, event: ConversationEvent) => void

class WebSocketManager {
  private ws: WebSocket | null = null
  private eventHandler: WebSocketEventHandler | null = null
  private reconnectTimeout: ReturnType<typeof setTimeout> | null = null
  private destroyed = false
  private reconnectAttempts = 0
  private readonly MAX_RECONNECT_ATTEMPTS = 10
  private readonly BASE_RECONNECT_DELAY_MS = 1000

  setEventHandler(handler: WebSocketEventHandler): void {
    this.eventHandler = handler
  }

  initialize(): void {
    this.destroyed = false
    this.reconnectAttempts = 0
    this.openConnection()
  }

  destroy(): void {
    this.destroyed = true
    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout)
      this.reconnectTimeout = null
    }
    if (this.ws) {
      this.ws.close()
      this.ws = null
    }
  }

  getConnectionStatus(): 'connected' | 'connecting' | 'disconnected' {
    if (!this.ws) return 'disconnected'
    switch (this.ws.readyState) {
      case WebSocket.OPEN: return 'connected'
      case WebSocket.CONNECTING: return 'connecting'
      default: return 'disconnected'
    }
  }

  private openConnection(): void {
    if (this.destroyed) return

    const wsUrl = this.getWebSocketURL()
    this.ws = new WebSocket(wsUrl)

    this.ws.onopen = () => {
      console.log('WebSocketManager: Connection opened')
      this.reconnectAttempts = 0
    }

    this.ws.onmessage = (event) => {
      if (!this.eventHandler) return
      try {
        const data = JSON.parse(event.data as string) as { conversation_id: number }
        this.eventHandler(data.conversation_id, data as unknown as ConversationEvent)
      } catch (error) {
        console.error('WebSocketManager: Failed to parse message:', error)
      }
    }

    this.ws.onerror = (error) => {
      if (!this.destroyed) {
        console.error('WebSocketManager: Connection error:', error)
      }
    }

    this.ws.onclose = (event) => {
      console.log(`WebSocketManager: Connection closed (code=${event.code})`)
      this.ws = null
      if (!this.destroyed) {
        this.scheduleReconnect()
      }
    }
  }

  private scheduleReconnect(): void {
    if (this.reconnectAttempts >= this.MAX_RECONNECT_ATTEMPTS) {
      console.error('WebSocketManager: Max reconnect attempts reached, giving up')
      return
    }
    this.reconnectAttempts++
    const delay = Math.min(
      this.BASE_RECONNECT_DELAY_MS * Math.pow(2, this.reconnectAttempts - 1),
      30_000
    )
    console.log(`WebSocketManager: Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts})`)
    this.reconnectTimeout = setTimeout(() => {
      this.reconnectTimeout = null
      this.openConnection()
    }, delay)
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

export const webSocketManager = new WebSocketManager()
