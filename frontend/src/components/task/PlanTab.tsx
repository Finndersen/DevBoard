import { useState, useCallback, useEffect, memo } from 'react'
import type { ComponentType } from 'react'
import { CheckIcon, XMarkIcon, PencilIcon, ChevronDownIcon, ChevronRightIcon, ClockIcon, ArrowPathIcon, CheckCircleIcon, XCircleIcon, MinusCircleIcon, StopCircleIcon, CodeBracketIcon, DocumentTextIcon, ClipboardDocumentCheckIcon, EyeIcon, ChatBubbleLeftRightIcon } from '@heroicons/react/24/outline'
import { StopIcon } from '@heroicons/react/24/solid'
import { MarkdownDocumentEditor } from '../MarkdownDocumentEditor'
import { Button, Markdown, StatusBadge, Textarea } from '../ui'
import { textColors, borderColors, surfaces, hoverColors, statusColors } from '../../styles/designSystem'
import { apiClient, TaskStatus } from '../../lib/api'
import { useNotificationStore } from '../../stores/notificationStore'
import type { DocumentResponse, ImplementationPlanResponse, ImplementationStepResponse, ImplementationStepStatus, ImplementationStepType } from '../../lib/api'
import SubAgentConversationModal from '../claude-code/SubAgentConversationModal'

function formatDuration(seconds: number): string {
  if (seconds < 60) {
    return `${seconds}s`
  } else if (seconds < 3600) {
    const m = Math.floor(seconds / 60)
    const s = seconds % 60
    return `${m}m ${s}s`
  } else {
    const h = Math.floor(seconds / 3600)
    const m = Math.floor((seconds % 3600) / 60)
    return `${h}h ${m}m`
  }
}

interface StepDurationProps {
  step: ImplementationStepResponse
}

function StepDuration({ step }: StepDurationProps) {
  const [elapsedSeconds, setElapsedSeconds] = useState<number>(() => {
    if (step.status === 'running' && step.started_at) {
      return Math.floor((Date.now() - new Date(step.started_at).getTime()) / 1000)
    }
    return 0
  })

  useEffect(() => {
    if (step.status !== 'running' || !step.started_at) return
    const interval = setInterval(() => {
      setElapsedSeconds(Math.floor((Date.now() - new Date(step.started_at!).getTime()) / 1000))
    }, 1000)
    return () => clearInterval(interval)
  }, [step.status, step.started_at])

  if (step.status === 'running' && step.started_at) {
    return <span className="text-xs text-gray-500 dark:text-gray-400 tabular-nums">{formatDuration(elapsedSeconds)}</span>
  }

  if ((step.status === 'complete' || step.status === 'failed' || step.status === 'interrupted') && step.started_at && step.completed_at) {
    const durationSeconds = Math.floor(
      (new Date(step.completed_at).getTime() - new Date(step.started_at).getTime()) / 1000
    )
    return <span className="text-xs text-gray-500 dark:text-gray-400 tabular-nums">{formatDuration(durationSeconds)}</span>
  }

  return null
}

const STEP_STATUS_CONFIG: Record<ImplementationStepStatus, { icon: ComponentType<{ className?: string }>; iconClass: string; variant: 'default' | 'success' | 'warning' | 'error' | 'info' }> = {
  pending: { icon: ClockIcon, iconClass: 'text-gray-400', variant: 'default' },
  running: { icon: ArrowPathIcon, iconClass: 'text-blue-500 animate-spin', variant: 'info' },
  complete: { icon: CheckCircleIcon, iconClass: 'text-green-500', variant: 'success' },
  failed: { icon: XCircleIcon, iconClass: 'text-red-500', variant: 'error' },
  skipped: { icon: MinusCircleIcon, iconClass: 'text-gray-400', variant: 'warning' },
  interrupted: { icon: StopCircleIcon, iconClass: 'text-yellow-500', variant: 'warning' },
}

