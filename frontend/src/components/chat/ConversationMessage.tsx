import { useState, useRef, useEffect } from 'react'
import type { ConversationEvent, ToolResult, SystemEventType, MetaMessageType, LocalCommand } from '../../lib/api'
import {
  getUserMessageClasses,
  formatEventTiming,
  formatDuration,
} from '../../styles/messageStyles'
import { Markdown, Modal } from '../ui'
import ToolCallDisplay from './ToolCallDisplay'
import { getToolDisplayLabel, formatToolDisplayLabel } from '../../utils/toolDisplayLabels'

function ThinkingAnnotation({ durationText, thinkingText }: { durationText: string; thinkingText: string | null }) {
  const [expanded, setExpanded] = useState(false)

  return (
    <div className="py-0.5">
      <button
        onClick={() => thinkingText && setExpanded(e => !e)}
        aria-expanded={thinkingText ? expanded : undefined}
        className={`text-[11px] text-gray-500 dark:text-gray-600 italic text-left ${thinkingText ? 'cursor-pointer hover:text-gray-400 dark:hover:text-gray-500' : 'cursor-default'}`}
      >
        {durationText}{thinkingText && <span className="ml-0.5 not-italic">{expanded ? '▾' : '▸'}</span>}
      </button>
      {expanded && thinkingText && (
        <div className="mt-1 pl-3 border-l border-gray-700/40 max-h-40 overflow-y-auto">
          <p className="text-[11px] text-gray-500 dark:text-gray-600 whitespace-pre-wrap">{thinkingText}</p>
        </div>
      )}
    </div>
  )
}

