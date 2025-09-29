import { useState, useRef, useEffect } from 'react'
import { BellIcon } from '@heroicons/react/24/outline'
import { useApprovals } from '../contexts/ApprovalsContext'
import DocumentDiffModal from './DocumentDiffModal'
import type { PendingApproval } from '../lib/api'

export default function NotificationsPanel() {
  const [isOpen, setIsOpen] = useState(false)
  const [selectedApproval, setSelectedApproval] = useState<PendingApproval | null>(null)
  const [selectedApprovalKey, setSelectedApprovalKey] = useState<string | null>(null)
  const panelRef = useRef<HTMLDivElement>(null)
  const { state, removeApproval } = useApprovals()

  const getTotalApprovals = () => {
    return Object.keys(state.approvals).reduce((total, key) => {
      return total + (state.approvals[key]?.length || 0)
    }, 0)
  }

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

  const handleApprovalDecision = (toolCallId: string) => {
    if (!selectedApprovalKey) return

    removeApproval(selectedApprovalKey, toolCallId)
    handleModalClose()
  }

  const totalApprovals = getTotalApprovals()
  const pendingKeys = Object.keys(state.approvals).filter(
    key => state.approvals[key] && state.approvals[key].length > 0
  )

  return (
    <>
      <div className="relative" ref={panelRef}>
        <button
          onClick={() => setIsOpen(!isOpen)}
          className="relative p-2 rounded-md text-gray-700 dark:text-gray-300 hover:text-gray-900 dark:hover:text-white hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
          aria-label="Notifications"
        >
          <BellIcon className="w-5 h-5" />
          {totalApprovals > 0 && (
            <span className="absolute top-0 right-0 inline-flex items-center justify-center px-2 py-1 text-xs font-bold leading-none text-white transform translate-x-1/2 -translate-y-1/2 bg-orange-500 rounded-full">
              {totalApprovals}
            </span>
          )}
        </button>

        {isOpen && (
          <div className="absolute right-0 mt-2 w-96 bg-white dark:bg-gray-800 rounded-lg shadow-lg border border-gray-200 dark:border-gray-700 z-50">
            <div className="p-4 border-b border-gray-200 dark:border-gray-700">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                Notifications
              </h3>
            </div>

            <div className="max-h-96 overflow-y-auto">
              {pendingKeys.length === 0 ? (
                <div className="p-8 text-center">
                  <BellIcon className="mx-auto h-12 w-12 text-gray-400" />
                  <p className="mt-2 text-sm text-gray-600 dark:text-gray-400">
                    No pending approvals
                  </p>
                </div>
              ) : (
                <div className="divide-y divide-gray-200 dark:divide-gray-700">
                  {pendingKeys.map(key => {
                    const approvals = state.approvals[key] || []
                    return approvals.map((approval) => (
                      <button
                        key={`${key}-${approval.tool_call_id}`}
                        onClick={() => handleApprovalClick(key, approval)}
                        className="w-full p-4 text-left hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors"
                      >
                        <div className="flex items-start space-x-3">
                          <div className="flex-shrink-0 mt-1">
                            <div className="w-2 h-2 bg-orange-500 rounded-full"></div>
                          </div>
                          <div className="flex-1 min-w-0">
                            <p className="text-sm font-medium text-gray-900 dark:text-white">
                              {getDisplayName(key)}
                            </p>
                            <p className="text-sm text-gray-600 dark:text-gray-400">
                              {getDocumentTypeDisplay(approval.document_type)} - {approval.tool_name}
                            </p>
                            {approval.reasoning && (
                              <p className="text-xs text-gray-500 dark:text-gray-500 mt-1 line-clamp-2">
                                {approval.reasoning}
                              </p>
                            )}
                          </div>
                        </div>
                      </button>
                    ))
                  })}
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