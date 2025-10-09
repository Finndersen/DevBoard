import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { immer } from 'zustand/middleware/immer'

export type NotificationType =
  | 'tool_approval'
  | 'agent_complete'
  | 'agent_blocked'
  | 'agent_message'
  | 'build_status'
  | 'system_error'

export type NotificationPriority = 'high' | 'normal' | 'low'

export type EntityType = 'task' | 'project' | 'codebase' | 'settings' | 'home' | null

export interface NotificationAction {
  label: string
  action: () => void
  style: 'primary' | 'secondary' | 'danger'
}

export interface Notification {
  id: string
  type: NotificationType
  priority: NotificationPriority
  entityType: EntityType
  entityId: string | null
  entityTitle: string | null
  conversationId: number | null
  timestamp: Date
  message: string
  actions: NotificationAction[]
  read: boolean
  dismissed: boolean
}

interface NotificationsState {
  notifications: Notification[]
  filter: 'all' | 'unread'
  groupBy: 'none' | 'entity' | 'type'
}

interface NotificationsActions {
  // Add/remove notifications
  addNotification: (notification: Omit<Notification, 'id' | 'timestamp' | 'read' | 'dismissed'>) => string
  removeNotification: (id: string) => void
  clearAllNotifications: () => void

  // Update notification state
  markAsRead: (id: string) => void
  markAllAsRead: () => void
  dismissNotification: (id: string) => void

  // Filtering and grouping
  setFilter: (filter: 'all' | 'unread') => void
  setGroupBy: (groupBy: 'none' | 'entity' | 'type') => void

  // Utilities
  getNotification: (id: string) => Notification | undefined
  getUnreadCount: () => number
  getNotificationsByEntity: (entityType: EntityType, entityId: string) => Notification[]
  getNotificationsByConversation: (conversationId: number) => Notification[]
  hasHighPriorityNotifications: () => boolean
}

type NotificationStore = NotificationsState & NotificationsActions

const STORAGE_KEY = 'devboard-notifications'

export const useNotificationStore = create<NotificationStore>()(
  persist(
    immer((set, get) => ({
      // Initial state
      notifications: [],
      filter: 'all',
      groupBy: 'none',

      // Add/remove notifications
      addNotification: (notificationData) => {
        const id = `notification-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`
        const notification: Notification = {
          ...notificationData,
          id,
          timestamp: new Date(),
          read: false,
          dismissed: false
        }

        set((draft) => {
          // Add to beginning of array (newest first)
          draft.notifications.unshift(notification)

          // Limit to 100 notifications
          if (draft.notifications.length > 100) {
            draft.notifications = draft.notifications.slice(0, 100)
          }
        })

        return id
      },

      removeNotification: (id) => {
        set((draft) => {
          draft.notifications = draft.notifications.filter(n => n.id !== id)
        })
      },

      clearAllNotifications: () => {
        set((draft) => {
          draft.notifications = []
        })
      },

      // Update notification state
      markAsRead: (id) => {
        set((draft) => {
          const notification = draft.notifications.find(n => n.id === id)
          if (notification) {
            notification.read = true
          }
        })
      },

      markAllAsRead: () => {
        set((draft) => {
          draft.notifications.forEach(n => {
            n.read = true
          })
        })
      },

      dismissNotification: (id) => {
        set((draft) => {
          const notification = draft.notifications.find(n => n.id === id)
          if (notification) {
            notification.dismissed = true
            notification.read = true
          }
        })
      },

      // Filtering and grouping
      setFilter: (filter) => {
        set((draft) => {
          draft.filter = filter
        })
      },

      setGroupBy: (groupBy) => {
        set((draft) => {
          draft.groupBy = groupBy
        })
      },

      // Utilities
      getNotification: (id) => {
        return get().notifications.find(n => n.id === id)
      },

      getUnreadCount: () => {
        return get().notifications.filter(n => !n.read && !n.dismissed).length
      },

      getNotificationsByEntity: (entityType, entityId) => {
        return get().notifications.filter(
          n => n.entityType === entityType && n.entityId === entityId && !n.dismissed
        )
      },

      getNotificationsByConversation: (conversationId) => {
        return get().notifications.filter(
          n => n.conversationId === conversationId && !n.dismissed
        )
      },

      hasHighPriorityNotifications: () => {
        return get().notifications.some(n => n.priority === 'high' && !n.read && !n.dismissed)
      }
    })),
    {
      name: STORAGE_KEY,
      partialize: (state) => ({
        notifications: state.notifications.filter(n => {
          // Only persist critical (high priority) or unread notifications
          // And only keep notifications from last 7 days
          const sevenDaysAgo = new Date()
          sevenDaysAgo.setDate(sevenDaysAgo.getDate() - 7)
          return (
            (n.priority === 'high' || !n.read) &&
            new Date(n.timestamp) > sevenDaysAgo
          )
        }),
        filter: state.filter,
        groupBy: state.groupBy
      })
    }
  )
)
