import { useState, useEffect } from 'react'
import { Button, Input } from '../ui'
import type { LanguageModelRecord, CreateLanguageModelRequest, UpdateLanguageModelRequest, ModelProvider, ModelType } from '../../lib/api'

interface LanguageModelFormProps {
  model: LanguageModelRecord | null
  onSubmit: (data: CreateLanguageModelRequest | UpdateLanguageModelRequest) => Promise<void>
  onCancel: () => void
  isSaving: boolean
}

export function LanguageModelForm({ model, onSubmit, onCancel, isSaving }: LanguageModelFormProps) {
  const [provider, setProvider] = useState<ModelProvider>('anthropic')
  const [name, setName] = useState('')
  const [modelType, setModelType] = useState<ModelType>('standard')
  const [fullName, setFullName] = useState('')
  const [bedrockId, setBedrockId] = useState('')
  const [contextWindow, setContextWindow] = useState('')
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (model) {
      setProvider(model.provider)
      setName(model.name)
      setModelType(model.model_type)
      setFullName(model.full_name ?? '')
      setBedrockId(model.bedrock_id ?? '')
      setContextWindow(model.context_window != null ? String(model.context_window) : '')
    } else {
      setProvider('anthropic')
      setName('')
      setModelType('standard')
      setFullName('')
      setBedrockId('')
      setContextWindow('')
    }
    setError(null)
  }, [model])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)

    if (!name.trim()) {
      setError('Name is required')
      return
    }

    const parsedContextWindow = contextWindow.trim() ? parseInt(contextWindow.trim(), 10) : null
    const data: CreateLanguageModelRequest | UpdateLanguageModelRequest = {
      provider,
      name: name.trim(),
      model_type: modelType,
      full_name: fullName.trim() || null,
      bedrock_id: bedrockId.trim() || null,
      context_window: parsedContextWindow,
    }

    try {
      await onSubmit(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save model')
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      {error && (
        <div className="p-3 bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300 rounded-md text-sm">
          {error}
        </div>
      )}

      <div>
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
          Provider <span className="text-red-500">*</span>
        </label>
        <select
          value={provider}
          onChange={(e) => setProvider(e.target.value as ModelProvider)}
          className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 bg-white text-gray-900 dark:bg-gray-700 dark:text-white"
        >
          <option value="anthropic">Anthropic</option>
          <option value="openai">OpenAI</option>
          <option value="google">Google</option>
        </select>
      </div>

      <Input
        label="Name"
        value={name}
        onChange={(e) => setName(e.target.value)}
        placeholder="e.g., claude-sonnet-4-5"
        required
        helpText="Model identifier used in the provider's API"
      />

      <div>
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
          Type <span className="text-red-500">*</span>
        </label>
        <select
          value={modelType}
          onChange={(e) => setModelType(e.target.value as ModelType)}
          className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 bg-white text-gray-900 dark:bg-gray-700 dark:text-white"
        >
          <option value="fast">Fast — optimized for speed</option>
          <option value="standard">Standard — balanced performance</option>
          <option value="advanced">Advanced — highest capability</option>
        </select>
      </div>

      <Input
        label="Full Name"
        value={fullName}
        onChange={(e) => setFullName(e.target.value)}
        placeholder="e.g., claude-sonnet-4-5-20250929"
        helpText="Optional full model identifier for external engines"
      />

      <Input
        label="Bedrock ID"
        value={bedrockId}
        onChange={(e) => setBedrockId(e.target.value)}
        placeholder="e.g., eu.anthropic.claude-sonnet-4-5-20250929-v1:0"
        helpText="Optional AWS Bedrock inference profile ID"
      />

      <Input
        label="Context Window"
        value={contextWindow}
        onChange={(e) => setContextWindow(e.target.value)}
        placeholder="e.g., 200000"
        helpText="Maximum context window size in tokens"
        type="number"
      />

      <div className="flex justify-end space-x-3 pt-4 border-t border-gray-200 dark:border-gray-700">
        <Button type="button" variant="secondary" onClick={onCancel} disabled={isSaving}>
          Cancel
        </Button>
        <Button type="submit" variant="primary" loading={isSaving}>
          {model ? 'Save Changes' : 'Add Model'}
        </Button>
      </div>
    </form>
  )
}