function LocalCommandDisplay({ message, highlightRing, previousEventTimestamp }: { message: LocalCommand; highlightRing: string; previousEventTimestamp?: string | null }) {
  const [isExpanded, setIsExpanded] = useState(false)
  const isShell = message.command_type === 'shell'
  const hasOutput = message.output.length > 0

  // Strip leading slash from command if present — the icon already provides the prefix
  const displayCommand = isShell ? message.command : message.command.replace(/^\//, '')

  const icon = isShell ? (
    <span className="font-mono text-xs font-bold text-emerald-600 dark:text-emerald-400">&gt;_</span>
  ) : (
    <span className="font-mono text-xs font-bold text-blue-600 dark:text-blue-400">/</span>
  )

  return (
    <div className="flex w-full min-w-0">
      <button
        onClick={hasOutput ? () => setIsExpanded(!isExpanded) : undefined}
        className={`group rounded-md overflow-hidden max-w-full min-w-[200px] text-left bg-gray-100 dark:bg-white/[0.03] border border-gray-200 dark:border-white/[0.06] ${hasOutput ? 'hover:bg-gray-150 dark:hover:bg-white/[0.06] cursor-pointer' : 'cursor-default'} transition-colors ${highlightRing}`}
      >
        <div className="px-3 py-1.5 flex items-center justify-between gap-3">
          <div className="flex items-center gap-2 min-w-0 flex-1">
            {icon}
            <span className="text-xs text-gray-900 dark:text-gray-200 font-mono truncate">
              {displayCommand}
            </span>
            {message.is_error && (
              <svg className="w-4 h-4 text-red-600 dark:text-red-400 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            )}
          </div>
          <div className="flex items-center gap-2 flex-shrink-0">
            <span className="text-[10px] text-gray-600 whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity">
              {formatEventTiming(message.timestamp, previousEventTimestamp ?? null)}
            </span>
            {hasOutput && (
              <svg
                className={`w-4 h-4 text-gray-600 dark:text-gray-400 transition-transform flex-shrink-0 ${isExpanded ? 'rotate-180' : ''}`}
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            )}
          </div>
        </div>

        {isExpanded && hasOutput && (
          <div className="border-t border-gray-300 dark:border-white/[0.08] select-text min-w-0" onClick={(e) => e.stopPropagation()}>
            <div className="px-3 py-2 bg-gray-100 dark:bg-white/[0.05]">
              <pre className="text-xs text-gray-900 dark:text-gray-300 bg-white dark:bg-gray-900 rounded p-2 font-mono border border-gray-300 dark:border-white/[0.08] select-text cursor-text whitespace-pre-wrap overflow-x-auto">
                {message.output}
              </pre>
            </div>
          </div>
        )}
      </button>
    </div>
  )
}

function getSystemEventLabel(type: SystemEventType, data?: Record<string, unknown> | null): string | null {
  switch (type) {
    case 'workspace_create':
      return 'Creating workspace'
    case 'workspace_allocate':
      return 'Allocating workspace'
    case 'workspace_branch_checkout':
      return 'Checking out branch'
    case 'workspace_setup':
      return 'Running workspace setup'
    case 'branch_rebased':
      return data?.message as string ?? 'Branch rebased'
    case 'stash_apply_conflict':
      return 'Stash apply conflict - agent resolving'
    case 'session_expired':
      return (data?.message as string) ?? 'Session expired, starting new conversation'
    case 'task_updated':
      return null // Don't show task_updated events (handled separately)
    case 'conversation_updated':
      return null // Don't show conversation_updated events
    case 'stream_error':
      return `Error: ${(data?.message as string) ?? 'Unknown error'}`
    case 'compacting_conversation':
      return 'Compacting conversation...'
    case 'rate_limit': {
      const status = data?.status as string
      const utilization = data?.utilization as number | undefined
      const pct = utilization != null ? ` (${Math.round(utilization * 100)}% used)` : ''
      const limitType = data?.rate_limit_type as string | undefined
      const typeSuffix = limitType ? ` [${limitType}]` : ''
      return status === 'rejected'
        ? `Rate limit reached${pct}${typeSuffix} — request rejected`
        : `Approaching rate limit${pct}${typeSuffix}`
    }
    default:
      return null
  }
}

interface ConversationMessageProps {
  message: ConversationEvent
  toolResult?: ToolResult
  isLatest?: boolean
  isHighlighted?: boolean
  workingDir?: string
  sessionId?: string
  previousEventTimestamp?: string | null
}

const MAX_COLLAPSED_HEIGHT = 240 // ~10 lines at typical line height

export default function ConversationMessageComponent({ message, toolResult, isLatest = false, isHighlighted = false, workingDir, sessionId, previousEventTimestamp }: ConversationMessageProps) {
  const highlightRing = isHighlighted ? 'ring-2 ring-amber-400 dark:ring-amber-500' : ''
  // Handle different event types
  if (message.event_type === 'message') {
    const isUser = message.role === 'user'
    const [isExpanded, setIsExpanded] = useState(false)
    const [needsExpansion, setNeedsExpansion] = useState(false)
    const contentRef = useRef<HTMLDivElement>(null)

    useEffect(() => {
      // Don't check for expansion if this is the latest message
      if (isLatest || !contentRef.current) {
        setNeedsExpansion(false)
        return
      }

      const height = contentRef.current.scrollHeight
      setNeedsExpansion(height > MAX_COLLAPSED_HEIGHT)
    }, [message.text_content, isLatest])

    if (isUser) {
      return (
        <div className={`${getUserMessageClasses()} ${highlightRing} flex group`}>
          <div className="w-0.5 flex-shrink-0 rounded-full bg-blue-400 dark:bg-blue-500 mr-3" />
          <div className="flex-1 min-w-0">
            <div className="relative">
              <div
                ref={contentRef}
                className={`overflow-hidden transition-all duration-300 ${
                  !isExpanded && needsExpansion ? 'max-h-60' : ''
                }`}
                style={{
                  maxHeight: !isExpanded && needsExpansion ? `${MAX_COLLAPSED_HEIGHT}px` : undefined
                }}
              >
                <Markdown forceWhiteText={false}>
                  {message.text_content}
                </Markdown>
              </div>
              {needsExpansion && !isExpanded && (
                <div className="absolute bottom-0 left-0 right-0 h-16 pointer-events-none bg-gradient-to-t from-gray-100 dark:from-[rgba(255,255,255,0.06)] to-transparent" />
              )}
            </div>
            {needsExpansion && (
              <div className="flex justify-center mt-1">
                <button
                  onClick={() => setIsExpanded(!isExpanded)}
                  className="text-xs font-medium hover:underline text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
                >
                  {isExpanded ? '▲ Show less' : '▼ Show more'}
                </button>
              </div>
            )}
          </div>
          <div className="flex-shrink-0 self-start ml-2 opacity-0 group-hover:opacity-100 transition-opacity">
            <span className="text-[10px] text-gray-600 whitespace-nowrap leading-5">
              {formatEventTiming(message.timestamp, previousEventTimestamp ?? null)}
            </span>
          </div>
        </div>
      )
    }

    // Agent message — plain text, no bubble
    return (
      <div className={`w-full text-sm ${highlightRing} group flex items-start gap-2`}>
        <div className="flex-1 min-w-0">
          <Markdown>{message.text_content}</Markdown>
        </div>
        <div className="flex-shrink-0 self-start opacity-0 group-hover:opacity-100 transition-opacity">
          <span className="text-[10px] text-gray-600 whitespace-nowrap leading-5">
            {formatEventTiming(message.timestamp, previousEventTimestamp ?? null)}
          </span>
        </div>
      </div>
    )
  }

  if (message.event_type === 'tool_call') {
    return <ToolCallDisplay toolCall={message} toolResult={toolResult} isHighlighted={isHighlighted} workingDir={workingDir} sessionId={sessionId} previousEventTimestamp={previousEventTimestamp} />
  }

  // Tool results are rendered as part of their corresponding tool call
  if (message.event_type === 'tool_result') {
    return null
  }

  // Tool call requests (pending approval) - render similarly to tool calls but with different styling
  if (message.event_type === 'tool_call_request') {
    // Compute display label for the tool request (tool_args can be string | object | null)
    const toolArgs = typeof message.tool_args === 'object' ? message.tool_args : null
    const displayLabel = getToolDisplayLabel(message.tool_name, toolArgs, workingDir)

    return (
      <div className="flex w-full min-w-0">
        <div className={`rounded-md overflow-hidden max-w-full min-w-[300px] ${highlightRing}`}>
          <div className="px-3 py-1.5 flex items-center gap-2 min-w-0">
            <svg
              className="w-4 h-4 text-yellow-400 flex-shrink-0"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
              />
            </svg>
            <span
              className="text-sm text-yellow-200 truncate overflow-hidden text-ellipsis whitespace-nowrap"
              title={`Awaiting Approval: ${formatToolDisplayLabel(displayLabel)}`}
            >
              <span className="font-normal">Awaiting Approval: </span>
              <span className="font-semibold">{displayLabel.toolName}</span>
              {displayLabel.details && (
                <span className="font-normal italic text-yellow-300/80">: {displayLabel.details}</span>
              )}
            </span>
          </div>
          {message.tool_args && typeof message.tool_args === 'object' && Object.keys(message.tool_args).length > 0 && (
            <div className="px-3 py-2">
              <div className="text-xs font-medium text-gray-400 mb-2">Arguments:</div>
              <pre className="text-xs text-gray-300 bg-gray-900 rounded p-2 font-mono whitespace-pre overflow-x-auto">
                {typeof message.tool_args === 'string'
                  ? message.tool_args
                  : JSON.stringify(message.tool_args, null, 2)}
              </pre>
            </div>
          )}
        </div>
      </div>
    )
  }

  // System events - render as inline badges (only for specific event types)
  if (message.event_type === 'system') {
    const label = getSystemEventLabel(message.type, message.data)

    // Only render badge if we have a label for this event type
    if (!label) {
      return null
    }

    const isError = message.type === 'stream_error'
    const isWarning = message.type === 'session_expired'
    const colorClasses = isError
      ? 'bg-red-500/10 border-red-500/20 text-red-400'
      : isWarning
        ? 'bg-amber-500/10 border border-amber-500/20 text-amber-400'
        : 'bg-blue-500/10 border border-blue-500/20 text-blue-400'

    return (
      <div className="flex w-full justify-center my-1">
        <div className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs ${colorClasses}`}>
          <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
            {isError ? (
              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
            ) : isWarning ? (
              <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
            ) : (
              <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
            )}
          </svg>
          <span>{label}</span>
        </div>
      </div>
    )
  }

  // Local commands (shell commands or slash commands) - render as expandable cards
  if (message.event_type === 'local_command') {
    if (!message.command) return null
    return <LocalCommandDisplay message={message} highlightRing={highlightRing} previousEventTimestamp={previousEventTimestamp} />
  }

  // Meta messages (compact summaries, skill content) - render as clickable indicator that opens a modal
  if (message.event_type === 'meta_message') {
    const metaLabels: Record<MetaMessageType, string> = {
      compact_summary: 'Conversation compacted',
      skill_content: 'Skill activated',
    }
    const label = metaLabels[message.meta_type]
    const [isModalOpen, setIsModalOpen] = useState(false)

    return (
      <div className="flex w-full justify-center my-1">
        <button
          onClick={() => setIsModalOpen(true)}
          className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs bg-blue-500/10 border border-blue-500/30 text-blue-400 hover:bg-blue-500/25 hover:border-blue-400/60 hover:text-blue-300 transition-colors cursor-pointer ${highlightRing}`}
          title="Click to view details"
        >
          <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
          </svg>
          <span>{label}</span>
          <svg className="w-3 h-3 opacity-60" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
          </svg>
        </button>
        <Modal isOpen={isModalOpen} onClose={() => setIsModalOpen(false)} title={label} maxWidth="6xl">
          <Markdown>{message.text_content}</Markdown>
        </Modal>
      </div>
    )
  }

  // Thinking events - render as subtle muted italic annotation
  if (message.event_type === 'thinking') {
    const durationText = message.duration_seconds != null
      ? `Thought for ${formatDuration(message.duration_seconds * 1000)}`
      : 'Thought'

    return <ThinkingAnnotation durationText={durationText} thinkingText={message.thinking_text} />
  }

  // Fallback for unknown event types
  return null
}