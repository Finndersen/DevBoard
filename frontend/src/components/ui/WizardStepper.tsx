import { CheckIcon } from '@heroicons/react/24/solid'

export interface WizardStep {
  id: string
  label: string
  description?: string
}

interface WizardStepperProps {
  steps: WizardStep[]
  currentStep: number
  onStepClick?: (stepIndex: number) => void
  allowClickBack?: boolean
}

export default function WizardStepper({
  steps,
  currentStep,
  onStepClick,
  allowClickBack = true,
}: WizardStepperProps) {
  const handleStepClick = (index: number) => {
    if (allowClickBack && index < currentStep && onStepClick) {
      onStepClick(index)
    }
  }

  return (
    <nav aria-label="Progress" className="mb-6">
      <ol className="flex items-center">
        {steps.map((step, index) => {
          const isCompleted = index < currentStep
          const isCurrent = index === currentStep
          const isPast = index < currentStep
          const isClickable = allowClickBack && isPast && onStepClick

          return (
            <li
              key={step.id}
              className={`relative ${index !== steps.length - 1 ? 'flex-1' : ''}`}
            >
              <div className="flex items-center">
                <button
                  type="button"
                  onClick={() => handleStepClick(index)}
                  disabled={!isClickable}
                  className={`
                    relative flex h-8 w-8 items-center justify-center rounded-full
                    ${isCompleted
                      ? 'bg-blue-600 hover:bg-blue-700'
                      : isCurrent
                        ? 'border-2 border-blue-600 bg-white dark:bg-gray-800'
                        : 'border-2 border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800'
                    }
                    ${isClickable ? 'cursor-pointer' : 'cursor-default'}
                    transition-colors
                  `}
                  aria-current={isCurrent ? 'step' : undefined}
                >
                  {isCompleted ? (
                    <CheckIcon className="h-4 w-4 text-white" />
                  ) : (
                    <span
                      className={`text-sm font-medium ${
                        isCurrent
                          ? 'text-blue-600'
                          : 'text-gray-500 dark:text-gray-400'
                      }`}
                    >
                      {index + 1}
                    </span>
                  )}
                </button>

                {/* Connector line */}
                {index !== steps.length - 1 && (
                  <div
                    className={`ml-2 h-0.5 flex-1 ${
                      isCompleted ? 'bg-blue-600' : 'bg-gray-300 dark:bg-gray-600'
                    }`}
                  />
                )}
              </div>

              {/* Step label (shown below the circle on smaller screens, or could be hidden) */}
              <div className="mt-2 min-w-0">
                <span
                  className={`text-xs font-medium ${
                    isCurrent
                      ? 'text-blue-600'
                      : isCompleted
                        ? 'text-gray-900 dark:text-gray-100'
                        : 'text-gray-500 dark:text-gray-400'
                  }`}
                >
                  {step.label}
                </span>
              </div>
            </li>
          )
        })}
      </ol>
    </nav>
  )
}
