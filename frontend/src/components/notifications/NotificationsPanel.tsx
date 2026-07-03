import { useState, useRef, useEffect } from 'react'
import { BellIcon, XMarkIcon } from '@heroicons/react/24/outline'
import { surfaces, borderColors, textColors, hoverColors } from '../../styles/designSystem'
import { useAllApprovals, useApprovalActions } from '../../stores/approvalsStore'
import { useNotificationStore } from '../../stores/notificationStore'
import { reportMutationError } from '../../lib/errors'
import DocumentDiffModal from '../documents/DocumentDiffModal'
import { getDocumentTypeFromToolName, getReasoningFromToolArgs } from '../../utils/toolTypeUtils'
import type { PendingApproval, ToolApprovalDecision } from '../../lib/api'

export default function NotificationsPanel() {
  const [isOpen, setIsOpen] = useState(false)
  const [selectedApproval, setSelectedApproval] = useState<PendingApproval | null>(null)
  const [selectedApprovalKey, setSelectedApprovalKey] = useState<string | null>(null)
  const panelRef = useRef<HTMLDivElement>(null)
  const approvals = useAllApprovals()
  const { processApprovalDecision } = useApprovalActions()
  const {
    notifications,
    filter,
    setFilter,
    markAsRead,
    markAllAsRead,
    dismissNotification,
    getUnreadCount,
    addNotification,
  } = useNotificationStore()

  const getTotalCount = () => {
    const approvalCount = Object.keys(approvals).reduce((total, key) => {
      return total + (approvals[key]?.length || 0)
    }, 0)
    const notificationCount = getUnreadCount()
    return approvalCount + notificationCount
  }

  // Filter notifications based on current filter setting
  const filteredNotifications = filter === 'unread'
    ? notifications.filter(n => !n.read && !n.dismissed)
    : notifications.filter(n => !n.dismissed)

  const getDisplayName = (key: string) => {
    if (key.startsWith('project-')) {
      const projectId = key.replace('project-', '')
      return `Project ${projectId}`
    } else if (key.startsWith('task-')) {
      const taskId = key.replace('task-', '')
      return `Task ${taskId}`
    }
    return key
  }

  const getDocumentTypeDisplay = (documentType: string | null) => {
    switch (documentType) {
      case 'task_specification':
        return 'Task Specification'
      case 'implementation_plan':
        return 'Implementation Plan'
      case 'project_specification':
        return 'Project Specification'
      case 'initiative_context':
        return 'Initiative Context'
      default:
        return documentType || 'Document'
    }
  }

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (panelRef.current && !panelRef.current.contains(event.target as Node)) {
        setIsOpen(false)
      }
    }

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside)
    }

    return () => {
      document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [isOpen])

  const handleApprovalClick = (key: string, approval: PendingApproval) => {
    setSelectedApproval(approval)
    setSelectedApprovalKey(key)
    setIsOpen(false)
  }

  const handleModalClose = () => {
    setSelectedApproval(null)
    setSelectedApprovalKey(null)
  }

  const handleApprovalDecision = async (toolCallId: string, decision: ToolApprovalDecision) => {
    if (!selectedApprovalKey) return

    try {
      await processApprovalDecision(selectedApprovalKey, toolCallId, decision)
      handleModalClose()
    } catch (error) {
      reportMutationError(addNotification, error, {
        entityType: null,
        entityId: null,
        entityTitle: null,
        fallbackMessage: 'Failed to process approval decision',
      })
      // Still close the modal to prevent UI lockup
      handleModalClose()
    }
  }

  const totalCount = getTotalCount()
  const pendingKeys = Object.keys(approvals).filter(
    key => approvals[key] && approvals[key].length > 0
  )

  const getNotificationIcon = (type: string) => {
    switch (type) {
      case 'tool_approval':
        return '🔧'
      case 'agent_complete':
        return '✅'
      case 'agent_blocked':
        return '⚠️'
      case 'agent_message':
        return '💬'
      case 'build_status':
        return '🏗️'
      case 'system_error':
        return '❌'
      default:
        return '🔔'
    }
  }

  return (
    <>
      <div className="relative" ref={panelRef}>
        <button
          onClick={() => setIsOpen(!isOpen)}
          className="relative p-2 rounded-md text-gray-700 dark:text-gray-300 hover:text-gray-900 dark:hover:text-white hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
          aria-label="Notifications"
        >
          <BellIcon className="w-5 h-5" />
          {totalCount > 0 && (
            <span className="absolute top-0 right-0 inline-flex items-center justify-center px-2 py-1 text-xs font-bold leading-none text-white transform translate-x-1/2 -translate-y-1/2 bg-orange-500 rounded-full">
              {totalCount}
            </span>
          )}
        </button>

        {isOpen && (
          <div className={`absolute right-0 mt-2 w-96 ${surfaces.raised} rounded-lg shadow-lg border ${borderColors.default} z-50`}>
            {/* Header */}
            <div className={`p-4 border-b ${borderColors.default} flex items-center justify-between`}>
              <h3 className={`text-lg font-semibold ${textColors.primary}`}>
                Notifications ({totalCount})
              </h3>
              <div className="flex items-center space-x-2">
                <button
                  onClick={() => setFilter(filter === 'all' ? 'unread' : 'all')}
                  className="text-xs text-blue-600 dark:text-blue-400 hover:underline"
                >
                  {filter === 'all' ? 'Show Unread' : 'Show All'}
                </button>
                {totalCount > 0 && (
                  <button
                    onClick={markAllAsRead}
                    className="text-xs text-gray-600 dark:text-gray-400 hover:underline"
                  >
                    Mark all read
                  </button>
                )}
              </div>
            </div>

            <div className="max-h-96 overflow-y-auto">
              {pendingKeys.length === 0 && filteredNotifications.length === 0 ? (
                <div className="p-8 text-center">
                  <BellIcon className="mx-auto h-12 w-12 text-gray-400" />
                  <p className={`mt-2 text-sm ${textColors.secondary}`}>
                    No notifications
                  </p>
                </div>
              ) : (
                <div className="divide-y divide-gray-200 dark:divide-gray-700">
                  {/* Pending Approvals (High Priority) */}
                  {pendingKeys.map(key => {
                    const keyApprovals = approvals[key] || []
                    return keyApprovals.map((approval) => (
                      <button
                        key={`${key}-${approval.tool_call_id}`}
                        onClick={() => handleApprovalClick(key, approval)}
                        className={`w-full p-4 text-left ${hoverColors.subtle} transition-colors`}
                      >
                        <div className="flex items-start space-x-3">
                          <div className="flex-shrink-0 mt-1">
                            <div className="w-2 h-2 bg-orange-500 rounded-full"></div>
                          </div>
                          <div className="flex-1 min-w-0">
                            <p className={`text-sm font-medium ${textColors.primary}`}>
                              {getDisplayName(key)}
                            </p>
                            <p className={`text-sm ${textColors.secondary}`}>
                              {getDocumentTypeDisplay(getDocumentTypeFromToolName(approval.tool_name))} - {approval.tool_name}
                            </p>
                            {getReasoningFromToolArgs(approval) && (
                              <p className={`text-xs ${textColors.muted} mt-1 line-clamp-2`}>
                                {getReasoningFromToolArgs(approval)}
                              </p>
                            )}
                          </div>
                        </div>
                      </button>
                    ))
                  })}

                  {/* General Notifications */}
                  {filteredNotifications.map((notification) => (
                    <div
                      key={notification.id}
                      className={`p-4 ${!notification.read ? 'bg-blue-50 dark:bg-blue-900/10' : ''}`}
                    >
                      <div className="flex items-start space-x-3">
                        <div className="flex-shrink-0 text-lg">
                          {getNotificationIcon(notification.type)}
                        </div>
                        <div className="flex-1 min-w-0">
                          {notification.entityTitle && (
                            <p className={`text-sm font-medium ${textColors.primary}`}>
                              {notification.entityTitle}
                            </p>
                          )}
                          <p className={`text-sm ${textColors.secondary}`}>
                            {notification.message}
                          </p>
                          <p className={`text-xs ${textColors.muted} mt-1`}>
                            {new Date(notification.timestamp).toLocaleString()}
                          </p>

                          {/* Actions */}
                          {notification.actions.length > 0 && (
                            <div className="flex items-center space-x-2 mt-2">
                              {notification.actions.map((action, idx) => (
                                <button
                                  key={idx}
                                  onClick={() => {
                                    action.action()
                                    if (!notification.read) {
                                      markAsRead(notification.id)
                                    }
                                    setIsOpen(false)
                                  }}
                                  className={`text-xs px-2 py-1 rounded ${
                                    action.style === 'primary'
                                      ? 'bg-blue-600 text-white hover:bg-blue-700'
                                      : action.style === 'danger'
                                      ? 'bg-red-600 text-white hover:bg-red-700'
                                      : 'bg-gray-200 dark:bg-gray-600 text-gray-700 dark:text-gray-300 hover:bg-gray-300 dark:hover:bg-gray-500'
                                  }`}
                                >
                                  {action.label}
                                </button>
                              ))}
                            </div>
                          )}
                        </div>

                        {/* Dismiss button */}
                        <button
                          onClick={() => dismissNotification(notification.id)}
                          className="flex-shrink-0 p-1 hover:bg-gray-200 dark:hover:bg-gray-600 rounded"
                          aria-label="Dismiss"
                        >
                          <XMarkIcon className="w-4 h-4 text-gray-500" />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {selectedApproval && (
        <DocumentDiffModal
          approval={selectedApproval}
          isOpen={true}
          onClose={handleModalClose}
          onApproval={handleApprovalDecision}
        />
      )}
    </>
  )
}