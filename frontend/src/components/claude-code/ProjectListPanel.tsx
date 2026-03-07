import { FolderIcon } from '@heroicons/react/24/outline'
import { textColors } from '../../styles/designSystem'
import type { ClaudeCodeProject } from '../../lib/api'

interface ProjectListPanelProps {
  projects: ClaudeCodeProject[]
  selectedEncodedPath: string | null
  onSelect: (project: ClaudeCodeProject) => void
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

function formatCost(cost: number | null): string | null {
  if (cost === null || cost === undefined) return null
  return `$${cost.toFixed(4)}`
}

export function ProjectListPanel({ projects, selectedEncodedPath, onSelect }: ProjectListPanelProps) {
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
        const cost = formatCost(project.last_cost)
        const linesChanged = project.last_lines_added !== null || project.last_lines_removed !== null
          ? `+${project.last_lines_added ?? 0}/-${project.last_lines_removed ?? 0}`
          : null

        return (
          <button
            key={project.encoded_path}
            onClick={() => onSelect(project)}
            className={`w-full text-left px-4 py-3 hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors ${
              isSelected ? 'bg-blue-50 dark:bg-blue-900/30 border-l-2 border-l-blue-500' : ''
            }`}
          >
            <div className="min-w-0">
              <h3 className={`font-medium ${textColors.primary} truncate`} title={project.path}>
                {name}
              </h3>
              <p className={`text-xs ${textColors.secondary} truncate`} title={project.path}>
                {project.path}
              </p>
              <div className={`flex items-center gap-2 mt-1 text-xs ${textColors.muted}`}>
                <span>{formatRelativeTime(project.last_activity)}</span>
                <span>·</span>
                <span>{project.session_count} {project.session_count === 1 ? 'session' : 'sessions'}</span>
                {cost && (
                  <>
                    <span>·</span>
                    <span>{cost}</span>
                  </>
                )}
                {linesChanged && (
                  <>
                    <span>·</span>
                    <span className="font-mono">{linesChanged}</span>
                  </>
                )}
              </div>
            </div>
          </button>
        )
      })}
    </div>
  )
}
