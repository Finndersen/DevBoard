import { useState, useEffect, useCallback, useMemo } from 'react'
import { useSearchParams, useNavigate } from 'react-router-dom'
import { textColors } from '../../styles/designSystem'
import { apiClient } from '../../lib/api'
import type { ClaudeCodeProject, ClaudeCodeSession, SessionSearchResult } from '../../lib/api'
import { ProjectListPanel } from './ProjectListPanel'
import { SessionListPanel, AGENT_ROLE_LABELS } from './SessionListPanel'
import { SessionConversationViewer } from './SessionConversationViewer'
import { SessionSearch } from './SessionSearch'

export default function SessionsTab() {
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()

  const selectedProjectPath = searchParams.get('project')
  const selectedSessionId = searchParams.get('session')

  const [projects, setProjects] = useState<ClaudeCodeProject[]>([])
  const [sessions, setSessions] = useState<ClaudeCodeSession[]>([])
  const [projectsLoading, setProjectsLoading] = useState(true)
  const [sessionsLoading, setSessionsLoading] = useState(false)
  const [projectsError, setProjectsError] = useState<string | null>(null)
  const [excludeEmpty, setExcludeEmpty] = useState(true)
  const [searchResults, setSearchResults] = useState<SessionSearchResult[]>([])
  const [searchQuery, setSearchQuery] = useState('')

  const selectedProject = projects.find(p => p.encoded_path === selectedProjectPath) ?? null
  const selectedSession = sessions.find(s => s.session_id === selectedSessionId) ?? null
  const filteredSessions = excludeEmpty ? sessions.filter(s => !s.is_empty) : sessions

  const isSearchActive = searchQuery.trim().length > 0

  const matchingProjectPaths = useMemo(
    () => new Set(searchResults.map(r => r.project_encoded_path)),
    [searchResults]
  )

  const matchingSessionIds = useMemo(
    () => new Set(searchResults.map(r => r.session_id)),
    [searchResults]
  )

  const projectMatchCounts = useMemo(() => {
    const counts = new Map<string, number>()
    for (const r of searchResults) {
      counts.set(r.project_encoded_path, (counts.get(r.project_encoded_path) ?? 0) + 1)
    }
    return counts
  }, [searchResults])

  const sessionMatchCounts = useMemo(() => {
    const counts = new Map<string, number>()
    for (const r of searchResults) {
      counts.set(r.session_id, (counts.get(r.session_id) ?? 0) + 1)
    }
    return counts
  }, [searchResults])

  const highlightUuids = useMemo(() => {
    if (!isSearchActive || !selectedSessionId) return undefined
    return searchResults
      .filter(r => r.session_id === selectedSessionId && r.message_uuid)
      .map(r => r.message_uuid!)
  }, [isSearchActive, selectedSessionId, searchResults])

  const displayedProjects = isSearchActive
    ? projects.filter(p => matchingProjectPaths.has(p.encoded_path))
    : projects

  const displayedSessions = isSearchActive
    ? filteredSessions.filter(s => matchingSessionIds.has(s.session_id))
    : filteredSessions

  const loadProjects = useCallback(async () => {
    setProjectsLoading(true)
    setProjectsError(null)
    try {
      const data = await apiClient.getClaudeCodeProjects()
      setProjects(data)
    } catch (err) {
      setProjectsError(err instanceof Error ? err.message : 'Failed to load projects')
    } finally {
      setProjectsLoading(false)
    }
  }, [])

  const loadSessions = useCallback(async (encodedPath: string) => {
    setSessionsLoading(true)
    setSessions([])
    try {
      const data = await apiClient.getClaudeCodeSessions(encodedPath)
      setSessions(data)
    } catch (err) {
      console.error('Failed to load sessions:', err)
      setSessions([])
    } finally {
      setSessionsLoading(false)
    }
  }, [])

  useEffect(() => {
    loadProjects()
  }, [loadProjects])

  useEffect(() => {
    if (selectedProjectPath) {
      loadSessions(selectedProjectPath)
    } else {
      setSessions([])
    }
  }, [selectedProjectPath, loadSessions])

  const handleProjectSelect = (project: ClaudeCodeProject) => {
    setSearchParams(prev => {
      prev.set('tab', 'sessions')
      prev.set('project', project.encoded_path)
      prev.delete('session')
      return prev
    }, { replace: true })
  }

  const handleSessionSelect = (session: ClaudeCodeSession) => {
    setSearchParams(prev => {
      prev.set('session', session.session_id)
      return prev
    }, { replace: true })
  }

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Global toolbar */}
      <div className="px-4 py-2 border-b border-gray-200 dark:border-gray-700 shrink-0 flex items-center gap-4">
        <p className={`text-sm ${textColors.secondary} flex-1 min-w-0 truncate`}>
          Browse and search Claude Code project session histories
        </p>
        <label className="flex items-center gap-1.5 text-xs text-gray-500 dark:text-gray-400 cursor-pointer whitespace-nowrap">
          <input type="checkbox" checked={excludeEmpty} onChange={e => setExcludeEmpty(e.target.checked)} />
          Hide empty
        </label>
        <div className="w-80 shrink-0">
          <SessionSearch onResults={(results, query) => {
            setSearchResults(results)
            setSearchQuery(query)
          }} />
        </div>
      </div>

      <div className="flex flex-1 overflow-hidden">
      {/* Left panel: Projects */}
      <div className="w-72 shrink-0 border-r border-gray-200 dark:border-gray-700 flex flex-col overflow-hidden">
        <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-700 shrink-0">
          <h2 className={`text-sm font-semibold ${textColors.primary}`}>Projects</h2>
        </div>
        <div className="flex-1 overflow-y-auto">
          {projectsLoading ? (
            <div className="flex items-center justify-center py-8">
              <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-600" />
            </div>
          ) : projectsError ? (
            <div className="px-4 py-4">
              <p className="text-sm text-red-600 dark:text-red-400">{projectsError}</p>
              <button onClick={loadProjects} className={`mt-1 text-xs ${textColors.accent} hover:underline`}>
                Retry
              </button>
            </div>
          ) : (
            <ProjectListPanel
              projects={displayedProjects}
              selectedEncodedPath={selectedProjectPath}
              onSelect={handleProjectSelect}
              matchCounts={isSearchActive ? projectMatchCounts : undefined}
            />
          )}
        </div>
      </div>

      {/* Middle panel: Sessions */}
      {selectedProjectPath && (
        <div className="w-96 shrink-0 border-r border-gray-200 dark:border-gray-700 flex flex-col overflow-hidden">
          <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-700 shrink-0">
            <h2 className={`text-sm font-semibold ${textColors.primary}`}>Sessions</h2>
          </div>
          <div className="flex-1 overflow-y-auto">
            <SessionListPanel
              sessions={displayedSessions}
              selectedSessionId={selectedSessionId}
              loading={sessionsLoading}
              onSelect={handleSessionSelect}
              matchCounts={isSearchActive ? sessionMatchCounts : undefined}
            />
          </div>
        </div>
      )}

      {/* Right panel: Conversation viewer */}
      {selectedSessionId ? (
        <div className="flex-1 flex flex-col overflow-hidden">
          <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-700 shrink-0">
            <h2 className={`text-sm font-semibold ${textColors.primary}`}>
              {selectedSession?.label ?? 'Session'}
            </h2>
            <div className={`flex items-center gap-2 text-xs ${textColors.muted} min-w-0`}>
              <span className="font-mono truncate">{selectedSessionId}</span>
              {selectedSession?.task_info && (
                <>
                  <span className="shrink-0">·</span>
                  <span className="shrink-0">Task #{selectedSession.task_info.task_id}</span>
                  <span className="shrink-0">·</span>
                  <button
                    onClick={() => navigate(`/tasks/${selectedSession.task_info!.task_id}`)}
                    className="text-blue-600 dark:text-blue-400 hover:underline truncate"
                  >
                    {selectedSession.task_info.task_title}
                  </button>
                  <span className="shrink-0 inline-flex items-center px-1.5 py-0.5 rounded font-medium bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300">
                    {AGENT_ROLE_LABELS[selectedSession.task_info.agent_role] ?? selectedSession.task_info.agent_role}
                  </span>
                </>
              )}
            </div>
          </div>
          <div className="flex-1 overflow-hidden">
            <SessionConversationViewer
              sessionId={selectedSessionId}
              linkedSessionId={selectedSession?.linked_session_id ?? null}
              highlightUuids={highlightUuids}
            />
          </div>
        </div>
      ) : selectedProjectPath ? (
        <div className="flex-1 flex items-center justify-center">
          <p className={`text-sm ${textColors.secondary}`}>Select a session to view its conversation</p>
        </div>
      ) : (
        <div className="flex-1 flex items-center justify-center">
          <p className={`text-sm ${textColors.secondary}`}>Select a project to browse its sessions</p>
        </div>
      )}
      </div>
    </div>
  )
}
