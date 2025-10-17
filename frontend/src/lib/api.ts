export interface Project {
  id: number
  name: string
  specification: DocumentResponse
  description: string
  default_conversation_id: number | null
  created_at: string
}

export interface Task {
  id: number
  title: string
  status: string
  project_id: number
  codebase_id: number | null
  remote_task_id: string | null
  conversation_id: number
  created_at: string
  specification: DocumentResponse
  implementation_plan: DocumentResponse | null
}

export interface TaskCreate {
  title: string
  codebase_id: number | null
  remote_task_id: string | null
  specification_content: string | null
}

export interface DocumentResponse {
  id: number
  document_type: string
  content: string
  content_hash: string
  created_at: string
  updated_at: string
}

// New agent conversation interfaces matching backend schemas
export type MessageRole = 'user' | 'agent'

export interface ConversationMessage {
  role: MessageRole
  text_content: string
  timestamp: string
}


export interface ToolCallRequest {
  tool_call_id: string
  tool_name: string
  tool_args: string | Record<string, unknown> | null
}

export type PromptResponseType = 'message' | 'tool_request'

export interface PromptResponse {
  type: PromptResponseType
  message: ConversationMessage | null
  tool_requests: ToolCallRequest[] | null
}

export interface UserPrompt {
  message: string
}

export interface ToolApprovalDecision {
  approved: boolean
  feedback?: string
}

export interface ToolApprovalRequest {
  approvals: Record<string, ToolApprovalDecision>
}

// Main PendingApproval interface - generic structure to support any tool type
export interface PendingApproval {
  tool_call_id: string
  tool_name: string
  tool_args: Record<string, unknown> | null  // Generic tool arguments, structure depends on tool type
}

export interface StateTransitionRequest {
  new_state: string
}

export interface PromptActionRequest {
  action_key: string
}

export interface Integration {
  id: string
  name: string
  type: string
  status: 'connected' | 'disconnected'
  config: Record<string, unknown>
}

export interface LLMProvider {
  id: string
  name: string
  type: string
  enabled: boolean
  config: Record<string, unknown>
}

export interface Codebase {
  id: number
  name: string
  description: string
  repository_url: string | null
  local_path: string
}


export interface ArchitectureDocument {
  exists: boolean
  content: string | null
  content_hash: string | null
  file_path: string | null
  size_bytes: number | null
}

export interface ArchitectureUpdateRequest {
  content: string
  original_hash: string | null
}

export interface ArchitectureUpdateResponse {
  success: boolean
  content_hash: string | null
  message: string | null
  error_type?: string
  current_hash?: string
}

export interface ArchitectureGenerationRequest {
  preserve_user_sections?: boolean
}

export interface ArchitectureGenerationResponse {
  success: boolean
  file_path: string | null
  content: string | null
  error_message: string | null
  error_type: string | null
}

export interface ConfigurationFieldInfo {
  name: string
  type: 'string' | 'boolean' | 'integer' | 'number'
  required: boolean
  description?: string
  env_value?: unknown
  db_value?: unknown
  default_value?: unknown
  is_secret: boolean
  env_var_name?: string
  is_overridden: boolean
  effective_value: unknown
}

export interface ConfigurationDetailResponse {
  key: string
  fields: ConfigurationFieldInfo[]
  is_valid: boolean
  validation_errors?: string[]
}

export interface IntegrationTestResponse {
  success: boolean
  error_type?: string
  error_message?: string
  details?: Record<string, unknown>
}

export interface ModelInfo {
  id: string
  provider: string
  name: string
  model_type: 'reasoning' | 'fast'
}

export interface AgentEngineInfo {
  engine: string
  display_name: string
  description: string
}

export interface AgentEngineModelConfig {
  engine: string
  model_id: string
}

export interface AgentConfigurationResponse {
  agent_role: string
  config: AgentEngineModelConfig
  available_engines: AgentEngineInfo[]
}

export interface UpdateAgentConfigurationRequest {
  engine: string
  model_id: string
}

export interface AvailableModelsByEngineResponse {
  models_by_engine: Record<string, ModelInfo[]>
}

export interface UpdateConversationModelRequest {
  model_id: string
}

