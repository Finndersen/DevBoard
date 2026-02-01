import { useState, useCallback } from 'react'
import { apiClient } from '../lib/api'
import type { DirectoryListResponse } from '../lib/api'

export function useListDirectory() {
  const [data, setData] = useState<DirectoryListResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const listDirectory = useCallback(async (path?: string) => {
    setLoading(true)
    setError(null)
    try {
      const result = await apiClient.listDirectory(path)
      setData(result)
      return result
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to list directory'
      setError(errorMessage)
      throw err
    } finally {
      setLoading(false)
    }
  }, [])

  return {
    data,
    loading,
    error,
    listDirectory,
  }
}