const STEP_TYPE_CONFIG: Record<ImplementationStepType, { label: string; icon: ComponentType<{ className?: string }>; variant: 'default' | 'info' | 'warning' | 'success' }> = {
  code_change: { label: 'Code Change', icon: CodeBracketIcon, variant: 'info' },
  documentation: { label: 'Documentation', icon: DocumentTextIcon, variant: 'default' },
  validation: { label: 'Validation', icon: ClipboardDocumentCheckIcon, variant: 'warning' },
  code_review: { label: 'Code Review', icon: EyeIcon, variant: 'success' },
}

interface StepCardProps {
  step: ImplementationStepResponse
  taskId: number
  onStepUpdated: () => void
}

const StepCard = memo(function StepCard({ step, taskId, onStepUpdated }: StepCardProps) {
  const [expanded, setExpanded] = useState(false)
  const [editingDetails, setEditingDetails] = useState(false)
  const [editedDetails, setEditedDetails] = useState(step.details)
  const [saving, setSaving] = useState(false)
  const [isSubAgentModalOpen, setIsSubAgentModalOpen] = useState(false)
  const [cancelling, setCancelling] = useState(false)
  const { addNotification } = useNotificationStore()

  const fetchMessages = useCallback(
    async () => {
      const r = await apiClient.getConversationMessages(step.conversation_id!)
      return { messages: r.messages, context_usage: r.context_usage }
    },
    [step.conversation_id]
  )

  const statusConfig = STEP_STATUS_CONFIG[step.status]
  const typeConfig = STEP_TYPE_CONFIG[step.type]

  const handleCancel = useCallback(async (e: React.MouseEvent) => {
    e.stopPropagation()
    if (!step.conversation_id || cancelling) return
    setCancelling(true)
    try {
      await apiClient.interruptConversation(step.conversation_id)
    } catch (error) {
      console.error('Failed to interrupt step:', error)
      addNotification({ type: 'system_error', message: 'Failed to cancel step' })
    } finally {
      setCancelling(false)
    }
  }, [step.conversation_id, cancelling, addNotification])

  const handleSaveDetails = useCallback(async () => {
    setSaving(true)
    try {
      await apiClient.updateImplementationStep(taskId, step.step_number, { details: editedDetails })
      setEditingDetails(false)
      onStepUpdated()
    } catch (error) {
      console.error('Failed to update step details:', error)
    } finally {
      setSaving(false)
    }
  }, [taskId, step.step_number, editedDetails, onStepUpdated])

  const handleStartEditing = useCallback(() => {
    setEditedDetails(step.details)
    setEditingDetails(true)
    setExpanded(true)
  }, [step.details])

  return (
    <div className={`border ${borderColors.default} rounded-lg`}>
      {/* Step Header */}
      <div
        className={`flex items-center gap-3 px-4 py-3 cursor-pointer ${hoverColors.subtle} transition-colors`}
        onClick={() => setExpanded(!expanded)}
      >
        {expanded ? (
          <ChevronDownIcon className="w-4 h-4 text-gray-400 flex-shrink-0" />
        ) : (
          <ChevronRightIcon className="w-4 h-4 text-gray-400 flex-shrink-0" />
        )}

        <statusConfig.icon className={`w-4 h-4 flex-shrink-0 ${statusConfig.iconClass}`} title={step.status} />

        <span className={`font-medium text-sm ${textColors.primary}`}>
          {step.step_number}. {step.title}
        </span>

        <div className="flex items-center gap-2 ml-auto flex-shrink-0">
          {step.status === 'running' && step.conversation_id != null && (
            <button
              type="button"
              onClick={handleCancel}
              disabled={cancelling}
              className="flex-shrink-0 flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium text-white bg-red-600 hover:bg-red-700 disabled:opacity-60 disabled:cursor-not-allowed transition-colors"
              title="Cancel step"
            >
              <StopIcon className="w-3 h-3" />
              {cancelling ? 'Cancelling…' : 'Cancel'}
            </button>
          )}
          <StepDuration step={step} />
          {step.conversation_id && (
            <button
              type="button"
              onClick={(e) => { e.stopPropagation(); setIsSubAgentModalOpen(true) }}
              className="flex-shrink-0 p-0.5 rounded text-blue-500 dark:text-blue-400 hover:bg-blue-100 dark:hover:bg-blue-900/40 transition-colors"
              title="View sub-agent conversation"
            >
              <ChatBubbleLeftRightIcon className="w-4 h-4" />
            </button>
          )}
          <div className="flex flex-col items-end gap-0.5">
            <StatusBadge variant={typeConfig.variant} size="sm">
              <typeConfig.icon className="w-3 h-3 mr-1" />
              {typeConfig.label}
            </StatusBadge>
            {step.model_display_name && (
              <span className="text-[10px] text-gray-500 dark:text-gray-500">{step.model_display_name}</span>
            )}
          </div>
        </div>
      </div>

      {/* Dependencies line */}
      {step.dependencies.length > 0 && (
        <div className="px-4 pb-2 -mt-1">
          <span className={`text-xs ${textColors.secondary}`}>
            Depends on: {step.dependencies.map(d => `Step ${d}`).join(', ')}
          </span>
        </div>
      )}

      {/* Expanded Content */}
      {expanded && (
        <div className="px-4 pb-4 border-t border-gray-100 dark:border-white/[0.08]/50 mt-1 pt-3">
          {/* Details */}
          <div className="relative">
            <h4 className={`text-xs font-semibold uppercase tracking-wide ${textColors.secondary} mb-2`}>Details</h4>
            {editingDetails ? (
              <div>
                <Textarea
                  value={editedDetails}
                  onChange={(e) => setEditedDetails(e.target.value)}
                  className="min-h-[120px] text-sm"
                />
                <div className="flex items-center gap-2 mt-2">
                  <Button onClick={handleSaveDetails} variant="primary" size="sm" loading={saving} icon={<CheckIcon className="w-4 h-4" />}>
                    Save
                  </Button>
                  <Button onClick={() => setEditingDetails(false)} variant="secondary" size="sm" icon={<XMarkIcon className="w-4 h-4" />}>
                    Cancel
                  </Button>
                </div>
              </div>
            ) : (
              <div className="relative group">
                <div className="prose prose-sm dark:prose-invert max-w-none">
                  <Markdown>{step.details}</Markdown>
                </div>
                <button
                  onClick={(e) => { e.stopPropagation(); handleStartEditing() }}
                  className={`absolute top-0 right-0 opacity-0 group-hover:opacity-100 flex items-center gap-1 px-2 py-1 rounded text-xs ${surfaces.raised} border ${borderColors.default} shadow-sm hover:bg-gray-50 dark:hover:bg-gray-700 transition-all ${textColors.muted}`}
                >
                  <PencilIcon className="w-3 h-3" />
                  Edit
                </button>
              </div>
            )}
          </div>

          {/* Outcome (for completed/failed/interrupted steps) */}
          {step.outcome && (
            <div className="mt-4">
              <h4 className={`text-xs font-semibold uppercase tracking-wide mb-2 ${
                step.status === 'failed' ? statusColors.error.text : step.status === 'interrupted' ? statusColors.warning.text : statusColors.success.text
              }`}>
                {step.status === 'failed' ? 'Error' : step.status === 'interrupted' ? 'Interrupted' : 'Outcome'}
              </h4>
              <div className={`p-3 rounded-md text-sm ${
                step.status === 'failed'
                  ? `${statusColors.error.bg} border ${statusColors.error.border}`
                  : step.status === 'interrupted'
                    ? `${statusColors.warning.bg} border ${statusColors.warning.border}`
                    : `${statusColors.success.bg} border ${statusColors.success.border}`
              }`}>
                <Markdown>{step.outcome}</Markdown>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Sub-agent conversation modal */}
      {step.conversation_id && (
        <SubAgentConversationModal
          isOpen={isSubAgentModalOpen}
          onClose={() => setIsSubAgentModalOpen(false)}
          fetchMessages={fetchMessages}
          title={step.title}
          conversationId={step.conversation_id ?? undefined}
        />
      )}
    </div>
  )
})

interface StructuredPlanViewProps {
  plan: ImplementationPlanResponse
  taskId: number
  taskStatus: TaskStatus
  onPlanUpdated: () => void
}

const StructuredPlanView = memo(function StructuredPlanView({ plan, taskId, taskStatus, onPlanUpdated }: StructuredPlanViewProps) {
  const [addingCodeReview, setAddingCodeReview] = useState(false)
  const { addNotification } = useNotificationStore()

  const showAddCodeReviewButton =
    taskStatus === TaskStatus.PLANNING &&
    plan.steps.length > 0 &&
    !plan.steps.some((s) => s.type === 'code_review')

  const handleAddCodeReview = useCallback(async () => {
    setAddingCodeReview(true)
    try {
      await apiClient.addImplementationStep(taskId, {
        title: 'Code review',
        type: 'code_review',
        details: 'Review the git diff for correctness, quality, and alignment with the spec.',
        dependencies: plan.steps.map((s) => s.step_number),
      })
      onPlanUpdated()
    } catch (error) {
      console.error('Failed to add code review step:', error)
      addNotification({ type: 'system_error', message: 'Failed to add code review step' })
    } finally {
      setAddingCodeReview(false)
    }
  }, [taskId, plan.steps, onPlanUpdated, addNotification])

  return (
    <div className="h-full flex flex-col overflow-y-auto space-y-4">
      {/* Plan Overview */}
      {plan.overview && (
        <div>
          <h3 className={`text-sm font-semibold ${textColors.primary} mb-2`}>Plan Overview</h3>
          <div className={`p-3 ${surfaces.sunken} rounded-lg border ${borderColors.default}`}>
            <Markdown>{plan.overview}</Markdown>
          </div>
        </div>
      )}

      {/* Implementation Steps */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h3 className={`text-sm font-semibold ${textColors.primary}`}>
            Implementation Steps
          </h3>
          <StatusBadge variant={plan.status === 'complete' ? 'success' : plan.status === 'failed' ? 'error' : plan.status === 'executing' ? 'info' : 'default'} size="sm">
            {plan.status}
          </StatusBadge>
        </div>

        <div className="space-y-2">
          {plan.steps.map((step) => (
            <StepCard
              key={step.id}
              step={step}
              taskId={taskId}
              onStepUpdated={onPlanUpdated}
            />
          ))}
          {plan.steps.length === 0 && (
            <p className={`${textColors.secondary} italic text-sm`}>No steps defined yet.</p>
          )}
        </div>

        {showAddCodeReviewButton && (
          <button
            type="button"
            onClick={handleAddCodeReview}
            disabled={addingCodeReview}
            className="mt-2 w-full border border-dashed border-gray-300 dark:border-white/[0.15] rounded-lg py-2 text-sm text-gray-500 dark:text-gray-400 hover:border-gray-400 dark:hover:border-white/[0.25] hover:text-gray-600 dark:hover:text-gray-300 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-1.5"
          >
            <span className="text-base leading-none">+</span>
            {addingCodeReview ? 'Adding...' : 'Add Code Review Step'}
          </button>
        )}
      </div>
    </div>
  )
})

interface PlanTabProps {
  taskId: number
  taskStatus: TaskStatus
  implementationPlan: ImplementationPlanResponse | null | undefined
  onPlanUpdated: () => void
  // Legacy props for Document-based plans
  implementationPlanDoc?: DocumentResponse | null | undefined
}

export function PlanTab({ taskId, taskStatus, implementationPlan, onPlanUpdated, implementationPlanDoc }: PlanTabProps) {
  // Structured plan takes priority
  if (implementationPlan) {
    return (
      <StructuredPlanView
        plan={implementationPlan}
        taskId={taskId}
        taskStatus={taskStatus}
        onPlanUpdated={onPlanUpdated}
      />
    )
  }

  // Legacy Document-based plan (read-only)
  if (implementationPlanDoc !== undefined) {
    return (
      <MarkdownDocumentEditor
        content={implementationPlanDoc?.content}
        placeholder="Enter implementation plan in Markdown format..."
        emptyText="No implementation plan provided."
      />
    )
  }

  return (
    <p className={`${textColors.secondary} italic`}>No implementation plan available.</p>
  )
}
