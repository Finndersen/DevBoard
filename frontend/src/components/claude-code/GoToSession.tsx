import { useState, useCallback } from 'react'
import { ArrowTopRightOnSquareIcon, XMarkIcon } from '@heroicons/react/24/outline'
import { apiClient } from '../../lib/api'
import { surfaces, textColors, statusColors, borderColors } from '../../styles/designSystem'

interface GoToSessionProps {
  onLocated: (sessionId: string, projectEncodedPath: string) => void
}

export function GoToSession({ onLocated }: GoToSessionProps) {
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const locate = useCallback(async () => {
    const sessionId = input.trim()
    if (!sessionId) return
    setLoading(true)
    setError(null)
    try {
      const result = await apiClient.locateClaudeCodeSession(sessionId)
      onLocated(sessionId, result.project_encoded_path)
      setInput('')
    } catch (err) {
      const message = err instanceof Error ? err.message : ''
      setError(message.includes('404') ? 'Session not found' : 'Failed to locate session')
    } finally {
      setLoading(false)
    }
  }, [input, onLocated])

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') locate()
    if (e.key === 'Escape') {
      setInput('')
      setError(null)
    }
  }

  return (
    <div className="relative">
      <ArrowTopRightOnSquareIcon className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
      <input
        type="text"
        value={input}
        onChange={e => { setInput(e.target.value); setError(null) }}
        onKeyDown={handleKeyDown}
        placeholder="Go to session ID… (Enter)"
        className={`w-full pl-9 pr-8 py-1.5 text-sm border ${borderColors.input} rounded-md
          ${surfaces.raised} ${textColors.primary}
          placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent`}
      />
      {loading && (
        <div className="absolute right-3 top-1/2 -translate-y-1/2">
          <div className="animate-spin rounded-full h-3 w-3 border-b-2 border-blue-600" />
        </div>
      )}
      {input && !loading && (
        <button
          onClick={() => { setInput(''); setError(null) }}
          className="absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200"
          aria-label="Clear"
        >
          <XMarkIcon className="w-3.5 h-3.5" />
        </button>
      )}
      {error && <p className={`mt-1 text-xs ${statusColors.error.text}`}>{error}</p>}
    </div>
  )
}
