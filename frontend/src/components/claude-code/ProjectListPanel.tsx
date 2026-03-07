import { FolderIcon } from '@heroicons/react/24/outline'
import { textColors } from '../../styles/designSystem'
import type { ClaudeCodeProject } from '../../lib/api'

interface ProjectListPanelProps {
  projects: ClaudeCodeProject[]
  selectedEncodedPath: string | null
  onSelect: (project: ClaudeCodeProject) => void
  matchCounts?: Map<string, number>
}

function formatRelativeTime(isoDate: string | null): string {
  if (!isoDate) return 'Never'
  const date = new Date(isoDate)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMinutes = Math.floor(diffMs / 60000)

  if (diffMinutes < 1) return 'Just now'
  if (diffMinutes < 60) return `${diffMinutes}m ago`
  const diffHours = Math.floor(diffMinutes / 60)
  if (diffHours < 24) return `${diffHours}h ago`
  const diffDays = Math.floor(diffHours / 24)
  if (diffDays < 30) return `${diffDays}d ago`
  return date.toLocaleDateString()
}

function getFriendlyProjectName(path: string): string {
  const parts = path.split('/').filter(Boolean)
  return parts.length > 0 ? parts[parts.length - 1] : path
}

export function ProjectListPanel({ projects, selectedEncodedPath, onSelect, matchCounts }: ProjectListPanelProps) {
  if (projects.length === 0) {
    return (
      <div className="text-center py-8 px-4">
        <FolderIcon className="w-10 h-10 mx-auto text-gray-400 mb-3" />
        <p className={`text-sm ${textColors.secondary}`}>No Claude Code projects found</p>
        <p className={`text-xs ${textColors.muted} mt-1`}>
          Run Claude Code in a project to get started
        </p>
      </div>
    )
  }

  return (
    <div className="divide-y divide-gray-200 dark:divide-gray-700">
      {projects.map(project => {
        const isSelected = project.encoded_path === selectedEncodedPath
        const name = getFriendlyProjectName(project.path)

        return (
          <button
            key={project.encoded_path}
            onClick={() => onSelect(project)}
            className={`w-full text-left px-4 py-3 hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors ${
              isSelected ? 'bg-blue-50 dark:bg-blue-900/30 border-l-2 border-l-blue-500' : ''
            }`}
          >
            <div className="min-w-0">
              <h3 className={`font-medium ${textColors.primary} truncate flex items-center`} title={project.path}>
                <span className="truncate">{name}</span>
                {matchCounts?.get(project.encoded_path) ? (
                  <span className="ml-1.5 shrink-0 inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium bg-amber-100 dark:bg-amber-900/40 text-amber-800 dark:text-amber-300">
                    {matchCounts.get(project.encoded_path)}
                  </span>
                ) : null}
              </h3>
              <p className={`text-xs ${textColors.secondary} truncate`} title={project.path}>
                {project.path}
              </p>
              <div className={`flex items-center gap-2 mt-1 text-xs ${textColors.muted}`}>
                <span>{formatRelativeTime(project.last_activity)}</span>
                <span>·</span>
                <span>{project.session_count} {project.session_count === 1 ? 'session' : 'sessions'}</span>
              </div>
            </div>
          </button>
        )
      })}
    </div>
  )
}
