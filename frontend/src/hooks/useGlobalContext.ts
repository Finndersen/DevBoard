import { useCallback } from 'react'
import { apiClient } from '../lib/api'
import { useApi } from './useApi'
import { useEditableField } from './useEditableField'

export function useGlobalContext() {
  const { data, loading, error, setData } = useApi(
    () => apiClient.getGlobalContext(),
    { immediate: true }
  )

  const content = data?.content ?? ''

  const saveFunction = useCallback(
    async (newContent: string) => {
      const updated = await apiClient.updateGlobalContext(newContent)
      setData(updated)
    },
    [setData]
  )

  const field = useEditableField(content, saveFunction)

  return { content, field, isLoading: loading, error }
}
