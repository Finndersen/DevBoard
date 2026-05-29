import { useState, useEffect, useRef } from 'react'
import { apiClient } from '../lib/api'

const POLL_INTERVAL = 15000 // 15 seconds

export function useActiveAgentRuns() {
  const [hasAnyRunning, setHasAnyRunning] = useState(false)
  const [runningAgentIds, setRunningAgentIds] = useState<Set<number>>(new Set())
  const intervalRef = useRef<NodeJS.Timeout | null>(null)

  const poll = async () => {
    try {
      const agents = await apiClient.getBackgroundAgents()
      const running = new Set<number>()

      agents.forEach(agent => {
        if (agent.has_active_run) {
          running.add(agent.id)
        }
      })

      setRunningAgentIds(running)
      setHasAnyRunning(running.size > 0)
    } catch (error) {
      console.error('Failed to poll active agent runs:', error)
    }
  }

  useEffect(() => {
    // Initial poll
    poll()

    // Set up polling interval
    intervalRef.current = setInterval(poll, POLL_INTERVAL)

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current)
      }
    }
  }, [])

  return {
    hasAnyRunning,
    runningAgentIds,
  }
}
