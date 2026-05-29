import { apiClient } from '../lib/api'
import type {
  BackgroundAgent,
  BackgroundAgentCreate,
  BackgroundAgentRun,
  BackgroundAgentRunStats,
  BackgroundAgentRunStatus,
  BackgroundAgentUpdate,
  ConversationResponse,
} from '../lib/api'
import { useApi, useMutation } from './useApi'

export function useBackgroundAgents(enabled?: boolean) {
  return useApi<BackgroundAgent[]>(() => apiClient.getBackgroundAgents(enabled))
}

export function useBackgroundAgent(id: number | string | null) {
  return useApi<BackgroundAgent>(
    () => apiClient.getBackgroundAgent(id!),
    { immediate: id !== null }
  )
}

export function useBackgroundAgentRuns(
  agentId: number | string | null,
  params?: { status?: BackgroundAgentRunStatus; limit?: number; offset?: number },
) {
  return useApi<BackgroundAgentRun[]>(
    () => apiClient.getBackgroundAgentRuns(agentId!, params),
    { immediate: agentId !== null }
  )
}

export function useBackgroundAgentRunStats(agentId: number | string | null) {
  return useApi<BackgroundAgentRunStats>(
    () => apiClient.getBackgroundAgentRunStats(agentId!),
    { immediate: agentId !== null }
  )
}

export function useBackgroundAgentRun(runId: number | string | null) {
  return useApi<BackgroundAgentRun>(
    () => apiClient.getBackgroundAgentRun(runId!),
    { immediate: runId !== null }
  )
}

export function useBackgroundAgentRunConversation(runId: number | string | null) {
  return useApi<ConversationResponse>(
    () => apiClient.getBackgroundAgentRunConversation(runId!),
    { immediate: runId !== null }
  )
}

export function useCreateBackgroundAgent() {
  return useMutation<BackgroundAgent, [BackgroundAgentCreate]>(
    (data) => apiClient.createBackgroundAgent(data),
  )
}

export function useUpdateBackgroundAgent() {
  return useMutation<BackgroundAgent, [number | string, BackgroundAgentUpdate]>(
    (id, data) => apiClient.updateBackgroundAgent(id, data),
  )
}

export function useDeleteBackgroundAgent() {
  return useMutation<void, [number | string]>(
    (id) => apiClient.deleteBackgroundAgent(id),
  )
}

export function useTriggerBackgroundAgent() {
  return useMutation<BackgroundAgentRun, [number | string, { input_message?: string | null } | undefined]>(
    (id, body) => apiClient.triggerBackgroundAgent(id, body),
  )
}
