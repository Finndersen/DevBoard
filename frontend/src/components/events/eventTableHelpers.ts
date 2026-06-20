import type { LogEntrySource } from '../../lib/api'

export const DEFAULT_LIMIT = 20

export function formatRelativeTime(timestamp: string): string {
  const diff = Date.now() - new Date(timestamp).getTime()
  const minutes = Math.floor(diff / 60_000)
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  return `${days}d ago`
}

export function sourceDotColor(source: LogEntrySource): string {
  switch (source) {
    case 'developer': return 'bg-blue-500'
    case 'system': return 'bg-gray-500'
    case 'agent': return 'bg-purple-500'
  }
}


export function typeBadgeClass(type: string, source: LogEntrySource): string {
  if (source === 'system') return 'bg-gray-700 text-gray-400'
  if (source === 'agent') return 'bg-purple-950 text-purple-300'
  switch (type) {
    case 'blocker': return 'bg-red-950 text-red-300'
    case 'decision': return 'bg-amber-950 text-amber-300'
    case 'thought': return 'bg-blue-950 text-blue-300'
    default: return 'bg-gray-700 text-gray-400'
  }
}
