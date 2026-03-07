import { useState, useEffect, useCallback } from 'react'
import { useSearchParams } from 'react-router-dom'
import { textColors } from '../../styles/designSystem'
import { apiClient } from '../../lib/api'
import type { ClaudeCodeProject, ClaudeCodeSession, SessionSearchResult } from '../../lib/api'
import { ProjectListPanel } from './ProjectListPanel'
import { SessionListPanel } from './SessionListPanel'
import { SessionConversationViewer } from './SessionConversationViewer'
import { SessionSearch } from './SessionSearch'

export default function SessionsTab() {
  const [searchParams, setSearchParams] = useSearchParams()

  const selectedProjectPath = searchParams.get('project')
  const selectedSessionId = searchParams.get('session')

  const [projects, setProjects] = useState<ClaudeCodeProject[]>([])
  const [sessions, setSessions] = useState<ClaudeCodeSession[]>([])
  const [projectsLoading, setProjectsLoading] = useState(true)
  const [sessionsLoading, setSessionsLoading] = useState(false)
  const [projectsError, setProjectsError] = useState<string | null>(null)

  const selectedProject = projects.find(p => p.encoded_path === selectedProjectPath) ?? null

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

  const handleSearchResultSelect = (result: SessionSearchResult) => {
    setSearchParams(prev => {
      prev.set('tab', 'sessions')
      prev.set('project', result.project_encoded_path)
      prev.set('session', result.session_id)
      return prev
    }, { replace: true })
  }

  return (
    <div className="flex h-full overflow-hidden">
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
              projects={projects}
              selectedEncodedPath={selectedProjectPath}
              onSelect={handleProjectSelect}
            />
          )}
        </div>
      </div>

      {/* Middle panel: Sessions */}
      {selectedProjectPath && (
        <div className="w-80 shrink-0 border-r border-gray-200 dark:border-gray-700 flex flex-col overflow-hidden">
          <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-700 shrink-0">
            <h2 className={`text-sm font-semibold ${textColors.primary} truncate`}>
              {selectedProject ? selectedProject.path.split('/').pop() : 'Sessions'}
            </h2>
          </div>
          <SessionSearch
            projectPath={selectedProject?.path ?? null}
            onResultSelect={handleSearchResultSelect}
          />
          <div className="flex-1 overflow-y-auto">
            <SessionListPanel
              sessions={sessions}
              selectedSessionId={selectedSessionId}
              loading={sessionsLoading}
              onSelect={handleSessionSelect}
            />
          </div>
        </div>
      )}

      {/* Right panel: Conversation viewer */}
      {selectedSessionId ? (
        <div className="flex-1 flex flex-col overflow-hidden">
          <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-700 shrink-0">
            <h2 className={`text-sm font-semibold ${textColors.primary}`}>
              {sessions.find(s => s.session_id === selectedSessionId)?.label ?? 'Session'}
            </h2>
            <p className={`text-xs ${textColors.muted} font-mono truncate`}>{selectedSessionId}</p>
          </div>
          <div className="flex-1 overflow-hidden">
            <SessionConversationViewer sessionId={selectedSessionId} />
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
  )
}
