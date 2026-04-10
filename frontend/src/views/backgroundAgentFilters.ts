import type { BackgroundAgent } from '../lib/api'

export type FilterType = 'all' | 'enabled' | 'disabled' | 'scheduled' | 'event-driven'

export function filterAgents(agents: BackgroundAgent[], filter: FilterType): BackgroundAgent[] {
  switch (filter) {
    case 'enabled':
      return agents.filter(a => a.enabled)
    case 'disabled':
      return agents.filter(a => !a.enabled)
    case 'scheduled':
      return agents.filter(a => a.schedule_triggers.length > 0)
    case 'event-driven':
      return agents.filter(a => a.event_triggers.length > 0)
    default:
      return agents
  }
}
