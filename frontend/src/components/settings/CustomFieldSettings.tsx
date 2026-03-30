import { useState, useEffect } from 'react'
import { PlusIcon, PencilIcon, TrashIcon, TagIcon } from '@heroicons/react/24/outline'
import { Card, Button, Modal, ConfirmDialog } from '../ui'
import { CustomFieldForm } from './CustomFieldForm'
import { apiClient } from '../../lib/api'
import type { CustomFieldDefinition, CustomFieldCreate, CustomFieldUpdate, CustomFieldEntityType } from '../../lib/api'
import { textColors, statusColors, borderColors } from '../../styles/designSystem'

const ENTITY_TYPE_LABELS: Record<'task' | 'project', string> = {
  task: 'Task',
  project: 'Project',
}

export function CustomFieldSettings() {
  const [activeEntityType, setActiveEntityType] = useState<CustomFieldEntityType>('task')
  const [fields, setFields] = useState<CustomFieldDefinition[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [isFormOpen, setIsFormOpen] = useState(false)
  const [editingField, setEditingField] = useState<CustomFieldDefinition | null>(null)
  const [isSaving, setIsSaving] = useState(false)

  const [deleteConfirmField, setDeleteConfirmField] = useState<CustomFieldDefinition | null>(null)
  const [isDeleting, setIsDeleting] = useState(false)

  const entityLabel = ENTITY_TYPE_LABELS[activeEntityType as 'task' | 'project'] ?? activeEntityType

  useEffect(() => {
    let stale = false
    setLoading(true)
    setError(null)
    apiClient.getCustomFieldDefinitions(activeEntityType)
      .then(data => { if (!stale) setFields(data) })
      .catch(err => {
        if (!stale) {
          console.error('Failed to load custom fields:', err)
          setError(`Failed to load ${entityLabel.toLowerCase()} custom fields`)
        }
      })
      .finally(() => { if (!stale) setLoading(false) })
    return () => { stale = true }
  }, [activeEntityType, entityLabel])

  const handleCreate = () => {
    setEditingField(null)
    setIsFormOpen(true)
  }

  const handleEdit = (field: CustomFieldDefinition) => {
    setEditingField(field)
    setIsFormOpen(true)
  }

  const handleDelete = (field: CustomFieldDefinition) => {
    setDeleteConfirmField(field)
  }

  const confirmDelete = async () => {
    if (!deleteConfirmField) return

    try {
      setIsDeleting(true)
      await apiClient.deleteCustomFieldDefinition(deleteConfirmField.id)
      setFields(prev => prev.filter(f => f.id !== deleteConfirmField.id))
      setDeleteConfirmField(null)
    } catch (err) {
      console.error('Failed to delete custom field:', err)
      setError(`Failed to delete ${entityLabel.toLowerCase()} custom field`)
    } finally {
      setIsDeleting(false)
    }
  }

  const handleFormSubmit = async (data: CustomFieldCreate | CustomFieldUpdate) => {
    try {
      setIsSaving(true)

      if (editingField) {
        const updated = await apiClient.updateCustomFieldDefinition(editingField.id, data as CustomFieldUpdate)
        setFields(prev => prev.map(f => f.id === updated.id ? updated : f))
      } else {
        const created = await apiClient.createCustomFieldDefinition({
          ...(data as CustomFieldCreate),
          entity_type: activeEntityType,
        })
        setFields(prev => [...prev, created])
      }

      setIsFormOpen(false)
      setEditingField(null)
    } catch (err) {
      console.error('Failed to save custom field:', err)
      throw err
    } finally {
      setIsSaving(false)
    }
  }

  const handleFormClose = () => {
    setIsFormOpen(false)
    setEditingField(null)
  }

  const handleTabChange = (entityType: CustomFieldEntityType) => {
    setActiveEntityType(entityType)
    setFields([])
    setError(null)
  }

  const getTypeLabel = (type: string) => {
    switch (type) {
      case 'text': return 'Text'
      case 'boolean': return 'Boolean'
      case 'enum': return 'Dropdown'
      default: return type
    }
  }

  const getTypeBadgeColor = (type: string) => {
    switch (type) {
      case 'text': return 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-300'
      case 'boolean': return 'bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-300'
      case 'enum': return 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300'
      default: return 'bg-gray-100 text-gray-800 dark:bg-white/[0.05] dark:text-gray-300'
    }
  }

  return (
    <>
      <Card className="p-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center space-x-2">
            <TagIcon className="w-5 h-5 text-gray-400" />
            <h3 className={`text-lg font-medium ${textColors.primary}`}>Custom Fields</h3>
          </div>
          <Button variant="primary" size="sm" onClick={handleCreate}>
            <PlusIcon className="w-4 h-4 mr-1" />
            Add Field
          </Button>
        </div>

        <div className="flex border-b border-gray-200 dark:border-white/[0.08] mb-6">
          {(['task', 'project'] as const).map(entityType => (
            <button
              key={entityType}
              onClick={() => handleTabChange(entityType)}
              className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                activeEntityType === entityType
                  ? 'border-blue-500 text-blue-600 dark:text-blue-400'
                  : 'border-transparent text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-300'
              }`}
            >
              {ENTITY_TYPE_LABELS[entityType]} Fields
            </button>
          ))}
        </div>

        <p className={`text-sm ${textColors.secondary} mb-6`}>
          Define custom fields that can be added to {entityLabel.toLowerCase()}s. These fields are available globally across all projects.
        </p>

        {error && (
          <div className={`mb-4 p-3 ${statusColors.error.bg} ${statusColors.error.text} rounded-md text-sm`}>
            {error}
          </div>
        )}

        {loading ? (
          <div className="animate-pulse space-y-4">
            <div className="space-y-3">
              <div className="h-12 bg-gray-200 dark:bg-white/[0.06] rounded"></div>
              <div className="h-12 bg-gray-200 dark:bg-white/[0.06] rounded"></div>
              <div className="h-12 bg-gray-200 dark:bg-white/[0.06] rounded"></div>
            </div>
          </div>
        ) : fields.length === 0 ? (
          <div className="text-center py-8">
            <TagIcon className="mx-auto h-12 w-12 text-gray-400" />
            <h4 className="mt-4 text-sm font-medium text-gray-900 dark:text-white">No {entityLabel.toLowerCase()} custom fields</h4>
            <p className="mt-2 text-sm text-gray-500 dark:text-gray-400">
              Get started by creating a custom field for your {entityLabel.toLowerCase()}s.
            </p>
            <Button variant="primary" size="sm" className="mt-4" onClick={handleCreate}>
              <PlusIcon className="w-4 h-4 mr-1" />
              Create Field
            </Button>
          </div>
        ) : (
          <div className="space-y-3">
            {fields.map(field => (
              <div
                key={field.id}
                className={`flex items-center justify-between p-4 border ${borderColors.default} rounded-lg hover:border-gray-300 dark:hover:border-gray-500 transition-colors`}
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center space-x-3">
                    <span className={`font-medium ${textColors.primary}`}>{field.name}</span>
                    <span className={`px-2 py-0.5 text-xs rounded-full ${getTypeBadgeColor(field.type)}`}>
                      {getTypeLabel(field.type)}
                    </span>
                    {field.mandatory && (
                      <span className="px-2 py-0.5 text-xs rounded-full bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-300">
                        Required
                      </span>
                    )}
                  </div>
                  {field.description && (
                    <p className={`mt-1 text-sm ${textColors.secondary} truncate`}>{field.description}</p>
                  )}
                  {field.type === 'enum' && field.options && field.options.length > 0 && (
                    <p className={`mt-1 text-xs ${textColors.tertiary}`}>
                      Options: {field.options.join(', ')}
                    </p>
                  )}
                </div>

                <div className="flex items-center space-x-2 ml-4">
                  <button
                    onClick={() => handleEdit(field)}
                    className="p-1.5 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors"
                    title="Edit field"
                  >
                    <PencilIcon className="w-4 h-4" />
                  </button>
                  <button
                    onClick={() => handleDelete(field)}
                    className="p-1.5 text-gray-400 hover:text-red-600 dark:hover:text-red-400 transition-colors"
                    title="Delete field"
                  >
                    <TrashIcon className="w-4 h-4" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>

      <Modal
        isOpen={isFormOpen}
        onClose={handleFormClose}
        title={editingField ? `Edit ${entityLabel} Custom Field` : `Create ${entityLabel} Custom Field`}
        maxWidth="lg"
      >
        <CustomFieldForm
          field={editingField}
          entityType={activeEntityType}
          onSubmit={handleFormSubmit}
          onCancel={handleFormClose}
          isSaving={isSaving}
        />
      </Modal>

      <ConfirmDialog
        isOpen={!!deleteConfirmField}
        onClose={() => setDeleteConfirmField(null)}
        onConfirm={confirmDelete}
        title={`Delete ${entityLabel} Custom Field`}
        message={`Are you sure you want to delete the field "${deleteConfirmField?.name}"? Existing ${entityLabel.toLowerCase()} values will be retained but displayed as plain text.`}
        confirmText="Delete"
        variant="danger"
        loading={isDeleting}
      />
    </>
  )
}
