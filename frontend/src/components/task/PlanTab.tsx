import { useState, useCallback } from 'react'
import type { ComponentType } from 'react'
import { CheckIcon, XMarkIcon, PencilIcon, ChevronDownIcon, ChevronRightIcon, ClockIcon, ArrowPathIcon, CheckCircleIcon, XCircleIcon, MinusCircleIcon, CodeBracketIcon, DocumentTextIcon, ClipboardDocumentCheckIcon, EyeIcon } from '@heroicons/react/24/outline'
import { useEditableField } from '../../hooks/useEditableField'
import { MarkdownDocumentEditor } from '../MarkdownDocumentEditor'
import { Button, Markdown, StatusBadge, Textarea } from '../ui'
import { textColors } from '../../styles/designSystem'
import { apiClient } from '../../lib/api'
import type { DocumentResponse, ImplementationPlanResponse, ImplementationStepResponse, ImplementationStepStatus, ImplementationStepType } from '../../lib/api'

const STEP_STATUS_CONFIG: Record<ImplementationStepStatus, { icon: ComponentType<{ className?: string }>; iconClass: string; variant: 'default' | 'success' | 'warning' | 'error' | 'info' }> = {
  pending: { icon: ClockIcon, iconClass: 'text-gray-400', variant: 'default' },
  running: { icon: ArrowPathIcon, iconClass: 'text-blue-500 animate-spin', variant: 'info' },
  complete: { icon: CheckCircleIcon, iconClass: 'text-green-500', variant: 'success' },
  failed: { icon: XCircleIcon, iconClass: 'text-red-500', variant: 'error' },
  skipped: { icon: MinusCircleIcon, iconClass: 'text-gray-400', variant: 'warning' },
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

function StepCard({ step, taskId, onStepUpdated }: StepCardProps) {
  const [expanded, setExpanded] = useState(false)
  const [editingDetails, setEditingDetails] = useState(false)
  const [editedDetails, setEditedDetails] = useState(step.details)
  const [saving, setSaving] = useState(false)

  const statusConfig = STEP_STATUS_CONFIG[step.status]
  const typeConfig = STEP_TYPE_CONFIG[step.type]

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
    <div className="border border-gray-200 dark:border-gray-700 rounded-lg">
      {/* Step Header */}
      <div
        className="flex items-center gap-3 px-4 py-3 cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors"
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
          <StatusBadge variant={typeConfig.variant} size="sm">
            <typeConfig.icon className="w-3 h-3 mr-1" />
            {typeConfig.label}
          </StatusBadge>
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
        <div className="px-4 pb-4 border-t border-gray-100 dark:border-gray-700/50 mt-1 pt-3">
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
                  className="absolute top-0 right-0 opacity-0 group-hover:opacity-100 flex items-center gap-1 px-2 py-1 rounded text-xs bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 shadow-sm hover:bg-gray-50 dark:hover:bg-gray-750 transition-all text-gray-500 dark:text-gray-400"
                >
                  <PencilIcon className="w-3 h-3" />
                  Edit
                </button>
              </div>
            )}
          </div>

          {/* Outcome (for completed/failed steps) */}
          {step.outcome && (
            <div className="mt-4">
              <h4 className={`text-xs font-semibold uppercase tracking-wide mb-2 ${
                step.status === 'failed' ? 'text-red-500' : 'text-green-600 dark:text-green-400'
              }`}>
                {step.status === 'failed' ? 'Error' : 'Outcome'}
              </h4>
              <div className={`p-3 rounded-md text-sm ${
                step.status === 'failed'
                  ? 'bg-red-50 dark:bg-red-900/10 border border-red-200 dark:border-red-800/30'
                  : 'bg-green-50 dark:bg-green-900/10 border border-green-200 dark:border-green-800/30'
              }`}>
                <Markdown>{step.outcome}</Markdown>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

interface StructuredPlanViewProps {
  plan: ImplementationPlanResponse
  taskId: number
  onPlanUpdated: () => void
}

function StructuredPlanView({ plan, taskId, onPlanUpdated }: StructuredPlanViewProps) {
  return (
    <div className="h-full flex flex-col overflow-y-auto space-y-4">
      {/* Plan Overview */}
      {plan.overview && (
        <div>
          <h3 className={`text-sm font-semibold ${textColors.primary} mb-2`}>Plan Overview</h3>
          <div className="p-3 bg-gray-50 dark:bg-gray-800/50 rounded-lg border border-gray-200 dark:border-gray-700">
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
      </div>
    </div>
  )
}

interface PlanTabProps {
  taskId: number
  implementationPlan: ImplementationPlanResponse | null | undefined
  onPlanUpdated: () => void
  // Legacy props for Document-based plans
  implementationPlanDoc?: DocumentResponse | null | undefined
  planField?: ReturnType<typeof useEditableField<string>>
}

export function PlanTab({ taskId, implementationPlan, onPlanUpdated, implementationPlanDoc, planField }: PlanTabProps) {
  // Structured plan takes priority
  if (implementationPlan) {
    return (
      <StructuredPlanView
        plan={implementationPlan}
        taskId={taskId}
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
