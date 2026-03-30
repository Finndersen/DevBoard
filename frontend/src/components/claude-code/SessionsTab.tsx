import { useState, useEffect, useCallback, useMemo, useRef } from 'react'
import { useSearchParams, useNavigate } from 'react-router-dom'
import { ArrowPathIcon, ChevronLeftIcon } from '@heroicons/react/24/outline'
import { textColors, statusColors } from '../../styles/designSystem'
import { apiClient } from '../../lib/api'
import type { ClaudeCodeProject, ClaudeCodeSession, SessionSearchResult } from '../../lib/api'
import { ProjectListPanel } from './ProjectListPanel'
import { SessionListPanel, AGENT_ROLE_LABELS } from './SessionListPanel'
import { SessionConversationViewer } from './SessionConversationViewer'
import type { TabId } from './SessionConversationViewer'
import { SessionSearch } from './SessionSearch'
import { GoToSession } from './GoToSession'

export default function SessionsTab() {
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()

  const [selectedProjectPath, setSelectedProjectPath] = useState<string | null>(
    () => searchParams.get('project')
  )
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(
    () => searchParams.get('session')
  )

  const [projects, setProjects] = useState<ClaudeCodeProject[]>([])
  const [sessions, setSessions] = useState<ClaudeCodeSession[]>([])
  const [projectsLoading, setProjectsLoading] = useState(true)
  const [sessionsLoading, setSessionsLoading] = useState(false)
  const [projectsError, setProjectsError] = useState<string | null>(null)
  const [excludeEmpty, setExcludeEmpty] = useState(true)
  const [excludeSubAgents, setExcludeSubAgents] = useState(false)
  const [searchResults, setSearchResults] = useState<SessionSearchResult[]>([])
  const [searchQuery, setSearchQuery] = useState('')
  const [viewerActiveTab, setViewerActiveTab] = useState<TabId>('plan')

  const selectedSession = sessions.find(s => s.session_id === selectedSessionId) ?? null
  const filteredSessions = sessions.filter(s => {
    if (excludeEmpty && s.is_empty) return false
    if (excludeSubAgents && s.sub_agent_info !== null) return false
    return true
  })

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

  const selectedProject = projects.find(p => p.encoded_path === selectedProjectPath) ?? null

  // Save/restore selection state when search activates/deactivates
  const preSearchSelectionRef = useRef<{ project: string | null; session: string | null } | undefined>(undefined)
  const prevIsSearchActiveRef = useRef(isSearchActive)
  const skipRestoreRef = useRef(false)

  useEffect(() => {
    if (isSearchActive && !prevIsSearchActiveRef.current) {
      // Search just activated — save current selection and clear it to show project list
      preSearchSelectionRef.current = {
        project: selectedProjectPath,
        session: selectedSessionId,
      }
      setSelectedProjectPath(null)
      setSelectedSessionId(null)
    } else if (!isSearchActive && prevIsSearchActiveRef.current) {
      // Search just deactivated — restore previous selection (unless GoToSession already set one)
      if (preSearchSelectionRef.current && !skipRestoreRef.current) {
        setSelectedProjectPath(preSearchSelectionRef.current.project)
        setSelectedSessionId(preSearchSelectionRef.current.session)
      }
      preSearchSelectionRef.current = undefined
      skipRestoreRef.current = false
    }
    prevIsSearchActiveRef.current = isSearchActive
    // eslint-disable-next-line react-hooks/exhaustive-deps -- intentionally capturing selection state at search activation time
  }, [isSearchActive])

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
    setSelectedProjectPath(project.encoded_path)
    setSelectedSessionId(null)
    setSearchParams(prev => { prev.set('tab', 'sessions'); return prev }, { replace: true })
  }

  const handleSessionSelect = (session: ClaudeCodeSession) => {
    setSelectedSessionId(session.session_id)
  }

  const handleRefresh = useCallback(() => {
    loadProjects()
    if (selectedProjectPath) {
      loadSessions(selectedProjectPath)
    }
  }, [loadProjects, loadSessions, selectedProjectPath])

  const handleGoToSession = (sessionId: string, projectEncodedPath: string) => {
    if (isSearchActive) {
      skipRestoreRef.current = true
    }
    setSearchResults([])
    setSearchQuery('')
    setSelectedProjectPath(projectEncodedPath)
    setSelectedSessionId(sessionId)
  }

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Global toolbar */}
      <div className="px-4 py-2 border-b border-gray-200 dark:border-white/[0.08] shrink-0 flex items-center gap-4">
        <p className={`text-sm ${textColors.secondary} flex-1 min-w-0 truncate`}>
          Browse and search Claude Code project session histories
        </p>
        <button
          onClick={handleRefresh}
          disabled={projectsLoading || sessionsLoading}
          className="p-1.5 rounded-md text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 disabled:opacity-50 shrink-0"
          title="Refresh projects and sessions"
        >
          <ArrowPathIcon className="w-4 h-4" />
        </button>
        <div className="w-64 shrink-0">
          <GoToSession onLocated={handleGoToSession} />
        </div>
        <div className="w-80 shrink-0">
          <SessionSearch onResults={(results, query) => {
            setSearchResults(results)
            setSearchQuery(query)
          }} />
        </div>
      </div>

      <div className="flex flex-1 overflow-hidden">
      {/* List panel — drill-down: shows either projects or sessions */}
      <div className="w-96 shrink-0 border-r border-gray-200 dark:border-white/[0.08] flex flex-col overflow-hidden">
        {!selectedProjectPath ? (
          /* State A: Project list */
          <>
            <div className="px-4 py-3 border-b border-gray-200 dark:border-white/[0.08] shrink-0">
              <h2 className={`text-sm font-semibold ${textColors.primary}`}>Projects</h2>
            </div>
            <div className="flex-1 overflow-y-auto">
              {projectsLoading ? (
                <div className="flex items-center justify-center py-8">
                  <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-600" />
                </div>
              ) : projectsError ? (
                <div className="px-4 py-4">
                  <p className={`text-sm ${statusColors.error.text}`}>{projectsError}</p>
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
          </>
        ) : (
          /* State B: Session list for selected project */
          <>
            <div className="px-4 py-3 border-b border-gray-200 dark:border-white/[0.08] shrink-0">
              <button
                onClick={() => { setSelectedProjectPath(null); setSelectedSessionId(null) }}
                className={`flex items-center gap-1 text-xs ${textColors.accent} hover:underline mb-1`}
              >
                <ChevronLeftIcon className="w-3.5 h-3.5" />
                Projects
              </button>
              <h2
                className={`text-sm font-semibold ${textColors.primary} truncate`}
                title={selectedProject?.project_path ?? selectedProjectPath}
              >
                {selectedProject?.project_path?.split('/').filter(Boolean).pop() ?? selectedProjectPath}
              </h2>
              <div className="flex items-center gap-3 mt-2">
                <label className="flex items-center gap-1.5 text-xs text-gray-500 dark:text-gray-400 cursor-pointer whitespace-nowrap">
                  <input type="checkbox" checked={excludeEmpty} onChange={e => setExcludeEmpty(e.target.checked)} />
                  Hide empty
                </label>
                <label className="flex items-center gap-1.5 text-xs text-gray-500 dark:text-gray-400 cursor-pointer whitespace-nowrap">
                  <input type="checkbox" checked={excludeSubAgents} onChange={e => setExcludeSubAgents(e.target.checked)} />
                  Hide sub-agents
                </label>
              </div>
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
          </>
        )}
      </div>

      {/* Right panel: Conversation viewer */}
      {selectedSessionId ? (
        <div className="flex-1 flex flex-col overflow-hidden">
          <div className="px-4 py-3 border-b border-gray-200 dark:border-white/[0.08] shrink-0">
            <h2 className={`text-sm font-semibold ${textColors.primary}`}>
              {selectedSession?.label ?? 'Session'}
            </h2>
            <div className={`flex items-center gap-2 text-xs ${textColors.muted} min-w-0`}>
              {selectedSession?.task_info && (
                <>
                  <span className="shrink-0">·</span>
                  <button
                    onClick={() => navigate(`/tasks/${selectedSession.task_info!.task_id}`)}
                    className="text-blue-600 dark:text-blue-400 hover:underline truncate"
                  >
                    Task #{selectedSession.task_info.task_id}: {selectedSession.task_info.task_title}
                  </button>
                  <span className="shrink-0 inline-flex items-center px-1.5 py-0.5 rounded font-medium bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300">
                    {AGENT_ROLE_LABELS[selectedSession.task_info.agent_role] ?? selectedSession.task_info.agent_role}
                  </span>
                </>
              )}
              {selectedSession?.sub_agent_info && (
                <>
                  <span className="shrink-0">·</span>
                  {selectedSession.sub_agent_info.parent_task_id && (
                    <button
                      onClick={() => navigate(`/tasks/${selectedSession.sub_agent_info!.parent_task_id}`)}
                      className="text-blue-600 dark:text-blue-400 hover:underline truncate"
                    >
                      {selectedSession.sub_agent_info.parent_task_title}
                    </button>
                  )}
                  <span className="shrink-0 inline-flex items-center px-1.5 py-0.5 rounded font-medium bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300">
                    {AGENT_ROLE_LABELS[selectedSession.sub_agent_info.agent_role] ?? selectedSession.sub_agent_info.agent_role}
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
              onActiveTabChange={setViewerActiveTab}
              workingDir={selectedProject?.path}
              tabBarRight={(() => {
                const isCombined = selectedSession?.session_role === 'plan' && !!selectedSession?.linked_session_id
                const showImplTab = isCombined && viewerActiveTab === 'implementation'
                const displaySessionId = showImplTab ? selectedSession!.linked_session_id! : selectedSessionId
                const implSession = showImplTab
                  ? sessions.find(s => s.session_id === selectedSession!.linked_session_id)
                  : null
                const displayTime = showImplTab && implSession?.start_time
                  ? implSession.start_time
                  : selectedSession?.start_time
                return (
                  <span className={`flex items-center gap-2 text-xs ${textColors.muted}`}>
                    <span className="font-mono truncate">{displaySessionId}</span>
                    {displayTime && (
                      <>
                        <span className="shrink-0">·</span>
                        <span className="shrink-0">{new Date(displayTime).toLocaleString('en-US', { month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit' })}</span>
                      </>
                    )}
                  </span>
                )
              })()}
            />
          </div>
        </div>
      ) : (
        <div className="flex-1 flex items-center justify-center">
          <p className={`text-sm ${textColors.secondary}`}>
            {selectedProjectPath ? 'Select a session to view its conversation' : 'Select a project to browse its sessions'}
          </p>
        </div>
      )}
      </div>
    </div>
  )
}