export interface ConversationResponse {
  id: number
  parent_entity_type: string
  parent_entity_id: number
  agent_role: string
  engine: string
  model_id: string
  is_active: boolean
  created_at: string
}

export class ApiClient {
  private readonly baseURL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

  private async request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    const url = `${this.baseURL}${endpoint}`
    const response = await fetch(url, {
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
      ...options,
    })

    if (!response.ok) {
      throw new Error(`API request failed: ${response.status} ${response.statusText}`)
    }

    return response.json()
  }

  // Projects
  async getProjects(): Promise<Project[]> {
    return this.request<Project[]>('/api/projects')
  }

  async createProject(project: Omit<Project, 'id' | 'created_at'>): Promise<Project> {
    return this.request<Project>('/api/projects', {
      method: 'POST',
      body: JSON.stringify(project),
    })
  }

  async getProject(id: number | string): Promise<Project> {
    return this.request<Project>(`/api/projects/${id}`)
  }

  async updateProject(id: number | string, project: Partial<Project>): Promise<Project> {
    return this.request<Project>(`/api/projects/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(project),
    })
  }

  async deleteProject(id: number | string): Promise<void> {
    return this.request<void>(`/api/projects/${id}`, { method: 'DELETE' })
  }

  // Tasks
  async getProjectTasks(projectId: number | string): Promise<Task[]> {
    return this.request<Task[]>(`/api/projects/${projectId}/tasks`)
  }

  async createTask(projectId: number | string, task: TaskCreate): Promise<Task> {
    return this.request<Task>(`/api/projects/${projectId}/tasks`, {
      method: 'POST',
      body: JSON.stringify(task),
    })
  }

  async getTask(id: number | string): Promise<Task> {
    return this.request<Task>(`/api/tasks/${id}`)
  }

  async updateTask(id: number | string, task: Partial<Task>): Promise<Task> {
    return this.request<Task>(`/api/tasks/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(task),
    })
  }

  async deleteTask(id: number | string): Promise<void> {
    return this.request<void>(`/api/tasks/${id}`, { method: 'DELETE' })
  }


  async transitionTaskState(taskId: number | string, request: StateTransitionRequest): Promise<Task> {
    return this.request<Task>(`/api/tasks/${taskId}/state-transition`, {
      method: 'POST',
      body: JSON.stringify(request),
    })
  }

  // Unified Conversation API
  async getConversation(conversationId: number | string): Promise<ConversationResponse> {
    return this.request<ConversationResponse>(`/api/conversations/${conversationId}`)
  }

  async getConversationMessages(conversationId: number | string): Promise<ConversationMessage[]> {
    return this.request<ConversationMessage[]>(`/api/conversations/${conversationId}/messages`)
  }

  async sendConversationMessage(conversationId: number | string, request: UserPrompt): Promise<PromptResponse> {
    return this.request<PromptResponse>(`/api/conversations/${conversationId}/messages`, {
      method: 'POST',
      body: JSON.stringify(request),
    })
  }

  async approveConversationTools(conversationId: number | string, request: ToolApprovalRequest): Promise<PromptResponse> {
    return this.request<PromptResponse>(`/api/conversations/${conversationId}/approve-tools`, {
      method: 'POST',
      body: JSON.stringify(request),
    })
  }

  async clearConversationMessages(conversationId: number | string): Promise<{ message: string; success: boolean }> {
    return this.request<{ message: string; success: boolean }>(`/api/conversations/${conversationId}/messages`, {
      method: 'DELETE',
    })
  }

  async sendPromptAction(conversationId: number | string, request: PromptActionRequest): Promise<PromptResponse> {
    return this.request<PromptResponse>(`/api/conversations/${conversationId}/prompt-action`, {
      method: 'POST',
      body: JSON.stringify(request),
    })
  }

  // Settings
  async getIntegrations(): Promise<Integration[]> {
    return this.request<Integration[]>('/api/settings/integrations')
  }

  async toggleIntegration(id: string): Promise<Integration> {
    return this.request<Integration>(`/api/settings/integrations/${id}/toggle`, {
      method: 'POST',
    })
  }

  async getLLMProviders(): Promise<LLMProvider[]> {
    return this.request<LLMProvider[]>('/api/settings/llm-providers')
  }

  async toggleLLMProvider(id: string): Promise<LLMProvider> {
    return this.request<LLMProvider>(`/api/settings/llm-providers/${id}/toggle`, {
      method: 'POST',
    })
  }

  // Configuration Management
  async listConfigurations(prefix: string): Promise<ConfigurationDetailResponse[]> {
    return this.request<ConfigurationDetailResponse[]>(`/api/configurations?prefix=${encodeURIComponent(prefix)}`)
  }
  
  async getConfigurationDetail(configKey: string): Promise<ConfigurationDetailResponse> {
    return this.request<ConfigurationDetailResponse>(`/api/configurations/${configKey}/detail`)
  }

  async updateConfigurationFields(configKey: string, fieldUpdates: Record<string, unknown>): Promise<ConfigurationDetailResponse> {
    return this.request<ConfigurationDetailResponse>(`/api/configurations/${configKey}/fields`, {
      method: 'PATCH',
      body: JSON.stringify(fieldUpdates),
    })
  }

  async testIntegrationConnection(integrationType: string): Promise<IntegrationTestResponse> {
    return this.request<IntegrationTestResponse>(`/api/settings/integrations/${integrationType}/test`, {
      method: 'POST',
    })
  }

  async getAgentConfiguration(agentRole: string): Promise<AgentConfigurationResponse> {
    return this.request<AgentConfigurationResponse>(`/api/agents/${agentRole}/configuration`)
  }

  async updateAgentConfiguration(agentRole: string, request: UpdateAgentConfigurationRequest): Promise<AgentConfigurationResponse> {
    return this.request<AgentConfigurationResponse>(`/api/agents/${agentRole}/configuration`, {
      method: 'PUT',
      body: JSON.stringify(request),
    })
  }

  async getAvailableModelsByEngine(): Promise<AvailableModelsByEngineResponse> {
    return this.request<AvailableModelsByEngineResponse>('/api/agents/available-models')
  }

  async updateConversationModel(conversationId: number | string, request: UpdateConversationModelRequest): Promise<{ conversation_id: number; agent_role: string; engine: string; model_id: string; updated_at: string }> {
    return this.request<{ conversation_id: number; agent_role: string; engine: string; model_id: string; updated_at: string }>(`/api/conversations/${conversationId}/model`, {
      method: 'PUT',
      body: JSON.stringify(request),
    })
  }

  // Codebases
  async getCodebases(): Promise<Codebase[]> {
    return this.request<Codebase[]>('/api/codebases')
  }

  async createCodebase(codebase: Omit<Codebase, 'id' | 'repository_url'>): Promise<Codebase> {
    return this.request<Codebase>('/api/codebases', {
      method: 'POST',
      body: JSON.stringify(codebase),
    })
  }

  async getCodebase(id: number | string): Promise<Codebase> {
    return this.request<Codebase>(`/api/codebases/${id}`)
  }

  async updateCodebase(id: number | string, codebase: Partial<Codebase>): Promise<Codebase> {
    return this.request<Codebase>(`/api/codebases/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(codebase),
    })
  }

  async deleteCodebase(id: number | string): Promise<void> {
    return this.request<void>(`/api/codebases/${id}`, { method: 'DELETE' })
  }

  // Architecture operations
  async getArchitectureDocument(codebaseId: number | string): Promise<ArchitectureDocument> {
    return this.request<ArchitectureDocument>(`/api/codebases/${codebaseId}/architecture_document/`)
  }

  // New update endpoint
  async updateArchitectureDocument(
    codebaseId: number | string, 
    request: ArchitectureUpdateRequest
  ): Promise<ArchitectureUpdateResponse> {
    return this.request<ArchitectureUpdateResponse>(
      `/api/codebases/${codebaseId}/architecture_document/`,
      {
        method: 'PUT',
        body: JSON.stringify(request),
      }
    )
  }

  async generateArchitecture(
    codebaseId: number | string, 
    options: ArchitectureGenerationRequest = {}
  ): Promise<ArchitectureGenerationResponse> {
    return this.request<ArchitectureGenerationResponse>(
      `/api/codebases/${codebaseId}/architecture_document/generate`,
      {
        method: 'POST',
        body: JSON.stringify(options),
      }
    )
  }
}

export const apiClient = new ApiClient()