import { useState, useCallback } from 'react'

interface UseAsyncOperationOptions<R> {
  onSuccess?: (result: R) => void
  onError?: (error: Error) => void
}

/**
 * Custom hook for managing async operations with loading and error states
 * Eliminates repetitive try/catch/loading state patterns
 */
export function useAsyncOperation<T extends unknown[], R>(
  operation: (...args: T) => Promise<R>,
  options: UseAsyncOperationOptions<R> = {}
) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  
  const execute = useCallback(async (...args: T): Promise<R | undefined> => {
    setLoading(true)
    setError(null)
    
    try {
      const result = await operation(...args)
      options.onSuccess?.(result)
      return result
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Operation failed'
      setError(errorMessage)
      options.onError?.(err as Error)
      console.error('Operation failed:', err)
    } finally {
      setLoading(false)
    }
  }, [operation, options])
  
  return { 
    execute, 
    loading, 
    error,
    clearError: useCallback(() => setError(null), [])
  }
}