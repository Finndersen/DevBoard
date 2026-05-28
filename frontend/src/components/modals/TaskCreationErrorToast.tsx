import { XMarkIcon, ExclamationCircleIcon } from '@heroicons/react/24/outline'
import { useUIStore } from '../../stores/uiStore'
import { surfaces, statusColors, textColors } from '../../styles/designSystem'
import Button from '../ui/Button'

export default function TaskCreationErrorToast() {
  const modalDrafts = useUIStore(s => s.modalDrafts)
  const openExistingDraft = useUIStore(s => s.openExistingDraft)
  const removeModalDraft = useUIStore(s => s.removeModalDraft)

  const errorDrafts = Object.entries(modalDrafts).filter(
    ([, draft]) => draft.creationError != null && draft.creationError !== ''
  )

  if (errorDrafts.length === 0) return null

  return (
    <div className="fixed bottom-6 right-6 z-50 flex flex-col gap-2">
      {errorDrafts.map(([draftId, draft]) => (
        <div
          key={draftId}
          role="alert"
          className={`${surfaces.raised} border ${statusColors.error.border} rounded-lg shadow-lg p-4 w-80`}
        >
          <div className="flex items-start gap-3">
            <div className={`${statusColors.error.icon} rounded-full p-1 shrink-0`}>
              <ExclamationCircleIcon className={`w-4 h-4 ${statusColors.error.text}`} />
            </div>
            <div className="flex-1 min-w-0">
              <p className={`text-sm font-semibold ${textColors.primary}`}>Task creation failed</p>
              <p className={`text-xs mt-0.5 ${textColors.secondary} line-clamp-2`}>{draft.creationError}</p>
            </div>
            <button
              onClick={() => removeModalDraft(draftId)}
              className={`shrink-0 ${textColors.muted} hover:text-gray-700 dark:hover:text-gray-300`}
              aria-label="Dismiss error"
            >
              <XMarkIcon className="w-4 h-4" />
            </button>
          </div>
          <div className="flex gap-2 mt-3">
            <Button
              variant="primary"
              size="sm"
              onClick={() => openExistingDraft(draftId)}
              className="flex-1"
            >
              Retry
            </Button>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => removeModalDraft(draftId)}
              className="flex-1"
            >
              Dismiss
            </Button>
          </div>
        </div>
      ))}
    </div>
  )
}
