import { useState, useEffect, useCallback, useRef } from 'react'

export interface ApiState<T> {
  data: T | null
  loading: boolean
  error: string | null
}

export interface UseApiOptions {
  immediate?: boolean
}

export function useApi<T>(
  apiCall: () => Promise<T>,
  options: UseApiOptions = {}
): ApiState<T> & { refetch: () => Promise<void>; setData: (data: T) => void } {
  const { immediate = true } = options

  // Store the apiCall in a ref to avoid dependency issues
  const apiCallRef = useRef(apiCall)
  apiCallRef.current = apiCall

  const [state, setState] = useState<ApiState<T>>({
    data: null,
    loading: immediate,
    error: null
  })

  const inFlightRef = useRef(false)

  const execute = useCallback(async () => {
    if (inFlightRef.current) return
    inFlightRef.current = true
    setState(prev => ({ ...prev, loading: true, error: null }))

    try {
      const data = await apiCallRef.current()
      setState({ data, loading: false, error: null })
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'An unexpected error occurred'
      setState(prev => ({ ...prev, loading: false, error: errorMessage }))
    } finally {
      inFlightRef.current = false
    }
  }, [])

  const setData = useCallback((data: T) => {
    setState({ data, loading: false, error: null })
  }, [])

  useEffect(() => {
    if (immediate) {
      execute()
    }
  }, [immediate, execute])

  return {
    ...state,
    refetch: execute,
    setData
  }
}

interface UseMutationOptions<T> {
  onSuccess?: (data: T) => void
  onError?: (error: Error) => void
  updateCache?: (data: T) => void
}

export function useMutation<T, TArgs extends unknown[]>(
  mutationFn: (...args: TArgs) => Promise<T>,
  options: UseMutationOptions<T> = {}
): {
  mutate: (...args: TArgs) => Promise<T>
  loading: boolean
  error: string | null
} {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  
  // Store options in ref to avoid dependency issues
  const optionsRef = useRef(options)
  optionsRef.current = options
  
  // Store mutationFn in ref to avoid dependency issues  
  const mutationFnRef = useRef(mutationFn)
  mutationFnRef.current = mutationFn

  const mutate = useCallback(async (...args: TArgs): Promise<T> => {
    setLoading(true)
    setError(null)
    
    try {
      const result = await mutationFnRef.current(...args)
      
      // Update local cache with returned data (eliminates need for refetch!)
      optionsRef.current.updateCache?.(result)
      optionsRef.current.onSuccess?.(result)
      
      setLoading(false)
      return result
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'An unexpected error occurred'
      setError(errorMessage)
      optionsRef.current.onError?.(err as Error)
      setLoading(false)
      throw err
    }
  }, []) // Empty dependency array for stable function

  return { mutate, loading, error }
}