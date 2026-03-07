import { useState, useEffect, useCallback, useRef } from 'react'
import { MagnifyingGlassIcon } from '@heroicons/react/24/outline'
import { textColors } from '../../styles/designSystem'
import { apiClient } from '../../lib/api'
import type { SessionSearchResult } from '../../lib/api'

interface SessionSearchProps {
  projectPath: string | null
  onResultSelect: (result: SessionSearchResult) => void
}

export function SessionSearch({ projectPath, onResultSelect }: SessionSearchProps) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<SessionSearchResult[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const search = useCallback(async (q: string) => {
    if (!q.trim()) {
      setResults([])
      return
    }
    setLoading(true)
    setError(null)
    try {
      const data = await apiClient.searchClaudeCodeSessions(q, projectPath ?? undefined)
      setResults(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Search failed')
      setResults([])
    } finally {
      setLoading(false)
    }
  }, [projectPath])

  useEffect(() => {
    if (debounceRef.current) {
      clearTimeout(debounceRef.current)
    }
    debounceRef.current = setTimeout(() => {
      search(query)
    }, 300)

    return () => {
      if (debounceRef.current) {
        clearTimeout(debounceRef.current)
      }
    }
  }, [query, search])

  return (
    <div className="border-b border-gray-200 dark:border-gray-700">
      {/* Search input */}
      <div className="p-3">
        <div className="relative">
          <MagnifyingGlassIcon className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            type="text"
            value={query}
            onChange={e => setQuery(e.target.value)}
            placeholder={projectPath ? 'Search this project…' : 'Search all sessions…'}
            className="w-full pl-9 pr-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-md
              bg-white dark:bg-gray-800 text-gray-900 dark:text-white
              placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
          {loading && (
            <div className="absolute right-3 top-1/2 -translate-y-1/2">
              <div className="animate-spin rounded-full h-3 w-3 border-b-2 border-blue-600" />
            </div>
          )}
        </div>
        {error && <p className="mt-1 text-xs text-red-600 dark:text-red-400">{error}</p>}
      </div>

      {/* Results */}
      {query.trim() && results.length > 0 && (
        <div className="max-h-48 overflow-y-auto border-t border-gray-200 dark:border-gray-700">
          {results.map((result, idx) => (
            <button
              key={`${result.session_id}-${result.line_number}-${idx}`}
              onClick={() => onResultSelect(result)}
              className="w-full text-left px-3 py-2 hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors"
            >
              <p className={`text-xs font-mono ${textColors.secondary} truncate`}>
                {result.line_content}
              </p>
              <p className={`text-xs ${textColors.muted} mt-0.5`}>
                {result.project_encoded_path} · line {result.line_number}
              </p>
            </button>
          ))}
        </div>
      )}

      {query.trim() && !loading && results.length === 0 && (
        <div className="px-3 pb-2">
          <p className={`text-xs ${textColors.muted}`}>No results</p>
        </div>
      )}
    </div>
  )
}
