import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import {
  PencilIcon,
  CheckIcon,
  XMarkIcon,
  ChevronDownIcon,
  CodeBracketIcon,
  TrashIcon,
  FolderIcon,
  ChatBubbleLeftIcon,
  ArrowPathIcon,
  WrenchScrewdriverIcon,
} from '@heroicons/react/24/outline'
import { CheckCircleIcon } from '@heroicons/react/24/solid'
import { StatusIndicator, ReviewBadge } from '../github/PRStatusComponents'
import { TaskStatus } from '../../lib/api'
import type { Task, Codebase, TaskGitStatus, GitHubPRStatusResponse } from '../../lib/api'
import { useEditableField } from '../../hooks/useEditableField'
import { Button, Input, StatusBadge, ConfirmDialog } from '../ui'
import { textColors, borderColors, surfaces } from '../../styles/designSystem'

// Git branch icon (Y-shape: trunk at bottom splitting into branch at top-right)
const GitBranchIcon = ({ className }: { className?: string }) => (
  <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="20" r="2" />
    <circle cx="12" cy="4" r="2" />
    <circle cx="18" cy="6" r="2" />
    <path d="M12 18 L12 6" />
    <path d="M12 18 Q16 14 18 8" />
  </svg>
)

// GitHub mark icon
const GitHubIcon = ({ className }: { className?: string }) => (
  <svg className={className} viewBox="0 0 16 16" fill="currentColor">
    <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z" />
  </svg>
)

interface TaskDetailHeaderProps {
  task: Task
  project: { id: number; name: string } | null | undefined
  titleField: ReturnType<typeof useEditableField<string>>
  codebases: Codebase[] | null | undefined
  selectedCodebase: Codebase | null | undefined
  gitStatus: TaskGitStatus | null
  branchStatusLoading: boolean
  prStatus: GitHubPRStatusResponse | null
  prStatusLoading: boolean
  onRefreshPrStatus: () => void
  workflowActionButtons: React.ReactElement | null
  onCodebaseSelect: (codebaseId: number | null) => void
  onOpenBranchStatusModal: () => void
  onDeleteTask: (deleteBranch: boolean) => void
  deleteLoading: boolean
  deleteError: unknown
  onResolveConflicts: () => void
  isConversationStreaming: boolean
}

const getStatusVariant = (status: TaskStatus): 'default' | 'success' | 'warning' | 'error' | 'info' => {
  switch (status) {
    case TaskStatus.PLANNING:
    case TaskStatus.IMPLEMENTING:
      return 'info'
    case TaskStatus.PR_OPEN:
      return 'warning'
    case TaskStatus.COMPLETE:
      return 'success'
    default:
      return 'default'
  }
}

