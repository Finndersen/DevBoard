import { useState, useEffect, useCallback } from 'react'
import { useNotificationStore } from '../stores/notificationStore'

/**
 * Custom hook for managing editable field state with save/cancel functionality
 * Eliminates repetitive edit/save/cancel patterns across forms
 */
export function useEditableField<T>(
  originalValue: T,
  saveFunction: (value: T) => Promise<unknown>
) {
  const [isEditing, setIsEditing] = useState(false)
  const [editedValue, setEditedValue] = useState(originalValue)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const addNotification = useNotificationStore(s => s.addNotification)
  
  // Update edited value when original value changes
  useEffect(() => {
    setEditedValue(originalValue)
  }, [originalValue])
  
  const startEditing = useCallback(() => {
    setEditedValue(originalValue)
    setIsEditing(true)
    setError(null)
  }, [originalValue])
  
  const cancelEditing = useCallback(() => {
    setEditedValue(originalValue)
    setIsEditing(false)
    setError(null)
  }, [originalValue])
  
  const save = useCallback(async () => {
    setSaving(true)
    setError(null)
    
    try {
      await saveFunction(editedValue)
      setIsEditing(false)
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Save failed'
      setError(errorMessage)
      console.error('Save failed:', err)
      addNotification({
        type: 'system_error',
        priority: 'high',
        entityType: null,
        entityId: null,
        entityTitle: null,
        conversationId: null,
        message: errorMessage,
        actions: [],
      })
    } finally {
      setSaving(false)
    }
  }, [editedValue, saveFunction, addNotification])
  
  return {
    isEditing,
    editedValue,
    setEditedValue,
    saving,
    error,
    startEditing,
    cancelEditing,
    save
  }
}