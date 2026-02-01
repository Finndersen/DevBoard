import { useState, useCallback } from 'react'
import { apiClient } from '../lib/api'
import type {
  ValidatePathResponse,
  BootstrapPreviewResponse,
  BootstrapCodebaseRequest,
  BootstrapCodebaseResponse,
} from '../lib/api'

export interface UseCodebaseBootstrapReturn {
  // Validation
  validation: ValidatePathResponse | null
  validationLoading: boolean
  validationError: string | null
  validatePath: (path: string) => Promise<ValidatePathResponse | null>
  clearValidation: () => void

  // Preview
  preview: BootstrapPreviewResponse | null
  previewLoading: boolean
  previewError: string | null
  loadPreview: (
    path: string,
    name: string,
    description: string,
    createGitignore?: boolean,
    createReadme?: boolean,
    createClaudeMd?: boolean,
  ) => Promise<BootstrapPreviewResponse | null>

  // Bootstrap execution
  bootstrapResult: BootstrapCodebaseResponse | null
  bootstrapLoading: boolean
  bootstrapError: string | null
  executeBootstrap: (request: BootstrapCodebaseRequest) => Promise<BootstrapCodebaseResponse | null>

  // Reset all state
  reset: () => void
}

export function useCodebaseBootstrap(): UseCodebaseBootstrapReturn {
  // Validation state
  const [validation, setValidation] = useState<ValidatePathResponse | null>(null)
  const [validationLoading, setValidationLoading] = useState(false)
  const [validationError, setValidationError] = useState<string | null>(null)

  // Preview state
  const [preview, setPreview] = useState<BootstrapPreviewResponse | null>(null)
  const [previewLoading, setPreviewLoading] = useState(false)
  const [previewError, setPreviewError] = useState<string | null>(null)

  // Bootstrap state
  const [bootstrapResult, setBootstrapResult] = useState<BootstrapCodebaseResponse | null>(null)
  const [bootstrapLoading, setBootstrapLoading] = useState(false)
  const [bootstrapError, setBootstrapError] = useState<string | null>(null)

  const validatePath = useCallback(async (path: string): Promise<ValidatePathResponse | null> => {
    setValidationLoading(true)
    setValidationError(null)

    try {
      const result = await apiClient.validateCodebasePath(path)
      setValidation(result)
      return result
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to validate path'
      setValidationError(message)
      return null
    } finally {
      setValidationLoading(false)
    }
  }, [])

  const clearValidation = useCallback(() => {
    setValidation(null)
    setValidationError(null)
  }, [])

  const loadPreview = useCallback(async (
    path: string,
    name: string,
    description: string,
    createGitignore: boolean = true,
    createReadme: boolean = true,
    createClaudeMd: boolean = true,
  ): Promise<BootstrapPreviewResponse | null> => {
    setPreviewLoading(true)
    setPreviewError(null)

    try {
      const result = await apiClient.previewBootstrap(
        path,
        name,
        description,
        createGitignore,
        createReadme,
        createClaudeMd,
      )
      setPreview(result)
      return result
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to load preview'
      setPreviewError(message)
      return null
    } finally {
      setPreviewLoading(false)
    }
  }, [])

  const executeBootstrap = useCallback(async (
    request: BootstrapCodebaseRequest,
  ): Promise<BootstrapCodebaseResponse | null> => {
    setBootstrapLoading(true)
    setBootstrapError(null)

    try {
      const result = await apiClient.bootstrapCodebase(request)
      setBootstrapResult(result)
      return result
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Bootstrap failed'
      setBootstrapError(message)
      return null
    } finally {
      setBootstrapLoading(false)
    }
  }, [])

  const reset = useCallback(() => {
    setValidation(null)
    setValidationLoading(false)
    setValidationError(null)
    setPreview(null)
    setPreviewLoading(false)
    setPreviewError(null)
    setBootstrapResult(null)
    setBootstrapLoading(false)
    setBootstrapError(null)
  }, [])

  return {
    // Validation
    validation,
    validationLoading,
    validationError,
    validatePath,
    clearValidation,

    // Preview
    preview,
    previewLoading,
    previewError,
    loadPreview,

    // Bootstrap
    bootstrapResult,
    bootstrapLoading,
    bootstrapError,
    executeBootstrap,

    // Reset
    reset,
  }
}
