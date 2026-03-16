import { useState, useRef, useEffect, useCallback, useMemo } from 'react'
import {
  ClipboardDocumentListIcon,
  FolderIcon,
  CodeBracketIcon,
  ChatBubbleLeftRightIcon,
  ExclamationCircleIcon,
} from '@heroicons/react/24/outline'
import { useConversations } from '../../hooks/useConversations'
import { useConversationStreamStore } from '../../stores/conversationStreamStore'
import { useUIStore } from '../../stores/uiStore'
import type { ViewType } from '../../stores/uiStore'
import type { ConversationListItem } from '../../lib/api'
import { textColors } from '../../styles/designSystem'
import { useViewStreamStatus } from '../../hooks/useViewStreamStatus'

const AGENT_ROLE_LABELS: Record<string, string> = {
  project: 'Project',
  project_qa: 'Project',
  task_specification: 'Specification',
  task_planning: 'Planning',
  task_implementation: 'Implementation',
  task_pr_review: 'PR Review',
  codebase_qa: 'Codebase QA',
  investigation: 'Investigation',
  code_review: 'Code Review',
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

function getAgentRoleColor(agentRole: string): string {
  switch (agentRole) {
    case 'task_specification':
    case 'task_planning':
      return 'text-blue-600 dark:text-blue-400'
    case 'task_implementation':
      return 'text-purple-600 dark:text-purple-400'
    case 'task_pr_review':
      return 'text-amber-600 dark:text-amber-400'
    case 'project':
    case 'project_qa':
    case 'codebase_qa':
    case 'investigation':
      return 'text-teal-600 dark:text-teal-400'
    case 'code_review':
      return 'text-amber-600 dark:text-amber-400'
    default:
      return 'text-gray-500 dark:text-gray-500'
  }
}

function getEntityIcon(entityType: string) {
  switch (entityType.toUpperCase()) {
    case 'TASK':
      return ClipboardDocumentListIcon
    case 'PROJECT':
      return FolderIcon
    case 'CODEBASE':
      return CodeBracketIcon
    default:
      return ChatBubbleLeftRightIcon
  }
}

export default function ConversationsPanel() {
  const { data: conversations, loading, error } = useConversations()
  const navigateTo = useUIStore(s => s.navigateTo)
  const activeViewId = useUIStore(s => s.activeViewId)
  const cachedViews = useUIStore(s => s.cachedViews)
  // Subscribe only to which entities have drafts (not content) to avoid re-renders on every keystroke
  const draftKeysStr = useUIStore(
    useCallback((s) => Object.keys(s.draftMessages).sort().join(','), [])
  )
  const draftKeys = useMemo(
    () => new Set(draftKeysStr ? draftKeysStr.split(',') : []),
    [draftKeysStr]
  )

  // Return a stable primitive string from the selector — useSyncExternalStore requires
  // getSnapshot to return a cached reference, so returning a new Set on every call causes
  // the "getSnapshot should be cached" warning and infinite loops.
  const streamingIdsStr = useConversationStreamStore(
    useCallback((state) => {
      const ids: number[] = []
      for (const [id, stream] of state.activeStreams) {
        if (stream.isStreaming) ids.push(id)
      }
      return ids.sort((a, b) => a - b).join(',')
    }, [])
  )
  const streamingConversationIds = useMemo(
    () => new Set(streamingIdsStr ? streamingIdsStr.split(',').map(Number) : []),
    [streamingIdsStr]
  )

  const displayConversations = useMemo(() => {
    if (!conversations) return null
    return [...conversations].sort((a, b) => {
      const aStreaming = streamingConversationIds.has(a.id) ? 1 : 0
      const bStreaming = streamingConversationIds.has(b.id) ? 1 : 0
      return bStreaming - aStreaming
    })
  }, [conversations, streamingConversationIds])

  // Track "needs attention" conversations (previously streaming, now completed)
  const [needsAttentionIds, setNeedsAttentionIds] = useState<Set<number>>(new Set())
  const [pulsingIds, setPulsingIds] = useState<Set<number>>(new Set())
  const prevStreamingIdsRef = useRef<Set<number>>(new Set())

  useEffect(() => {
    const prevIds = prevStreamingIdsRef.current

    // Find conversations that were streaming but are no longer
    const newlyCompleted = new Set<number>()
    for (const id of prevIds) {
      if (!streamingConversationIds.has(id)) {
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
      setPulsingIds(prev => {
        const next = new Set(prev)
        for (const id of newlyCompleted) {
          next.add(id)
        }
        return next
      })
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

    prevStreamingIdsRef.current = new Set(streamingConversationIds)
  }, [streamingConversationIds])

  // Sync view activity status from stream store
  useViewStreamStatus(conversations)

  const activeView = cachedViews.find(v => v.id === activeViewId)

  const handleClick = (item: ConversationListItem) => {
    const viewType = item.parent_entity_type.toLowerCase() as ViewType
    navigateTo({
      type: viewType,
      entityId: String(item.parent_entity_id),
      title: item.parent_entity_name,
    })
    setNeedsAttentionIds(prev => {
      const next = new Set(prev)
      next.delete(item.id)
      return next
    })
  }

  return (
    <div className="w-80 shrink-0 bg-white dark:bg-gray-800 border-r border-gray-200 dark:border-gray-700 flex flex-col transition-all duration-200">
      {/* Header */}
      <div className="h-16 flex items-center px-3 border-b border-gray-200 dark:border-gray-700 flex-shrink-0">
        <h2 className={`text-sm font-semibold ${textColors.primary}`}>Conversations</h2>
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
            {displayConversations!.map(item => {
              const EntityIcon = getEntityIcon(item.parent_entity_type)
              const isActive = streamingConversationIds.has(item.id)
              const needsAttention = needsAttentionIds.has(item.id)
              const isPulsing = pulsingIds.has(item.id)
              const roleLabel = AGENT_ROLE_LABELS[item.agent_role] ?? item.agent_role
              const roleColor = getAgentRoleColor(item.agent_role)
              const timestamp = item.last_activity_at ?? item.created_at
              const isSelected = !!(
                activeView &&
                item.parent_entity_type.toLowerCase() === activeView.type &&
                String(item.parent_entity_id) === activeView.entityId
              )
              const hasDraft = draftKeys.has(`${item.parent_entity_type.toLowerCase()}:${item.parent_entity_id}`)

              let borderStyle: string
              if (needsAttention) {
                borderStyle = 'border-l-2 border-l-blue-500 bg-blue-50/50 dark:bg-blue-900/10'
              } else if (isSelected) {
                borderStyle = 'border-l-2 border-l-gray-400 dark:border-l-gray-500 bg-gray-100 dark:bg-gray-700/70'
              } else {
                borderStyle = 'border-l-2 border-l-transparent'
              }

              return (
                <button
                  key={item.id}
                  onClick={() => handleClick(item)}
                  className={`w-full text-left px-3 py-2.5 hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors ${borderStyle} ${isPulsing ? 'animate-attention-pulse' : ''}`}
                >
                  {/* Row 1: Icon + name + draft indicator + activity dot */}
                  <div className="flex items-center gap-2 min-w-0">
                    <EntityIcon className={`w-4 h-4 shrink-0 ${textColors.secondary}`} />
                    <span className={`text-sm truncate flex-1 ${textColors.primary}`}>
                      {item.parent_entity_name}
                    </span>
                    {hasDraft && (
                      <span className="shrink-0 text-xs" title="Has draft">✏️</span>
                    )}
                    {isActive && (
                      <span className="relative flex h-2 w-2 shrink-0">
                        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75" />
                        <span className="relative inline-flex rounded-full h-2 w-2 bg-green-500" />
                      </span>
                    )}
                  </div>
                  {/* Row 2: Role + timestamp */}
                  <div className="text-xs mt-0.5 ml-6">
                    <span className={roleColor}>{roleLabel}</span>
                    <span className={textColors.muted}> · {formatRelativeTime(timestamp)}</span>
                  </div>
                  {/* Row 3: Project name (task conversations only) */}
                  {item.project_name && (
                    <div className={`text-xs mt-0.5 ml-6 truncate ${textColors.muted}`}>
                      {item.project_name}
                    </div>
                  )}
                </button>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
