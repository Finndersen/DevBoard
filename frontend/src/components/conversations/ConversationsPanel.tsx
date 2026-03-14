import { useState, useRef, useEffect, useMemo } from 'react'
import {
  ChevronLeftIcon,
  ChevronRightIcon,
  ListBulletIcon,
  FolderIcon,
  CodeBracketIcon,
  ChatBubbleLeftRightIcon,
  ExclamationCircleIcon,
} from '@heroicons/react/24/outline'
import { useConversations } from '../../hooks/useConversations'
import { useUIStore } from '../../stores/uiStore'
import type { TabType } from '../../stores/uiStore'
import type { ActiveExecutionsResponse, ConversationListItem } from '../../lib/api'
import { textColors } from '../../styles/designSystem'

const AGENT_ROLE_LABELS: Record<string, string> = {
  project_qa: 'Project QA',
  task_specification: 'Specification',
  task_planning: 'Planning',
  task_implementation: 'Implementation',
  task_pr_review: 'PR Review',
  codebase_qa: 'Codebase QA',
}

function formatRelativeTime(isoDate: string): string {
  const date = new Date(isoDate)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMinutes = Math.floor(diffMs / 60000)

  if (diffMinutes < 1) return 'Just now'
  if (diffMinutes < 60) return `${diffMinutes}m ago`
  const diffHours = Math.floor(diffMinutes / 60)
  if (diffHours < 24) return `${diffHours}h ago`
  const diffDays = Math.floor(diffHours / 24)
  if (diffDays < 30) return `${diffDays}d ago`
  return date.toLocaleDateString()
}

function getEntityIcon(entityType: string) {
  switch (entityType.toUpperCase()) {
    case 'TASK':
      return ListBulletIcon
    case 'PROJECT':
      return FolderIcon
    case 'CODEBASE':
      return CodeBracketIcon
    default:
      return ChatBubbleLeftRightIcon
  }
}

interface ConversationsPanelProps {
  activeExecutions: ActiveExecutionsResponse | null
  collapsed: boolean
  onToggleCollapse: () => void
}

