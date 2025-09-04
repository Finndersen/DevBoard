export interface Project {
  id: number
  name: string
  details: string
  current_status: string
  created_at: string
}

export interface Task {
  id: number
  title: string
  description: string
  status: string
  project_id: number
  created_at: string
  updated_at: string
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
      method: 'PUT',
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

  // Project Q&A
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
}

export const apiClient = new ApiClient()