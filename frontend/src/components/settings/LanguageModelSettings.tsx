import { useState, useEffect } from 'react'
import { PlusIcon, PencilIcon, TrashIcon, CpuChipIcon } from '@heroicons/react/24/outline'
import { Card, Button, Modal, ConfirmDialog } from '../ui'
import { LanguageModelForm } from './LanguageModelForm'
import { apiClient } from '../../lib/api'
import type { LanguageModelRecord, CreateLanguageModelRequest, UpdateLanguageModelRequest } from '../../lib/api'
import { textColors } from '../../styles/designSystem'

const PROVIDER_LABELS: Record<string, string> = {
  anthropic: 'Anthropic',
  openai: 'OpenAI',
  google: 'Google',
}

const PROVIDER_BADGE_COLORS: Record<string, string> = {
  anthropic: 'bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-300',
  openai: 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300',
  google: 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-300',
}

const TYPE_LABELS: Record<string, string> = {
  fast: 'Fast',
  standard: 'Standard',
  advanced: 'Advanced',
}

const TYPE_BADGE_COLORS: Record<string, string> = {
  fast: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-300',
  standard: 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-300',
  advanced: 'bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-300',
}

function formatContextWindow(tokens: number | null): string {
  if (tokens == null) return '—'
  if (tokens >= 1_000_000) return `${(tokens / 1_000_000).toLocaleString(undefined, { maximumFractionDigits: 1 })}M`
  if (tokens >= 1_000) return `${(tokens / 1_000).toLocaleString(undefined, { maximumFractionDigits: 0 })}K`
  return tokens.toLocaleString()
}

function compareModels(a: LanguageModelRecord, b: LanguageModelRecord): number {
  return a.provider.localeCompare(b.provider) || a.name.localeCompare(b.name)
}

