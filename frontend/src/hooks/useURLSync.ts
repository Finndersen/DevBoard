import { useEffect, useRef } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useUIStore } from '../stores/uiStore'
import type { ViewType } from '../stores/uiStore'

/**
 * Hook to synchronize URL with view state
 * - On URL change: Opens/switches to appropriate view
 * - On view switch: Updates URL
 */
export function useURLSync() {
  const location = useLocation()
  const navigate = useNavigate()
  const { navigateTo, switchTab, getActiveView, findViewByEntity } = useUIStore()
  const activeViewId = useUIStore(state => state.activeViewId)
  const shouldPushHistory = useUIStore(state => state.shouldPushHistory)

  // Track if we initiated the navigation to avoid pushing duplicate history entries
  const isNavigatingRef = useRef(false)

  // Parse URL to determine view type and entity ID
  const parseURL = (pathname: string): { type: ViewType; entityId: string; title: string } | null => {
    // Home
    if (pathname === '/') {
      return { type: 'home', entityId: 'main', title: 'Home' }
    }

    // List views
    if (pathname === '/projects') {
      return { type: 'projects-list', entityId: 'main', title: 'Projects' }
    }
    if (pathname === '/tasks') {
      return { type: 'tasks-list', entityId: 'main', title: 'Tasks' }
    }
    if (pathname === '/codebases') {
      return { type: 'codebases-list', entityId: 'main', title: 'Codebases' }
    }
    if (pathname === '/events') {
      return { type: 'events-list', entityId: 'main', title: 'Events' }
    }

    // Project detail
    const projectMatch = pathname.match(/^\/projects\/(\d+)$/)
    if (projectMatch) {
      return { type: 'project', entityId: projectMatch[1], title: `Project #${projectMatch[1]}` }
    }

    // Task detail
    const taskMatch = pathname.match(/^\/tasks\/(\d+)$/)
    if (taskMatch) {
      return { type: 'task', entityId: taskMatch[1], title: `Task #${taskMatch[1]}` }
    }

    // Codebase detail
    const codebaseMatch = pathname.match(/^\/codebases\/(\d+)$/)
    if (codebaseMatch) {
      return { type: 'codebase', entityId: codebaseMatch[1], title: `Codebase #${codebaseMatch[1]}` }
    }

    // Settings
    if (pathname === '/settings') {
      return { type: 'settings', entityId: 'main', title: 'Settings' }
    }

    // MCP Servers
    if (pathname === '/mcp-servers') {
      return { type: 'mcp-servers', entityId: 'main', title: 'MCP Servers' }
    }

    // Claude Code
    if (pathname === '/claude-code') {
      return { type: 'claude-code', entityId: 'main', title: 'Claude Code' }
    }

    return null
  }

  // Sync URL to views (URL changed -> open/switch view)
  useEffect(() => {
    // Skip if we initiated this navigation
    if (isNavigatingRef.current) {
      isNavigatingRef.current = false
      return
    }

    const viewInfo = parseURL(location.pathname)
    if (!viewInfo) return

    // Check if view already exists
    const existingView = findViewByEntity(viewInfo.type, viewInfo.entityId)
    if (existingView) {
      // Switch to existing view if not already active
      // Pass fromUrlSync=true to avoid setting shouldPushHistory (URL already changed)
      switchTab(existingView.id, { fromUrlSync: true })
    } else {
      // Open new view
      // Pass fromUrlSync=true to avoid setting shouldPushHistory (URL already changed)
      navigateTo(viewInfo, { fromUrlSync: true })
    }
  }, [location.pathname, navigateTo, switchTab, findViewByEntity])

  // Sync views to URL (active view changed -> update URL)
  useEffect(() => {
    const activeView = getActiveView()
    if (!activeView) return

    // Generate URL from active view (base path only, ignore query params)
    let targetPath = '/'

    switch (activeView.type) {
      case 'home':
        targetPath = '/'
        break
      case 'projects-list':
        targetPath = '/projects'
        break
      case 'tasks-list':
        targetPath = '/tasks'
        break
      case 'codebases-list':
        targetPath = '/codebases'
        break
      case 'project':
        targetPath = `/projects/${activeView.entityId}`
        break
      case 'task':
        targetPath = `/tasks/${activeView.entityId}`
        break
      case 'codebase':
        targetPath = `/codebases/${activeView.entityId}`
        break
      case 'settings':
        targetPath = '/settings'
        break
      case 'mcp-servers':
        targetPath = '/mcp-servers'
        break
      case 'claude-code':
        targetPath = '/claude-code'
        break
      case 'events-list':
        targetPath = '/events'
        break
    }

    // Only navigate if URL pathname needs to change (ignore query params here)
    // Query param changes (like tab switches within a project) are handled by the component itself
    if (location.pathname !== targetPath) {
      // Mark that we're initiating navigation
      isNavigatingRef.current = true

      // Determine if we should push or replace:
      // - Push for new views (shouldPushHistory = true) to create history entries
      // - Replace when already on the same view (shouldPushHistory = false) to avoid duplicates
      // Use the flag from the store which is set by navigateTo/switchTab
      navigate(targetPath, { replace: !shouldPushHistory })
    }
  }, [activeViewId, location.pathname, navigate, getActiveView, shouldPushHistory])
}
