import { useState, useCallback } from 'react'
import { MagnifyingGlassIcon, XMarkIcon } from '@heroicons/react/24/outline'
import { apiClient } from '../../lib/api'
import type { SessionSearchResult } from '../../lib/api'

interface SessionSearchProps {
  onResults: (results: SessionSearchResult[], query: string) => void
}

export function SessionSearch({ onResults }: SessionSearchProps) {
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const search = useCallback(async () => {
    if (!query.trim()) {
      onResults([], '')
      return
    }
    setLoading(true)
    setError(null)
    try {
      const data = await apiClient.searchClaudeCodeSessions(query)
      onResults(data, query)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Search failed')
      onResults([], query)
    } finally {
      setLoading(false)
    }
  }, [query, onResults])

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') search()
    if (e.key === 'Escape') {
      setQuery('')
      onResults([], '')
    }
  }

  return (
    <div className="relative">
      <MagnifyingGlassIcon className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
      <input
        type="text"
        value={query}
        onChange={e => setQuery(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Search all sessions… (Enter)"
        className="w-full pl-9 pr-8 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-md
          bg-white dark:bg-gray-800 text-gray-900 dark:text-white
          placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
      />
      {loading && (
        <div className="absolute right-3 top-1/2 -translate-y-1/2">
          <div className="animate-spin rounded-full h-3 w-3 border-b-2 border-blue-600" />
        </div>
      )}
      {query && !loading && (
        <button
          onClick={() => { setQuery(''); onResults([], '') }}
          className="absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200"
          aria-label="Clear search"
        >
          <XMarkIcon className="w-3.5 h-3.5" />
        </button>
      )}
      {error && <p className="mt-1 text-xs text-red-600 dark:text-red-400">{error}</p>}
    </div>
  )
}