export function LanguageModelSettings() {
  const [models, setModels] = useState<LanguageModelRecord[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [isFormOpen, setIsFormOpen] = useState(false)
  const [editingModel, setEditingModel] = useState<LanguageModelRecord | null>(null)
  const [isSaving, setIsSaving] = useState(false)

  const [deleteConfirmModel, setDeleteConfirmModel] = useState<LanguageModelRecord | null>(null)
  const [isDeleting, setIsDeleting] = useState(false)

  useEffect(() => {
    let stale = false
    setLoading(true)
    setError(null)
    apiClient.getLanguageModels()
      .then(data => { if (!stale) setModels(data.sort(compareModels)) })
      .catch(err => {
        if (!stale) {
          console.error('Failed to load language models:', err)
          setError('Failed to load language models')
        }
      })
      .finally(() => { if (!stale) setLoading(false) })
    return () => { stale = true }
  }, [])

  const handleCreate = () => {
    setEditingModel(null)
    setIsFormOpen(true)
  }

  const handleEdit = (model: LanguageModelRecord) => {
    setEditingModel(model)
    setIsFormOpen(true)
  }

  const handleDelete = (model: LanguageModelRecord) => {
    setDeleteConfirmModel(model)
  }

  const confirmDelete = async () => {
    if (!deleteConfirmModel) return
    try {
      setIsDeleting(true)
      await apiClient.deleteLanguageModel(deleteConfirmModel.id)
      setModels(prev => prev.filter(m => m.id !== deleteConfirmModel.id))
      setDeleteConfirmModel(null)
    } catch (err) {
      console.error('Failed to delete language model:', err)
      setError('Failed to delete language model')
    } finally {
      setIsDeleting(false)
    }
  }

  const handleFormSubmit = async (data: CreateLanguageModelRequest | UpdateLanguageModelRequest) => {
    try {
      setIsSaving(true)
      if (editingModel) {
        const updated = await apiClient.updateLanguageModel(editingModel.id, data as UpdateLanguageModelRequest)
        setModels(prev => prev.map(m => m.id === updated.id ? updated : m))
      } else {
        const created = await apiClient.createLanguageModel(data as CreateLanguageModelRequest)
        setModels(prev => [...prev, created].sort(compareModels))
      }
      setIsFormOpen(false)
      setEditingModel(null)
    } catch (err: unknown) {
      if (err instanceof Error && err.message.includes('409')) {
        setError('A model with this provider and name already exists.')
      } else {
        console.error('Failed to save language model:', err)
        throw err
      }
    } finally {
      setIsSaving(false)
    }
  }

  const handleFormClose = () => {
    setIsFormOpen(false)
    setEditingModel(null)
  }

  return (
    <>
      <Card className="p-6">
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center space-x-2">
            <CpuChipIcon className="w-5 h-5 text-gray-400" />
            <h3 className={`text-lg font-medium ${textColors.primary}`}>Language Models</h3>
          </div>
          <Button variant="primary" size="sm" onClick={handleCreate}>
            <PlusIcon className="w-4 h-4 mr-1" />
            Add Model
          </Button>
        </div>

        <p className={`text-sm ${textColors.secondary} mb-6`}>
          Manage the language models available for use by AI agents. Changes take effect for new conversations.
        </p>

        {error && (
          <div className="mb-4 p-3 bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300 rounded-md text-sm">
            {error}
          </div>
        )}

        {loading ? (
          <div className="animate-pulse space-y-3">
            <div className="h-12 bg-gray-200 dark:bg-gray-700 rounded"></div>
            <div className="h-12 bg-gray-200 dark:bg-gray-700 rounded"></div>
            <div className="h-12 bg-gray-200 dark:bg-gray-700 rounded"></div>
          </div>
        ) : models.length === 0 ? (
          <div className="text-center py-8">
            <CpuChipIcon className="mx-auto h-12 w-12 text-gray-400" />
            <h4 className="mt-4 text-sm font-medium text-gray-900 dark:text-white">No language models</h4>
            <p className="mt-2 text-sm text-gray-500 dark:text-gray-400">
              Add a language model to make it available for AI agents.
            </p>
            <Button variant="primary" size="sm" className="mt-4" onClick={handleCreate}>
              <PlusIcon className="w-4 h-4 mr-1" />
              Add Model
            </Button>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200 dark:border-gray-700">
                  <th className={`text-left py-3 pr-4 font-medium ${textColors.secondary}`}>Name</th>
                  <th className={`text-left py-3 pr-4 font-medium ${textColors.secondary}`}>Provider</th>
                  <th className={`text-left py-3 pr-4 font-medium ${textColors.secondary}`}>Type</th>
                  <th className={`text-left py-3 pr-4 font-medium ${textColors.secondary}`}>Full Name</th>
                  <th className={`text-left py-3 pr-4 font-medium ${textColors.secondary}`}>Context</th>
                  <th className="py-3 w-20"></th>
                </tr>
              </thead>
              <tbody>
                {models.map(model => (
                  <tr key={model.id} className="border-b border-gray-100 dark:border-gray-800 hover:bg-gray-50 dark:hover:bg-gray-800/50">
                    <td className={`py-3 pr-4 font-medium ${textColors.primary}`}>{model.name}</td>
                    <td className="py-3 pr-4">
                      <span className={`px-2 py-0.5 text-xs rounded-full ${PROVIDER_BADGE_COLORS[model.provider] ?? 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300'}`}>
                        {PROVIDER_LABELS[model.provider] ?? model.provider}
                      </span>
                    </td>
                    <td className="py-3 pr-4">
                      <span className={`px-2 py-0.5 text-xs rounded-full ${TYPE_BADGE_COLORS[model.model_type] ?? 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300'}`}>
                        {TYPE_LABELS[model.model_type] ?? model.model_type}
                      </span>
                    </td>
                    <td className={`py-3 pr-4 ${textColors.secondary}`}>{model.full_name ?? '—'}</td>
                    <td className={`py-3 pr-4 ${textColors.secondary}`}>{formatContextWindow(model.context_window)}</td>
                    <td className="py-3">
                      <div className="flex items-center justify-end space-x-1">
                        <button
                          onClick={() => handleEdit(model)}
                          className="p-1.5 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors"
                          title="Edit model"
                        >
                          <PencilIcon className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => handleDelete(model)}
                          className="p-1.5 text-gray-400 hover:text-red-600 dark:hover:text-red-400 transition-colors"
                          title="Delete model"
                        >
                          <TrashIcon className="w-4 h-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <Modal
        isOpen={isFormOpen}
        onClose={handleFormClose}
        title={editingModel ? 'Edit Language Model' : 'Add Language Model'}
        maxWidth="lg"
      >
        <LanguageModelForm
          model={editingModel}
          onSubmit={handleFormSubmit}
          onCancel={handleFormClose}
          isSaving={isSaving}
        />
      </Modal>

      <ConfirmDialog
        isOpen={!!deleteConfirmModel}
        onClose={() => setDeleteConfirmModel(null)}
        onConfirm={confirmDelete}
        title="Delete Language Model"
        message={`Are you sure you want to delete "${deleteConfirmModel?.name}"? Existing conversations referencing this model will retain the model ID but won't be able to use it for new requests.`}
        confirmText="Delete"
        variant="danger"
        loading={isDeleting}
      />
    </>
  )
}
