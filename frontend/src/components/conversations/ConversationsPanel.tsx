import { useState, useRef, useEffect, useCallback, useMemo } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import {
  ClipboardDocumentListIcon,
  FolderIcon,
  CodeBracketIcon,
  ChatBubbleLeftRightIcon,
  ExclamationCircleIcon,
  PlusIcon,
  ArrowTopRightOnSquareIcon,
  XMarkIcon,
} from '@heroicons/react/24/outline'
import { useConversations } from '../../hooks/useConversations'
import { useConversationStreamStore } from '../../stores/conversationStreamStore'
import { useUIStore } from '../../stores/uiStore'
import type { ViewType } from '../../stores/uiStore'
import type { ConversationResponse } from '../../lib/api'
import { textColors, surfaces, borderColors, hoverColors, projectColors, initiativeColors } from '../../styles/designSystem'
import { useViewStreamStatus } from '../../hooks/useViewStreamStatus'
import { StatusIndicator } from '../github/PRStatusComponents'
import { useGithubStore } from '../../stores/githubStore'

const AGENT_ROLE_LABELS: Record<string, string> = {
  project: 'Project',
  project_qa: 'Project',
  task_specification: 'Specification',
  task_planning: 'Planning',
  task_implementation: 'Implementation',
  task_pr_review: 'PR Review',
  task_finalisation: 'Finalisation',
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
    case 'task_finalisation':
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
  const navigate = useNavigate()
  const location = useLocation()
  const { data: conversations, loading, error } = useConversations()
  const navigateTo = useUIStore(s => s.navigateTo)
  const activeViewId = useUIStore(s => s.activeViewId)
  const cachedViews = useUIStore(s => s.cachedViews)
  const conversationsPanelCollapsed = useUIStore(s => s.conversationsPanelCollapsed)
  const clearUnreadConversations = useUIStore(s => s.clearUnreadConversations)
  const removeUnreadConversation = useUIStore(s => s.removeUnreadConversation)
  const { modalDrafts, setOpenModalDraft, createAndOpenDraft, removeModalDraft } = useUIStore()

  // Dropdown state for the "+" button
  const [dropdownOpen, setDropdownOpen] = useState(false)
  const dropdownRef = useRef<HTMLDivElement>(null)
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

  const pendingCreations = useMemo(
    () => Object.entries(modalDrafts).filter(([, draft]) => draft.isCreating === true),
    [modalDrafts]
  )

  // PR status from unified github store
  const fetchForTask = useGithubStore(s => s.fetchForTask)
  const getPrStatusForTask = useGithubStore(s => s.getPrStatusForTask)

  // Track "needs attention" conversations (previously streaming, now completed)
  const [needsAttentionIds, setNeedsAttentionIds] = useState<Set<number>>(new Set())
  const [pulsingIds, setPulsingIds] = useState<Set<number>>(new Set())
  const prevStreamingIdsRef = useRef<Set<number>>(new Set())

  // Fetch PR status for all task_pr_review conversations
  const prReviewTaskIdsKey = useMemo(() => {
    if (!conversations) return ''
    return conversations
      .filter(c => c.agent_role === 'task_pr_review')
      .map(c => c.parent_entity_id)
      .sort((a, b) => a - b)
      .join(',')
  }, [conversations])

  useEffect(() => {
    if (!conversations || !prReviewTaskIdsKey) return
    const prReviewConversations = conversations.filter(c => c.agent_role === 'task_pr_review')
    if (prReviewConversations.length === 0) return

    // Deduplicate by taskId, then fetch each into the github store
    const seenTaskIds = new Set<number>()
    for (const c of prReviewConversations) {
      if (!seenTaskIds.has(c.parent_entity_id)) {
        seenTaskIds.add(c.parent_entity_id)
        fetchForTask(c.parent_entity_id)
      }
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [prReviewTaskIdsKey])

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

      // Track unread conversations when panel is collapsed
      const { conversationsPanelCollapsed, addUnreadConversation } = useUIStore.getState()
      if (conversationsPanelCollapsed) {
        for (const id of newlyCompleted) {
          addUnreadConversation(id)
        }
      }
    }

    prevStreamingIdsRef.current = new Set(streamingConversationIds)
  }, [streamingConversationIds])

  // Clear all unreads when panel transitions from collapsed to expanded
  const prevCollapsedRef = useRef(conversationsPanelCollapsed)
  useEffect(() => {
    if (prevCollapsedRef.current && !conversationsPanelCollapsed) {
      clearUnreadConversations()
    }
    prevCollapsedRef.current = conversationsPanelCollapsed
  }, [conversationsPanelCollapsed, clearUnreadConversations])

  // Sync view activity status from stream store
  useViewStreamStatus(conversations)

  // Click outside to close dropdown
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setDropdownOpen(false)
      }
    }

    if (dropdownOpen) {
      document.addEventListener('mousedown', handleClickOutside)
      return () => document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [dropdownOpen])

  // Get draft count for badge
  const draftCount = Object.keys(modalDrafts).length

  const activeView = cachedViews.find(v => v.id === activeViewId)

  const activeConversationIdFromUrl = useMemo(() => {
    const params = new URLSearchParams(location.search)
    const id = params.get('conversation')
    return id ? parseInt(id, 10) : null
  }, [location.search])

  const handleClick = (item: ConversationResponse) => {
    const viewType = item.parent_entity_type.toLowerCase() as ViewType
    navigateTo({
      type: viewType,
      entityId: String(item.parent_entity_id),
      title: item.parent_entity_name,
    })
    if (viewType === 'project') {
      navigate(`/projects/${item.parent_entity_id}?conversation=${item.id}`)
    }
    setNeedsAttentionIds(prev => {
      const next = new Set(prev)
      next.delete(item.id)
      return next
    })
    removeUnreadConversation(item.id)
  }

  const handleNewTask = () => {
    createAndOpenDraft('task')
    setDropdownOpen(false)
  }

  const handleNewProjectConversation = () => {
    createAndOpenDraft('project_conversation')
    setDropdownOpen(false)
  }

  const handleRestoreDraft = (draftId: string) => {
    setOpenModalDraft(draftId)
    setDropdownOpen(false)
  }

  return (
    <div className={`${conversationsPanelCollapsed ? 'w-0' : 'w-80'} shrink-0 ${surfaces.raised} ${conversationsPanelCollapsed ? '' : `border-r ${borderColors.default}`} flex flex-col overflow-hidden transition-all duration-300`}>
      {/* Header with new conversation button */}
      {!conversationsPanelCollapsed && (
        <div className={`p-3 border-b ${borderColors.default} shrink-0 relative`} ref={dropdownRef}>
          <button
            onClick={() => setDropdownOpen(!dropdownOpen)}
            className={`w-full flex items-center justify-center gap-2 px-3 py-2 rounded-md transition-colors ${hoverColors.subtle} border ${borderColors.input}`}
          >
            <PlusIcon className="w-4 h-4" />
            <span className="text-sm font-medium">New</span>
            {draftCount > 0 && (
              <span className="ml-auto inline-flex items-center justify-center px-1.5 py-0.5 text-xs font-semibold rounded-full bg-blue-50 text-blue-600 border border-blue-200 dark:bg-blue-900/30 dark:text-blue-400 dark:border-blue-800 min-w-[1.25rem]">
                {draftCount}
              </span>
            )}
          </button>

          {/* Dropdown menu */}
          {dropdownOpen && (
            <div className={`absolute top-full left-3 right-3 mt-1 z-50 ${surfaces.raised} border ${borderColors.default} rounded-md shadow-lg`}>
              <div className="py-1">
                {/* Drafts section */}
                {draftCount > 0 && (
                  <>
                    <div className={`px-3 py-2 text-xs font-semibold uppercase tracking-wider ${textColors.secondary} border-b ${borderColors.default}`}>
                      Drafts
                    </div>
                    {Object.entries(modalDrafts).map(([draftId, draft]) => (
                      <button
                        key={draftId}
                        onClick={() => handleRestoreDraft(draftId)}
                        className={`w-full text-left px-3 py-2 text-sm ${hoverColors.subtle} flex items-center gap-2`}
                      >
                        {draft.type === 'task' ? (
                          <ClipboardDocumentListIcon className="w-4 h-4 flex-shrink-0" />
                        ) : (
                          <ChatBubbleLeftRightIcon className="w-4 h-4 flex-shrink-0" />
                        )}
                        <span className="flex-1 truncate">
                          {draft.type === 'task' ? 'New Task: ' : 'Project: '}{draft.previewLabel}
                        </span>
                        <span className="text-xs opacity-75">●</span>
                      </button>
                    ))}
                    <div className={`border-t ${borderColors.default} my-1`} />
                  </>
                )}

                {/* New conversation options */}
                <div className={`px-3 py-2 text-xs font-semibold uppercase tracking-wider ${textColors.secondary}`}>
                  New
                </div>
                <button
                  onClick={handleNewTask}
                  className={`w-full text-left px-3 py-2 text-sm ${hoverColors.subtle} flex items-center gap-2`}
                >
                  <ClipboardDocumentListIcon className="w-4 h-4 flex-shrink-0" />
                  <span>New Task</span>
                </button>
                <button
                  onClick={handleNewProjectConversation}
                  className={`w-full text-left px-3 py-2 text-sm ${hoverColors.subtle} flex items-center gap-2`}
                >
                  <ChatBubbleLeftRightIcon className="w-4 h-4 flex-shrink-0" />
                  <span>Project Conversation</span>
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Conversation list */}
      <div className="flex-1 overflow-y-auto">
        {loading && !conversations && pendingCreations.length === 0 && (
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

        {(pendingCreations.length > 0 || (conversations && conversations.length > 0)) && (
          <div className="divide-y divide-gray-100 dark:divide-gray-700/50">
            {pendingCreations.map(([draftId, draft]) => (
              <div
                key={draftId}
                className="px-3 py-2.5 border-l-2 border-l-blue-500/50 bg-blue-50/30 dark:bg-blue-900/10"
                data-testid="ghost-entry"
              >
                <div className="flex items-center gap-2 min-w-0">
                  <div className="w-4 h-4 shrink-0 animate-spin rounded-full border-b-2 border-blue-500" />
                  <span className={`text-sm flex-1 truncate ${textColors.primary}`}>
                    Initialising task…
                  </span>
                  <button
                    onClick={() => removeModalDraft(draftId)}
                    className={`shrink-0 ${textColors.muted} hover:text-gray-700 dark:hover:text-gray-300`}
                    aria-label="Dismiss initialising task"
                  >
                    <XMarkIcon className="w-4 h-4" />
                  </button>
                </div>
                <div className="mt-1.5 ml-6 space-y-1.5">
                  <div className="h-2.5 bg-gray-200 dark:bg-gray-600 rounded animate-pulse w-3/4" />
                  <div className="h-2.5 bg-gray-200 dark:bg-gray-600 rounded animate-pulse w-1/2" />
                </div>
                {draft.previewLabel && (
                  <div className={`text-xs mt-0.5 ml-6 truncate ${textColors.muted}`}>
                    {draft.previewLabel}
                  </div>
                )}
              </div>
            ))}
            {displayConversations?.map(item => {
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
                String(item.parent_entity_id) === activeView.entityId &&
                (item.parent_entity_type.toUpperCase() !== 'PROJECT' || item.id === activeConversationIdFromUrl)
              )
              const hasDraft = draftKeys.has(`conversation:${item.id}`)
              const isPRReview = item.agent_role === 'task_pr_review'
              const prStatus = isPRReview ? (getPrStatusForTask(item.parent_entity_id) ?? null) : null
              const isTaskConversation = item.parent_entity_type.toUpperCase() === 'TASK'
              const primaryLabel = !isTaskConversation && item.title ? item.title : item.parent_entity_name
              const secondaryLabel = isTaskConversation ? item.project_name : item.parent_entity_name

              let borderStyle: string
              if (needsAttention) {
                borderStyle = 'border-l-2 border-l-blue-500 bg-blue-50 dark:bg-blue-900/20'
              } else if (isSelected) {
                borderStyle = 'border-l-2 border-l-gray-400 dark:border-l-gray-500 bg-gray-100 dark:bg-white/[0.05]'
              } else {
                borderStyle = 'border-l-2 border-l-transparent'
              }

              return (
                <button
                  key={item.id}
                  onClick={() => handleClick(item)}
                  className={`w-full text-left px-3 py-2.5 ${hoverColors.subtle} transition-colors ${borderStyle} ${isPulsing ? 'animate-attention-pulse' : ''}`}
                >
                  {/* Row 1: Icon + name + draft indicator + activity dot */}
                  <div className="flex items-center gap-2 min-w-0">
                    <EntityIcon className={`w-4 h-4 shrink-0 ${textColors.secondary}`} />
                    <span className={`text-sm truncate flex-1 ${textColors.primary}`}>
                      {primaryLabel}
                    </span>
                    {prStatus && !prStatus.merged && (
                      <StatusIndicator
                        mergeableState={prStatus.mergeable_state}
                        ciStatus={prStatus.ci_status}
                        reviewDecision={prStatus.review_decision}
                      />
                    )}
                    {hasDraft && (
                      <span className="shrink-0 text-xs" title="Has draft">✏️</span>
                    )}
                    {isActive && (
                      <span className="relative flex h-2 w-2 shrink-0">
                        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75" />
                        <span className="relative inline-flex rounded-full h-2 w-2 bg-green-500" />
                      </span>
                    )}
                    {!isActive && needsAttention && (
                      <span className="inline-flex rounded-full h-2 w-2 bg-blue-500 shrink-0" />
                    )}
                  </div>
                  {/* Row 2: Role + task ID (for tasks) + timestamp */}
                  <div className="text-xs mt-0.5 ml-6">
                    <span className={roleColor}>{roleLabel}</span>
                    {isTaskConversation && (
                      <span className={textColors.muted}> · #{item.parent_entity_id}</span>
                    )}
                    <span className={textColors.muted}> · {formatRelativeTime(timestamp)}</span>
                  </div>
                  {/* Row 3: Project/initiative (tasks) or entity name (project/codebase conversations) */}
                  {(isTaskConversation ? item.project_name : secondaryLabel) && (
                    <div className={`text-xs mt-0.5 ml-6 flex items-center gap-1 min-w-0`}>
                      {isTaskConversation ? (
                        <>
                          {prStatus?.pr_number && (
                            <a
                              href={prStatus.pr_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className={`flex items-center gap-1 shrink-0 hover:underline ${textColors.accent}`}
                              onClick={e => e.stopPropagation()}
                              title="Open PR in GitHub"
                            >
                              PR #{prStatus.pr_number}
                              <ArrowTopRightOnSquareIcon className="w-2.5 h-2.5 flex-shrink-0 opacity-60 hover:opacity-100" />
                            </a>
                          )}
                          {prStatus?.pr_number && <span className={`shrink-0 ${textColors.muted}`}>•</span>}
                          <span className={`${projectColors.icon} truncate`}>{item.project_name}</span>
                          {item.initiative_name && (
                            <>
                              <span className={`shrink-0 ${textColors.muted}`}>›</span>
                              <span className={`${initiativeColors.icon} truncate`}>{item.initiative_name}</span>
                            </>
                          )}
                        </>
                      ) : (
                        <span className={`truncate ${textColors.muted}`}>{secondaryLabel}</span>
                      )}
                    </div>
                  )}
                </button>
              )
            })}
          </div>
        )}

        {conversations && conversations.length === 0 && pendingCreations.length === 0 && (
          <div className="text-center py-8 px-4">
            <ChatBubbleLeftRightIcon className="w-10 h-10 mx-auto text-gray-400 dark:text-gray-600 mb-3" />
            <p className={`text-sm ${textColors.secondary}`}>No active conversations</p>
          </div>
        )}
      </div>
    </div>
  )
}