export function TaskDetailHeader({
  task,
  project,
  titleField,
  codebases,
  selectedCodebase,
  gitStatus,
  branchStatusLoading,
  prStatus,
  prStatusLoading,
  onRefreshPrStatus,
  workflowActionButtons,
  onCodebaseSelect,
  onOpenBranchStatusModal,
  onDeleteTask,
  deleteLoading,
  onResolveConflicts,
  isConversationStreaming,
}: TaskDetailHeaderProps) {
  const [showCodebaseSelector, setShowCodebaseSelector] = useState(false)
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)
  const [deleteBranch, setDeleteBranch] = useState(true)
  const hasBranchWarning = gitStatus?.has_conflicts || gitStatus?.has_uncommitted_base_overlap || gitStatus?.remote_fetch_failed || gitStatus?.base_has_conflicting_uncommitted

  // Close codebase selector when clicking outside
  useEffect(() => {
    if (!showCodebaseSelector) return

    const handleClickOutside = (event: MouseEvent) => {
      const target = event.target as HTMLElement
      if (!target.closest('.relative')) {
        setShowCodebaseSelector(false)
      }
    }

    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [showCodebaseSelector])

  const handleConfirmDelete = async () => {
    await onDeleteTask(deleteBranch)
    setShowDeleteConfirm(false)
  }

  return (
    <>
      <div className="flex items-center gap-3 mb-2">
        {/* Title: flex-1 so it takes remaining space; line-clamp-2 allows up to 2 lines before truncating */}
        <div className="flex items-center gap-1 min-w-0 flex-1">
          {titleField.isEditing ? (
            <>
              <Input
                type="text"
                value={titleField.editedValue}
                onChange={(e) => titleField.setEditedValue(e.target.value)}
                className="text-lg font-bold h-8 flex-shrink-0"
                style={{ width: `${Math.max(20, titleField.editedValue.length * 0.8 + 5)}ch` }}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') titleField.save()
                  if (e.key === 'Escape') titleField.cancelEditing()
                }}
              />
              <Button
                onClick={(e) => {
                  e.preventDefault()
                  titleField.save()
                }}
                variant="secondary"
                size="sm"
                className="flex-shrink-0 p-1.5 min-w-[28px] h-7 border border-green-300 bg-green-50 text-green-700 hover:bg-green-100 hover:border-green-400 dark:border-green-600 dark:bg-green-900/30 dark:text-green-400 dark:hover:bg-green-900/50"
                title="Save (Enter)"
                loading={titleField.saving}
              >
                <CheckIcon className="w-4 h-4" />
              </Button>
              <Button
                onClick={(e) => {
                  e.preventDefault()
                  titleField.cancelEditing()
                }}
                variant="secondary"
                size="sm"
                className="flex-shrink-0 p-1.5 min-w-[28px] h-7 border border-gray-300 bg-gray-50 text-gray-600 hover:bg-gray-100 hover:border-gray-400 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-400 dark:hover:bg-gray-700"
                title="Cancel (Escape)"
              >
                <XMarkIcon className="w-4 h-4" />
              </Button>
            </>
          ) : (
            <>
              <h1
                className={`text-xl font-bold line-clamp-2 min-w-0 ${textColors.primary}`}
                title={task.title}
              >
                {task.title}
              </h1>
              <Button
                onClick={(e) => {
                  e.preventDefault()
                  titleField.startEditing()
                }}
                variant="ghost"
                size="sm"
                className="flex-shrink-0 p-2 text-gray-600 hover:text-gray-800 dark:text-gray-400 dark:hover:text-gray-200"
                title="Edit title"
              >
                <PencilIcon className="w-4 h-4" />
              </Button>
              <Button
                onClick={() => setShowDeleteConfirm(true)}
                variant="ghost"
                size="sm"
                className="flex-shrink-0 p-1.5 text-gray-400 hover:text-red-600 hover:bg-red-50 dark:text-gray-600 dark:hover:text-red-400 dark:hover:bg-red-900/20"
                title="Delete task"
                aria-label="Delete task"
              >
                <TrashIcon className="w-3.5 h-3.5" />
              </Button>
            </>
          )}
        </div>

        <StatusBadge variant={getStatusVariant(task.status)}>
          {task.status}
        </StatusBadge>

        {/* Compact project / codebase display */}
        <div className="flex items-center text-sm flex-shrink-0">
          {project && (
            <Link
              to={`/projects/${project.id}`}
              className="flex items-center space-x-1 px-1.5 py-0.5 rounded hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
              title="View project"
            >
              <FolderIcon className="w-3.5 h-3.5 text-gray-400 dark:text-gray-500" />
              <span className="text-blue-600 dark:text-blue-400 hover:underline max-w-[100px] truncate">{project.name}</span>
            </Link>
          )}
          {project && selectedCodebase && (
            <span className="text-gray-400 dark:text-gray-600 mx-0.5">/</span>
          )}
          <div className="relative">
            {selectedCodebase ? (
              <Link
                to={`/codebases/${selectedCodebase.id}`}
                className="flex items-center space-x-1 px-1.5 py-0.5 rounded hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
                title="View codebase"
              >
                <CodeBracketIcon className="w-3.5 h-3.5 text-gray-400 dark:text-gray-500" />
                <span className="text-blue-600 dark:text-blue-400 hover:underline max-w-[100px] truncate">{selectedCodebase.name}</span>
              </Link>
            ) : (
              <>
                <button
                  onClick={() => setShowCodebaseSelector(!showCodebaseSelector)}
                  className={`flex items-center space-x-1 px-1.5 py-0.5 rounded text-sm ${textColors.secondary} hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors`}
                  title="Select codebase"
                >
                  <CodeBracketIcon className="w-3.5 h-3.5" />
                  <span className="italic">No codebase</span>
                  <ChevronDownIcon className="w-3 h-3" />
                </button>

                {showCodebaseSelector && (
                  <div className={`absolute top-full left-0 mt-1 w-64 ${surfaces.raised} border ${borderColors.default} rounded-lg shadow-lg z-10`}>
                    <div className="max-h-64 overflow-y-auto">
                      {codebases && codebases.map((codebase: Codebase) => (
                        <button
                          key={codebase.id}
                          onClick={() => {
                            setShowCodebaseSelector(false)
                            onCodebaseSelect(codebase.id)
                          }}
                          className={`w-full text-left px-4 py-2 text-sm hover:bg-gray-50 dark:hover:bg-gray-700 ${
                            codebase.id === task.codebase_id ? 'bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400' : textColors.primary
                          } ${codebase.id !== codebases[0].id ? 'border-t border-gray-100 dark:border-white/[0.08]' : ''}`}
                        >
                          <div className="font-medium">{codebase.name}</div>
                          <div className={`text-xs ${textColors.secondary} truncate`}>{codebase.local_path}</div>
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
        </div>

        {/* Branch Status Icon - only shown when task has a branch_name and is not complete */}
        {gitStatus?.branch_name && task.status !== TaskStatus.COMPLETE && (
          <button
            onClick={onOpenBranchStatusModal}
            className={`flex-shrink-0 flex items-center space-x-1.5 px-2 py-1 rounded text-sm border transition-colors ${
              hasBranchWarning
                ? 'border-amber-400 bg-amber-50 text-amber-700 hover:bg-amber-100 dark:border-amber-500 dark:bg-amber-900/30 dark:text-amber-400 dark:hover:bg-amber-900/50'
                : gitStatus.worktree_slot_path
                  ? 'border-blue-400 bg-blue-50 text-blue-600 hover:bg-blue-100 dark:border-blue-500 dark:bg-blue-900/30 dark:text-blue-400 dark:hover:bg-blue-900/50'
                  : 'border-gray-300 hover:bg-gray-100 dark:border-gray-600 dark:hover:bg-gray-800 ' + textColors.secondary
            }`}
            title={
              gitStatus.has_conflicts
                ? 'Branch has conflicts with base branch'
                : gitStatus.has_uncommitted_base_overlap
                  ? 'Uncommitted changes overlap with base branch'
                  : gitStatus.remote_fetch_failed
                    ? 'Remote fetch failed — showing local state'
                    : gitStatus.base_has_conflicting_uncommitted
                      ? 'Uncommitted changes in main repo conflict with task branch'
                      : gitStatus.branch_name
            }
            disabled={branchStatusLoading}
          >
            <GitBranchIcon className="w-4 h-4" />
            {gitStatus.commits_ahead > 0 && (
              <span className="text-xs font-medium text-green-700 dark:text-green-300">↑{gitStatus.commits_ahead}</span>
            )}
            {gitStatus.commits_behind > 0 && (
              <span className="text-xs font-medium text-yellow-700 dark:text-yellow-300">↓{gitStatus.commits_behind}</span>
            )}
            {hasBranchWarning && (
              <svg className="w-3.5 h-3.5 text-amber-500 dark:text-amber-400" viewBox="0 0 20 20" fill="currentColor">
                <path fillRule="evenodd" d="M8.485 2.495c.673-1.167 2.357-1.167 3.03 0l6.28 10.875c.673 1.167-.17 2.625-1.516 2.625H3.72c-1.347 0-2.189-1.458-1.515-2.625L8.485 2.495zM10 6a.75.75 0 01.75.75v3.5a.75.75 0 01-1.5 0v-3.5A.75.75 0 0110 6zm0 9a1 1 0 100-2 1 1 0 000 2z" clipRule="evenodd" />
              </svg>
            )}
          </button>
        )}

        {/* PR Status - shown when task has a PR (pr_open or complete) */}
        {(task.status === TaskStatus.PR_OPEN || task.status === TaskStatus.COMPLETE) && (prStatus || prStatusLoading) && (
          <div className="flex-shrink-0 flex items-center rounded border border-gray-300 dark:border-gray-600 overflow-hidden">
            {prStatus && (
              <button
                onClick={() => window.open(prStatus.pr_url, '_blank')}
                className={`flex items-center space-x-1.5 px-2 py-1 text-sm hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors ${textColors.secondary}`}
                title={prStatus.merged ? "PR Merged" : "Open PR on GitHub"}
              >
                <GitHubIcon className="w-4 h-4" />
                {prStatus.merged ? (
                  <CheckCircleIcon className="w-3.5 h-3.5 text-purple-500" />
                ) : (
                  <StatusIndicator mergeableState={prStatus.mergeable_state} ciStatus={prStatus.ci_status} />
                )}
                <span className="font-medium">#{prStatus.pr_number}</span>
                <ReviewBadge decision={prStatus.review_decision} />
                {prStatus.comment_count > 0 && (
                  <span className="flex items-center space-x-0.5">
                    <ChatBubbleLeftIcon className="w-3.5 h-3.5" />
                    <span>{prStatus.comment_count}</span>
                  </span>
                )}
              </button>
            )}
            {prStatus?.mergeable_state?.toUpperCase() === 'DIRTY' && (
              <button
                onClick={onResolveConflicts}
                disabled={isConversationStreaming}
                className="flex items-center px-1.5 py-1 text-sm border-l border-gray-300 dark:border-gray-600 text-amber-500 hover:text-amber-600 hover:bg-amber-50 dark:text-amber-400 dark:hover:text-amber-300 dark:hover:bg-amber-900/20 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                title="Rebase and resolve conflicts"
                aria-label="Rebase and resolve conflicts"
              >
                <WrenchScrewdriverIcon className="w-3.5 h-3.5" />
              </button>
            )}
            {task.status === TaskStatus.PR_OPEN && (
              <button
                onClick={onRefreshPrStatus}
                disabled={prStatusLoading}
                className={`flex items-center px-1.5 py-1 text-sm border-l border-gray-300 dark:border-gray-600 hover:bg-gray-100 dark:hover:bg-gray-800 disabled:opacity-50 disabled:cursor-not-allowed transition-colors ${textColors.secondary}`}
                title="Refresh PR status"
              >
                <ArrowPathIcon className={`w-3.5 h-3.5 ${prStatusLoading ? 'animate-spin' : ''}`} />
              </button>
            )}
          </div>
        )}

        <div className="flex-shrink-0">
          {workflowActionButtons}
        </div>
      </div>

      {/* Delete Confirmation Dialog */}
      <ConfirmDialog
        isOpen={showDeleteConfirm}
        onClose={() => setShowDeleteConfirm(false)}
        onConfirm={handleConfirmDelete}
        title="Delete Task"
        message={
          <div>
            <p>Are you sure you want to delete "{task.title}"? This will permanently delete the task, its specification, implementation plan, conversations, and all associated data. This action cannot be undone.</p>
            {gitStatus?.branch_exists && gitStatus.commits_ahead > 0 && (
              <div style={{ marginTop: '12px', padding: '8px', backgroundColor: '#fff3cd', borderRadius: '4px' }}>
                ⚠️ Branch has {gitStatus.commits_ahead} unmerged commit{gitStatus.commits_ahead !== 1 ? 's' : ''}
              </div>
            )}
            {gitStatus?.branch_exists && (
              <label style={{ display: 'flex', alignItems: 'center', marginTop: '16px', cursor: 'pointer' }}>
                <input
                  type="checkbox"
                  checked={deleteBranch}
                  onChange={(e) => setDeleteBranch(e.target.checked)}
                  style={{ marginRight: '8px' }}
                />
                <span>
                  Also delete git branch {gitStatus?.branch_name && `"${gitStatus.branch_name}"`}
                </span>
              </label>
            )}
            {!gitStatus?.branch_exists && gitStatus?.branch_name && (
              <div style={{ marginTop: '12px', fontSize: '0.9em', color: '#666', fontStyle: 'italic' }}>
                Branch "{gitStatus.branch_name}" does not exist
              </div>
            )}
          </div>
        }
        confirmText="Delete Task"
        cancelText="Cancel"
        variant="danger"
        loading={deleteLoading}
      />
    </>
  )
}