export default function ConversationsPanel({ activeExecutions, collapsed, onToggleCollapse }: ConversationsPanelProps) {
  const { data: conversations, loading, error } = useConversations()
  const openTab = useUIStore(s => s.openTab)

  // Memoize active conversation IDs to avoid recomputing on every render
  const activeConversationIds = useMemo(
    () => new Set(activeExecutions?.executions.map(e => e.conversation_id) ?? []),
    [activeExecutions?.executions],
  )

  // Track "needs attention" conversations (previously active, now completed)
  const [needsAttentionIds, setNeedsAttentionIds] = useState<Set<number>>(new Set())
  // Track recently-added attention IDs for pulse animation
  const [pulsingIds, setPulsingIds] = useState<Set<number>>(new Set())
  const prevActiveIdsRef = useRef<Set<number>>(new Set())

  useEffect(() => {
    const prevActiveIds = prevActiveIdsRef.current

    // Find conversations that were active but are no longer
    const newlyCompleted = new Set<number>()
    for (const id of prevActiveIds) {
      if (!activeConversationIds.has(id)) {
        newlyCompleted.add(id)
      }
    }

    if (newlyCompleted.size > 0) {
      setNeedsAttentionIds(prev => {
        const next = new Set(prev)
        for (const id of newlyCompleted) {
          next.add(id)
        }
        return next
      })
      // Trigger pulse animation for newly completed conversations
      setPulsingIds(prev => {
        const next = new Set(prev)
        for (const id of newlyCompleted) {
          next.add(id)
        }
        return next
      })
      // Clear pulsing state after animation completes
      setTimeout(() => {
        setPulsingIds(prev => {
          const next = new Set(prev)
          for (const id of newlyCompleted) {
            next.delete(id)
          }
          return next
        })
      }, 2000)
    }

    prevActiveIdsRef.current = new Set(activeConversationIds)
  }, [activeConversationIds])

  const handleClick = (item: ConversationListItem) => {
    const tabType = item.parent_entity_type.toLowerCase() as TabType
    openTab({
      type: tabType,
      entityId: String(item.parent_entity_id),
      title: item.parent_entity_name,
    })
    // Clear "needs attention" for this conversation
    setNeedsAttentionIds(prev => {
      const next = new Set(prev)
      next.delete(item.id)
      return next
    })
  }

  if (collapsed) {
    return (
      <div className="w-10 shrink-0 bg-white dark:bg-gray-800 border-r border-gray-200 dark:border-gray-700 flex flex-col items-center pt-5">
        <button
          onClick={onToggleCollapse}
          className="p-1.5 rounded-md hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-500 dark:text-gray-400 transition-colors"
          aria-label="Expand conversations panel"
          title="Expand conversations"
        >
          <ChevronRightIcon className="w-4 h-4" />
        </button>
      </div>
    )
  }

  return (
    <div className="w-64 shrink-0 bg-white dark:bg-gray-800 border-r border-gray-200 dark:border-gray-700 flex flex-col transition-all duration-200">
      {/* Header */}
      <div className="h-16 flex items-center justify-between px-3 border-b border-gray-200 dark:border-gray-700 flex-shrink-0">
        <h2 className={`text-sm font-semibold ${textColors.primary}`}>Conversations</h2>
        <button
          onClick={onToggleCollapse}
          className="p-1.5 rounded-md hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-500 dark:text-gray-400 transition-colors"
          aria-label="Collapse conversations panel"
        >
          <ChevronLeftIcon className="w-4 h-4" />
        </button>
      </div>

      {/* Conversation list */}
      <div className="flex-1 overflow-y-auto">
        {loading && !conversations && (
          <div className="flex items-center justify-center py-8">
            <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-600" />
          </div>
        )}

        {error && !loading && (
          <div className="text-center py-8 px-4">
            <ExclamationCircleIcon className="w-10 h-10 mx-auto text-red-400 dark:text-red-500 mb-3" />
            <p className="text-sm text-red-600 dark:text-red-400">Failed to load conversations</p>
          </div>
        )}

        {conversations && conversations.length === 0 && (
          <div className="text-center py-8 px-4">
            <ChatBubbleLeftRightIcon className="w-10 h-10 mx-auto text-gray-400 dark:text-gray-600 mb-3" />
            <p className={`text-sm ${textColors.secondary}`}>No active conversations</p>
          </div>
        )}

        {conversations && conversations.length > 0 && (
          <div className="divide-y divide-gray-100 dark:divide-gray-700/50">
            {conversations.map(item => {
              const EntityIcon = getEntityIcon(item.parent_entity_type)
              const isActive = activeConversationIds.has(item.id)
              const needsAttention = needsAttentionIds.has(item.id)
              const isPulsing = pulsingIds.has(item.id)
              const roleLabel = AGENT_ROLE_LABELS[item.agent_role] ?? item.agent_role
              const timestamp = item.last_activity_at ?? item.created_at

              return (
                <button
                  key={item.id}
                  onClick={() => handleClick(item)}
                  className={`w-full text-left px-3 py-2.5 hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors ${
                    needsAttention
                      ? 'border-l-2 border-l-blue-500 bg-blue-50/50 dark:bg-blue-900/10'
                      : 'border-l-2 border-l-transparent'
                  } ${isPulsing ? 'animate-attention-pulse' : ''}`}
                >
                  {/* Row 1: Icon + name + activity dot */}
                  <div className="flex items-center gap-2 min-w-0">
                    <EntityIcon className={`w-4 h-4 shrink-0 ${textColors.secondary}`} />
                    <span className={`text-sm truncate flex-1 ${textColors.primary}`}>
                      {item.parent_entity_name}
                    </span>
                    {isActive && (
                      <span className="relative flex h-2 w-2 shrink-0">
                        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75" />
                        <span className="relative inline-flex rounded-full h-2 w-2 bg-green-500" />
                      </span>
                    )}
                  </div>
                  {/* Row 2: Role + timestamp */}
                  <div className={`text-xs mt-0.5 ml-6 ${textColors.muted}`}>
                    {roleLabel} · {formatRelativeTime(timestamp)}
                  </div>
                </button>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
