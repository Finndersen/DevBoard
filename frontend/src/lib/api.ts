export interface Project {
  id: number
  name: string
  specification: string
  description: string
  created_at: string
}

export interface Task {
  id: number
  title: string
  description: string | null
  status: string
  project_id: number
  codebase_id: number | null
  remote_task_id: string | null
  conversation_id: string | null
  implementation_plan: string | null
  created_at: string
}

export interface DocumentEdit {
  find: string
  replace: string
}

// New agent conversation interfaces matching backend schemas
export type MessageRole = 'user' | 'agent'

export interface ConversationMessage {
  id: number
  role: MessageRole
  text_content: string
  timestamp: string
}

export interface ToolCallRequest {
  tool_call_id: string
  tool_name: string
  tool_args: string | Record<string, any> | null
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

// Updated PendingApproval interface for component compatibility
export interface PendingApproval {
  tool_call_id: string
  tool_name: string
  document_type: string | null
  edits: DocumentEdit[] | null
  diff_preview: string | null
  reasoning: string | null
}

// Legacy task planning interfaces (keep for TaskPlanningChat component)
export interface TaskPlanningResponse {
  message: string
  task_specification_edits?: DocumentEdit[]
  task_implementation_plan_edits?: DocumentEdit[]
}

export interface ConversationMessageResponse {
  id: number
  message_type: 'request' | 'response'
  text_content: string | null
  tool_calls: ToolCallInfo[] | null
  created_at: string
}

export interface ToolCallInfo {
  tool_call_id: string
  tool_name: string
  status: 'pending_approval' | 'approved' | 'denied'
  arguments: Record<string, any>
  preview: Record<string, any> | null
}

export interface ConversationResponse {
  messages: ConversationMessageResponse[]
  pending_approvals: PendingApproval[] | null
  conversation_complete: boolean
}

export interface MessageRequest {
  message: string
}

export interface TaskPlanningRequest {
  message: string
}

export interface ApplyEditsRequest {
  message_id: number
  task_specification_edits?: DocumentEdit[]
  task_implementation_plan_edits?: DocumentEdit[]
}

export interface StateTransitionRequest {
  new_state: string
}

export interface Message {
  id: string
  content: string
  role: 'user' | 'assistant'
  timestamp: Date
}

export interface Integration {
  id: string
  name: string
  type: string
  status: 'connected' | 'disconnected'
  config: Record<string, any>
}

export interface LLMProvider {
  id: string
  name: string
  type: string
  enabled: boolean
  config: Record<string, any>
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
  current_value?: any
  value_source?: 'environment' | 'database' | 'default'
  is_secret: boolean
  env_var_name?: string
  default_value?: any
  env_value_present: boolean
}

export interface ConfigurationDetailResponse {
  key: string
  fields: ConfigurationFieldInfo[]
  validation_status: 'valid' | 'invalid' | 'unconfigured'
  validation_errors?: string[]
}

export interface IntegrationTestResponse {
  success: boolean
  error_type?: string
  error_message?: string
  details?: Record<string, any>
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

  async createTask(projectId: number | string, task: Omit<Task, 'id' | 'project_id' | 'created_at' | 'updated_at'>): Promise<Task> {
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
      method: 'PUT',
      body: JSON.stringify(task),
    })
  }

  async deleteTask(id: number | string): Promise<void> {
    return this.request<void>(`/api/tasks/${id}`, { method: 'DELETE' })
  }

  // Task Planning Agent - New Deferred Tools API
  async sendTaskConversationMessage(taskId: number | string, request: MessageRequest): Promise<ConversationResponse> {
    return this.request<ConversationResponse>(`/api/tasks/${taskId}/conversation`, {
      method: 'POST',
      body: JSON.stringify(request),
    })
  }

  async approveTaskTools(taskId: number | string, request: ToolApprovalRequest): Promise<ConversationResponse> {
    return this.request<ConversationResponse>(`/api/tasks/${taskId}/conversation/approve-tools`, {
      method: 'POST',
      body: JSON.stringify(request),
    })
  }

  async transitionTaskState(taskId: number | string, request: StateTransitionRequest): Promise<Task> {
    return this.request<Task>(`/api/tasks/${taskId}/state-transition`, {
      method: 'POST',
      body: JSON.stringify(request),
    })
  }

  // Project Agent Conversation - New API
  async getProjectAgentMessages(projectId: number | string): Promise<ConversationMessage[]> {
    return this.request<ConversationMessage[]>(`/api/projects/${projectId}/agent/messages`)
  }

  async sendProjectAgentMessage(projectId: number | string, request: UserPrompt): Promise<PromptResponse> {
    return this.request<PromptResponse>(`/api/projects/${projectId}/agent/messages`, {
      method: 'POST',
      body: JSON.stringify(request),
    })
  }

  async approveProjectAgentTools(projectId: number | string, request: ToolApprovalRequest): Promise<PromptResponse> {
    return this.request<PromptResponse>(`/api/projects/${projectId}/agent/approve-tools`, {
      method: 'POST',
      body: JSON.stringify(request),
    })
  }

  // Project Q&A - Legacy API (keep for compatibility)
  async getProjectQAHistory(projectId: number | string): Promise<Message[]> {
    return this.request<Message[]>(`/api/projects/${projectId}/qa/history`)
  }

  async askProjectQA(projectId: number | string, message: string): Promise<{ response: string }> {
    return this.request<{ response: string }>(`/api/projects/${projectId}/qa/ask`, {
      method: 'POST',
      body: JSON.stringify({ message }),
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
  async getConfigurationDetail(configKey: string): Promise<ConfigurationDetailResponse> {
    return this.request<ConfigurationDetailResponse>(`/api/configurations/${configKey}/detail`)
  }

  async updateConfigurationFields(configKey: string, fieldUpdates: Record<string, any>): Promise<ConfigurationDetailResponse> {
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