import {
  DocumentTextIcon,
  NumberedListIcon,
  CodeBracketIcon,
  ArrowPathIcon,
  XCircleIcon
} from '@heroicons/react/24/outline'
import { CheckCircleIcon as CheckCircleSolidIcon } from '@heroicons/react/24/solid'
import { TaskStatus } from '../../lib/api'
import { GitHubIcon } from '../icons/GitHubIcon'
import { StatusIndicator, ReviewBadge } from '../github/PRStatusComponents'
import { borderColors } from '../../styles/designSystem'

export interface TaskArtifactStepperProps {
  activeStep: 'specification' | 'plan' | 'changes' | 'pullrequest' | 'summary'
  onStepClick: (step: string) => void
  taskStatus: TaskStatus
  hasSpecification: boolean
  hasPlan: boolean
  planStatus?: 'pending' | 'executing' | 'complete' | 'failed'
  hasChanges: boolean
  changeCount?: number
  hasPR: boolean
  prStatus?: {
    mergeable_state: string
    ci_status: string
    merged: boolean
    review_decision?: string
  }
  hasSummary: boolean
}

type StepState = 'complete' | 'active' | 'pending'

interface Step {
  id: string
  name: string
  icon: React.ComponentType<{ className?: string }>
  state: StepState
  isClickable: boolean
  badge?: React.ReactNode
  statusIcon?: React.ReactNode
}

export function TaskArtifactStepper({
  activeStep,
  onStepClick,
  taskStatus,
  hasSpecification,
  hasPlan,
  planStatus,
  hasChanges,
  changeCount,
  hasPR,
  prStatus,
  hasSummary,
}: TaskArtifactStepperProps) {

  // Normalize status to lowercase for comparison with TaskStatus enum values
  const status = taskStatus.toLowerCase() as TaskStatus

  const getStepState = (stepId: string): StepState => {
    switch (stepId) {
      case 'specification':
        // Complete once a plan exists (plan implies spec is done), or past planning
        if (hasSpecification && (hasPlan || status !== TaskStatus.PLANNING)) return 'complete'
        if (status === TaskStatus.PLANNING) return 'active'
        return 'pending'

      case 'plan':
        // Complete when past implementing, or all implementation steps finished
        if (hasPlan && [TaskStatus.PR_OPEN, TaskStatus.COMPLETE].includes(status)) return 'complete'
        if (hasPlan && planStatus === 'complete') return 'complete'
        // Active during planning (once plan exists) and throughout implementation
        if (hasPlan && [TaskStatus.PLANNING, TaskStatus.IMPLEMENTING].includes(status)) return 'active'
        return 'pending'

      case 'changes':
        if ([TaskStatus.PR_OPEN, TaskStatus.COMPLETE].includes(status)) return 'complete'
        if (status === TaskStatus.IMPLEMENTING) return 'active'
        return 'pending'

      case 'pullrequest':
        if (prStatus?.merged) return 'complete'
        if (status === TaskStatus.PR_OPEN) return 'active'
        return 'pending'

      default:
        return 'pending'
    }
  }

  const getPlanStatusIcon = () => {
    switch (planStatus) {
      case 'executing':
        return <ArrowPathIcon className="w-3 h-3 animate-spin text-blue-500" />
      case 'failed':
        return <XCircleIcon className="w-3 h-3 text-red-500" />
      default:
        return null
    }
  }

  const getChangesBadge = () => {
    if (changeCount === undefined || changeCount <= 0) return null

    return (
      <span className="bg-blue-900/30 text-blue-400 text-xs px-1.5 py-0.5 rounded-full">
        {changeCount}
      </span>
    )
  }

  const getPRBadges = () => {
    if (!prStatus) return null

    return (
      <div className="flex items-center gap-1">
        <StatusIndicator
          mergeableState={prStatus.mergeable_state}
          ciStatus={prStatus.ci_status}
        />
        <ReviewBadge decision={prStatus.review_decision} />
      </div>
    )
  }

  const allSteps: Step[] = [
    {
      id: 'specification',
      name: 'Spec',
      icon: DocumentTextIcon,
      state: getStepState('specification'),
      isClickable: true,
      badge: undefined,
      statusIcon: undefined,
    },
    {
      id: 'plan',
      name: 'Plan',
      icon: NumberedListIcon,
      state: getStepState('plan'),
      isClickable: hasPlan,
      badge: undefined,
      statusIcon: getPlanStatusIcon(),
    },
    {
      id: 'changes',
      name: 'Changes',
      icon: CodeBracketIcon,
      state: getStepState('changes'),
      isClickable: hasChanges,
      badge: getChangesBadge(),
      statusIcon: undefined,
    },
    {
      id: 'pullrequest',
      name: 'PR',
      icon: GitHubIcon,
      state: getStepState('pullrequest'),
      isClickable: hasPR,
      badge: getPRBadges(),
      statusIcon: undefined,
    },
  ]

  // Only show steps that are complete or active (not future/pending)
  const steps = allSteps.filter(s => s.state !== 'pending')

  const isSelected = (step: Step) => step.id === activeStep

  const getStepClasses = (step: Step) => {
    const baseClasses = "flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-sm font-medium transition-colors"

    if (isSelected(step)) {
      return `${baseClasses} bg-blue-900/30 border border-blue-500 text-blue-400 cursor-pointer`
    }

    // Not selected — subtle styling for both complete and active
    return `${baseClasses} border border-transparent text-gray-400 ${step.isClickable ? 'cursor-pointer hover:text-gray-200 hover:bg-gray-800/50' : 'cursor-default'}`
  }

  const getStepStatusIndicator = (step: Step) => {
    if (step.state === 'complete') {
      return <CheckCircleSolidIcon className={`w-4 h-4 flex-shrink-0 ${isSelected(step) ? 'text-green-400' : 'text-green-600'}`} />
    }
    // Active (in-progress) — outlined circle
    return <div className={`w-3.5 h-3.5 rounded-full flex-shrink-0 border-2 ${isSelected(step) ? 'border-blue-400' : 'border-gray-500'}`} />
  }

  const handleStepClick = (step: Step) => {
    if (!step.isClickable || step.state === 'pending') return
    onStepClick(step.id)
  }

  return (
    <div className={`border-b ${borderColors.default} px-4 py-2`}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1">
          {steps.map((step, index) => {
            const nextStep = steps[index + 1]
            const StepIcon = step.icon

            return (
              <div key={step.id} className="flex items-center">
                <button
                  className={getStepClasses(step)}
                  onClick={() => handleStepClick(step)}
                  disabled={!step.isClickable || step.state === 'pending'}
                  title={!step.isClickable ? `${step.name} not available yet` : undefined}
                >
                  {getStepStatusIndicator(step)}
                  <StepIcon className="w-4 h-4 flex-shrink-0" />
                  <span className="whitespace-nowrap">{step.name}</span>

                  {step.statusIcon && (
                    <div className="ml-0.5 flex items-center">
                      {step.statusIcon}
                    </div>
                  )}

                  {step.badge && (
                    <div className="ml-0.5">
                      {step.badge}
                    </div>
                  )}
                </button>

                {nextStep && (
                  <span className="text-sm text-gray-600 mx-0.5">→</span>
                )}
              </div>
            )
          })}
        </div>

        {hasSummary && (
          <button
            className={`text-sm ${activeStep === 'summary' ? 'text-blue-400' : 'text-gray-500 hover:text-gray-300'} transition-colors`}
            onClick={() => onStepClick('summary')}
          >
            Summary
          </button>
        )}
      </div>
    </div>
  )
}
