import type { BackgroundAgentRunStatus } from '../lib/api'

export function computeSuccessRate(completed: number, total: number): number | null {
  if (total === 0) return null
  return (completed / total) * 100
}

export function formatTriggeredBy(triggeredBy: string): { icon: string; label: string } {
  if (triggeredBy === 'manual') return { icon: '▶', label: 'Manual' }
  if (triggeredBy.startsWith('schedule')) return { icon: '⏰', label: 'Schedule' }
  if (triggeredBy.startsWith('event:') || triggeredBy === 'event') return { icon: '⚡', label: 'Event' }
  return { icon: '▶', label: triggeredBy }
}

export function formatDuration(startedAt: string, completedAt: string | null): string {
  if (!completedAt) return '—'
  const ms = new Date(completedAt).getTime() - new Date(startedAt).getTime()
  if (ms < 1000) return `${ms}ms`
  const s = Math.round(ms / 1000)
  if (s < 60) return `${s}s`
  const m = Math.floor(s / 60)
  return `${m}m ${s % 60}s`
}

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

export function statusBadgeClass(status: BackgroundAgentRunStatus): string {
  const classes: Record<BackgroundAgentRunStatus, string> = {
    completed: 'bg-green-900/50 text-green-400 border border-green-700/50',
    failed: 'bg-red-900/50 text-red-400 border border-red-700/50',
    running: 'bg-blue-900/50 text-blue-400 border border-blue-700/50',
    queued: 'bg-gray-700 text-gray-400',
    cancelled: 'bg-gray-700 text-gray-400',
  }
  return classes[status] ?? 'bg-gray-700 text-gray-400'
}
