import { useNotificationStore } from '../stores/notificationStore'
import { useUIStore } from '../stores/uiStore'
import { useConversationStore } from '../stores/conversationStore'
import type { ActivityStatus, TabType } from '../stores/uiStore'

export interface AgentOperation {
  id: string
  conversationId: number
  entityType: TabType
  entityId: string
  entityTitle: string
  startTime: Date
  status: 'running' | 'completed' | 'failed'
  progress?: number
}

/**
 * Singleton Activity Manager
 * Tracks background operations and generates notifications
 */
class ActivityManager {
  private activeOperations: Map<string, AgentOperation> = new Map()

  /**
   * Start tracking a background operation
   */
  startBackgroundOperation(operation: Omit<AgentOperation, 'id' | 'startTime' | 'status'>): string {
    const id = `operation-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`
    const fullOperation: AgentOperation = {
      ...operation,
      id,
      startTime: new Date(),
      status: 'running'
    }

    this.activeOperations.set(id, fullOperation)

    // Update tab activity status
    this.updateTabActivity(operation.entityType, operation.entityId, {
      type: 'agent_working'
    })

    // Update conversation typing indicator
    const { setIsTyping } = useConversationStore.getState()
    setIsTyping(operation.conversationId, true)

    return id
  }

  /**
   * Update operation progress
   */
  updateOperationProgress(operationId: string, progress: number): void {
    const operation = this.activeOperations.get(operationId)
    if (operation) {
      operation.progress = progress
    }
  }

  /**
   * Mark operation as completed and generate notification
   */
  completeOperation(operationId: string, result?: { message?: string }): void {
    const operation = this.activeOperations.get(operationId)
    if (!operation) return

    operation.status = 'completed'

    // Update tab activity status
    this.updateTabActivity(operation.entityType, operation.entityId, {
      type: 'idle'
    })

    // Clear typing indicator
    const { setIsTyping } = useConversationStore.getState()
    setIsTyping(operation.conversationId, false)

    // Generate completion notification
    const { addNotification } = useNotificationStore.getState()
    addNotification({
      type: 'agent_complete',
      priority: 'normal',
      entityType: operation.entityType,
      entityId: operation.entityId,
      entityTitle: operation.entityTitle,
      conversationId: operation.conversationId,
      message: result?.message || `Agent completed work on ${operation.entityTitle}`,
      actions: [
        {
          label: 'View Results',
          action: () => this.navigateToEntity(operation.entityType, operation.entityId),
          style: 'primary'
        },
        {
          label: 'Dismiss',
          action: () => {
            const { removeNotification } = useNotificationStore.getState()
            removeNotification(operationId)
          },
          style: 'secondary'
        }
      ]
    })

    // Remove from active operations
    this.activeOperations.delete(operationId)
  }

  /**
   * Mark operation as failed and generate error notification
   */
  failOperation(operationId: string, error: { message: string }): void {
    const operation = this.activeOperations.get(operationId)
    if (!operation) return

    operation.status = 'failed'

    // Update tab activity status
    this.updateTabActivity(operation.entityType, operation.entityId, {
      type: 'action_required'
    })

    // Clear typing indicator
    const { setIsTyping } = useConversationStore.getState()
    setIsTyping(operation.conversationId, false)

    // Generate error notification
    const { addNotification } = useNotificationStore.getState()
    addNotification({
      type: 'agent_blocked',
      priority: 'high',
      entityType: operation.entityType,
      entityId: operation.entityId,
      entityTitle: operation.entityTitle,
      conversationId: operation.conversationId,
      message: `Agent encountered an error: ${error.message}`,
      actions: [
        {
          label: 'View Error',
          action: () => this.navigateToEntity(operation.entityType, operation.entityId),
          style: 'primary'
        },
        {
          label: 'Retry',
          action: () => {
            // Retry logic would go here
            console.log('Retry operation:', operationId)
          },
          style: 'secondary'
        }
      ]
    })

    // Remove from active operations
    this.activeOperations.delete(operationId)
  }

  /**
   * Get all active operations
   */
  getActiveOperations(): AgentOperation[] {
    return Array.from(this.activeOperations.values())
  }

  /**
   * Get active operations for a specific conversation
   */
  getOperationsForConversation(conversationId: number): AgentOperation[] {
    return this.getActiveOperations().filter(
      (op) => op.conversationId === conversationId
    )
  }

  /**
   * Update tab activity status
   */
  private updateTabActivity(entityType: TabType, entityId: string, status: ActivityStatus): void {
    const { findTabByEntity, setTabActivityStatus } = useUIStore.getState()
    const tab = findTabByEntity(entityType, entityId)
    if (tab) {
      setTabActivityStatus(tab.id, status)
    }
  }

  /**
   * Navigate to entity tab
   */
  private navigateToEntity(entityType: TabType, entityId: string): void {
    const { findTabByEntity, switchTab, openTab } = useUIStore.getState()

    // Check if tab exists
    const existingTab = findTabByEntity(entityType, entityId)
    if (existingTab) {
      switchTab(existingTab.id)
    } else {
      // Open new tab
      openTab({
        type: entityType,
        entityId,
        title: `${entityType} #${entityId}`
      })
    }
  }

  /**
   * Generate notification for new message in background
   */
  notifyBackgroundMessage(
    conversationId: number,
    entityType: TabType,
    entityId: string,
    entityTitle: string,
    messagePreview: string
  ): void {
    const { addNotification } = useNotificationStore.getState()
    const { findTabByEntity, activeTabId } = useUIStore.getState()

    // Check if the entity's tab is currently active
    const tab = findTabByEntity(entityType, entityId)
    if (tab && tab.id === activeTabId) {
      // Don't notify if user is actively viewing the conversation
      return
    }

    // Update tab activity status
    if (tab) {
      const { setTabActivityStatus } = useUIStore.getState()
      setTabActivityStatus(tab.id, {
        type: 'new_messages',
        count: 1 // Would need to track actual count
      })
    }

    // Generate notification
    addNotification({
      type: 'agent_message',
      priority: 'low',
      entityType,
      entityId,
      entityTitle,
      conversationId,
      message: `New message: ${messagePreview}`,
      actions: [
        {
          label: 'Open',
          action: () => this.navigateToEntity(entityType, entityId),
          style: 'primary'
        },
        {
          label: 'Dismiss',
          action: () => {
            // Dismiss notification
          },
          style: 'secondary'
        }
      ]
    })
  }
}

// Export singleton instance
export const activityManager = new ActivityManager()
