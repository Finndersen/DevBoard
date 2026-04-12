import type { EntityType, Notification } from '../stores/notificationStore'

/**
 * Dispatches a system_error notification for a user-triggered mutation that failed.
 * Prefer this over bare console.error for mutations so the user always sees feedback.
 */
export function reportMutationError(
  addNotification: (n: Omit<Notification, 'id' | 'timestamp' | 'read' | 'dismissed'>) => string,
  err: unknown,
  context: {
    entityType: EntityType
    entityId: string | null
    entityTitle: string | null
    fallbackMessage: string
  }
): void {
  console.error(context.fallbackMessage, err)
  addNotification({
    type: 'system_error',
    priority: 'high',
    entityType: context.entityType,
    entityId: context.entityId,
    entityTitle: context.entityTitle,
    conversationId: null,
    message: err instanceof Error ? err.message : context.fallbackMessage,
    actions: [],
  })
}
