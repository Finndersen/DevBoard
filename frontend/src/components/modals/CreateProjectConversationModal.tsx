import { useState, useCallback, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Modal, Button, Textarea } from '../ui'
import Alert from '../ui/Alert'
import { apiClient } from '../../lib/api'
import { useProjects } from '../../hooks'
import { useUIStore } from '../../stores/uiStore'
import { useConversationStreamStore } from '../../stores/conversationStreamStore'

interface CreateProjectConversationModalProps {
  isOpen: boolean
  onClose: () => void
  draftId?: string
}

interface FormData {
  projectId: string
  prompt: string
}

export default function CreateProjectConversationModal({
  isOpen,
  onClose,
  draftId,
}: CreateProjectConversationModalProps) {
  const navigate = useNavigate()
  const { data: projects } = useProjects()
  const { saveModalDraft, removeModalDraft } = useUIStore()
  const { seedInitialMessage } = useConversationStreamStore()

  const [formData, setFormData] = useState<FormData>({
    projectId: '',
    prompt: '',
  })
  const [isCreating, setIsCreating] = useState(false)
  const [createError, setCreateError] = useState<string | null>(null)

  // Initialize form from draft or reset on open/close
  useEffect(() => {
    if (isOpen) {
      if (draftId) {
        // Restore from draft
        const draft = useUIStore.getState().modalDrafts[draftId]
        if (draft && draft.type === 'project_conversation') {
          const data = draft.formData as Partial<FormData>
          setFormData({
            projectId: data.projectId || '',
            prompt: data.prompt || '',
          })
        }
      } else {
        // Fresh modal
        setFormData({
          projectId: '',
          prompt: '',
        })
      }
      setIsCreating(false)
      setCreateError(null)
    }
  }, [isOpen, draftId])

  const handleProjectChange = useCallback((e: React.ChangeEvent<HTMLSelectElement>) => {
    setFormData(prev => ({ ...prev, projectId: e.target.value }))
  }, [])

  const handlePromptChange = useCallback((e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setFormData(prev => ({ ...prev, prompt: e.target.value }))
  }, [])

  const handleMinimize = useCallback(() => {
    if (draftId) {
      // Update existing draft
      const draft = {
        type: 'project_conversation' as const,
        formData,
        previewLabel: formData.projectId
          ? (projects?.find(p => p.id === formData.projectId)?.name || formData.projectId)
          : 'Project Conversation',
        createdAt: Date.now(),
      }
      saveModalDraft(draftId, draft)
    } else {
      // Create new draft
      const draft = {
        type: 'project_conversation' as const,
        formData,
        previewLabel: formData.projectId
          ? (projects?.find(p => p.id === formData.projectId)?.name || formData.projectId)
          : 'Project Conversation',
        createdAt: Date.now(),
      }
      const newDraftId = `draft-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`
      saveModalDraft(newDraftId, draft)
    }
    onClose()
  }, [draftId, formData, saveModalDraft, onClose, projects])

  const handleClose = useCallback(() => {
    if (draftId) {
      removeModalDraft(draftId)
    }
    onClose()
  }, [draftId, removeModalDraft, onClose])

  const handleCreateConversation = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault()
      const trimmedPrompt = formData.prompt.trim()
      if (!formData.projectId || !trimmedPrompt) return

      setIsCreating(true)
      setCreateError(null)

      try {
        const conversation = await apiClient.createProjectConversation(formData.projectId, {
          initial_message: trimmedPrompt,
        })

        // Seed initial user message into stream store
        seedInitialMessage(conversation.id, trimmedPrompt)

        // Remove draft if it exists
        if (draftId) {
          removeModalDraft(draftId)
        }

        // Reset form and close
        setFormData({
          projectId: '',
          prompt: '',
        })
        onClose()

        // Navigate to project view with conversation active
        navigate(`/projects/${formData.projectId}?conversation=${conversation.id}`)
      } catch (error) {
        console.error('Failed to create project conversation:', error)
        setCreateError(
          error instanceof Error ? error.message : 'Failed to create project conversation'
        )
      } finally {
        setIsCreating(false)
      }
    },
    [formData, draftId, removeModalDraft, onClose, navigate, seedInitialMessage]
  )

  return (
    <Modal
      isOpen={isOpen}
      onClose={handleClose}
      title={
        <div className="flex items-center justify-between">
          <span>New Project Conversation</span>
          <button
            type="button"
            onClick={handleMinimize}
            className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors ml-2"
            title="Minimize to draft"
            aria-label="Minimize to draft"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20 12H4" />
            </svg>
          </button>
        </div>
      }
      maxWidth="lg"
    >
      <form onSubmit={handleCreateConversation} className="space-y-4">
        <div>
          <label htmlFor="project-select" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
            Project
          </label>
          <select
            id="project-select"
            value={formData.projectId}
            onChange={handleProjectChange}
            className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 bg-white dark:bg-white/[0.06] text-gray-900 dark:text-white"
            required
          >
            <option value="">Select a project...</option>
            {projects?.map(p => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </div>

        <Textarea
          label="Initial Prompt"
          value={formData.prompt}
          onChange={handlePromptChange}
          placeholder="Describe what you want to discuss about this project..."
          rows={8}
          required
        />

        {createError && <Alert variant="error">{createError}</Alert>}

        <div className="flex justify-end space-x-3 pt-4">
          <Button
            type="button"
            variant="secondary"
            onClick={handleClose}
            disabled={isCreating}
          >
            Cancel
          </Button>
          <Button
            type="submit"
            variant="primary"
            loading={isCreating}
            disabled={
              !formData.projectId ||
              !formData.prompt.trim() ||
              isCreating
            }
          >
            Create Conversation
          </Button>
        </div>
      </form>
    </Modal>
  )
}
