import { http, HttpResponse } from 'msw'
import type { Project, Task, ConfigurationDetailResponse, IntegrationTestResponse } from '../../lib/api'

// Mock data
const mockProjects: Project[] = [
  {
    id: 1,
    name: 'Test Project',
    details: 'This is a test project for development',
    current_status: 'Active',
    created_at: '2024-01-01T00:00:00Z',
  },
  {
    id: 2,
    name: 'Another Project',
    details: 'Another test project',
    current_status: 'Planning',
    created_at: '2024-01-02T00:00:00Z',
  },
]

const mockTasks: Task[] = [
  {
    id: 1,
    project_id: 1,
    title: 'Test Task',
    description: 'A test task for development',
    status: 'Designing',
    codebase_id: null,
    remote_task_id: null,
    conversation_id: null,
    implementation_plan: null,
    created_at: '2024-01-01T00:00:00Z',
  },
  {
    id: 2,
    project_id: 1,
    title: 'Another Task',
    description: 'Another test task',
    status: 'Planning',
    codebase_id: null,
    remote_task_id: 'PROJ-123',
    conversation_id: 'conv-456',
    implementation_plan: 'Implementation details here',
    created_at: '2024-01-02T00:00:00Z',
  },
]

const mockConfigurationResponse: ConfigurationDetailResponse = {
  key: 'integration.github.main',
  fields: [
    {
      name: 'api_token',
      type: 'string',
      required: true,
      description: 'GitHub API token',
      current_value: null,
      value_source: 'environment',
      is_secret: true,
      env_var_name: 'GITHUB_API_TOKEN',
      env_value_present: false,
    },
    {
      name: 'base_url',
      type: 'string',
      required: false,
      description: 'GitHub API base URL',
      current_value: 'https://api.github.com',
      value_source: 'default',
      is_secret: false,
      default_value: 'https://api.github.com',
      env_value_present: false,
    },
  ],
  validation_status: 'unconfigured',
  validation_errors: ['Missing required field: api_token'],
}

export const handlers = [
  // Projects endpoints
  http.get('*/api/projects', () => {
    return HttpResponse.json(mockProjects)
  }),

  http.post('*/api/projects', async ({ request }) => {
    const newProject = await request.json() as Omit<Project, 'id' | 'created_at'>
    const project: Project = {
      ...newProject,
      id: Date.now(),
      created_at: new Date().toISOString(),
    }
    return HttpResponse.json(project)
  }),

  http.get('*/api/projects/:id', ({ params }) => {
    const project = mockProjects.find(p => p.id === Number(params.id))
    if (!project) {
      return new HttpResponse(null, { status: 404 })
    }
    return HttpResponse.json(project)
  }),

  http.put('*/api/projects/:id', async ({ params, request }) => {
    const updates = await request.json() as Partial<Project>
    const project = mockProjects.find(p => p.id === Number(params.id))
    if (!project) {
      return new HttpResponse(null, { status: 404 })
    }
    const updatedProject = { ...project, ...updates }
    return HttpResponse.json(updatedProject)
  }),

  // Tasks endpoints
  http.get('*/api/projects/:projectId/tasks', ({ params }) => {
    const projectTasks = mockTasks.filter(t => t.project_id === Number(params.projectId))
    return HttpResponse.json(projectTasks)
  }),

  http.post('*/api/projects/:projectId/tasks', async ({ params, request }) => {
    const newTask = await request.json() as Omit<Task, 'id' | 'project_id' | 'created_at' | 'updated_at'>
    const task: Task = {
      ...newTask,
      id: Date.now(),
      project_id: Number(params.projectId),
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    }
    return HttpResponse.json(task)
  }),

  http.get('*/api/tasks/:id', ({ params }) => {
    const task = mockTasks.find(t => t.id === Number(params.id))
    if (!task) {
      return new HttpResponse(null, { status: 404 })
    }
    return HttpResponse.json(task)
  }),

  // Configuration endpoints
  http.get('*/api/configurations/:configKey/detail', ({ params }) => {
    // Return different mock data based on config key
    const configKey = params.configKey as string
    return HttpResponse.json({
      ...mockConfigurationResponse,
      key: configKey,
    })
  }),

  http.patch('*/api/configurations/:configKey/fields', async ({ params, request }) => {
    const updates = await request.json() as Record<string, any>
    return HttpResponse.json({
      ...mockConfigurationResponse,
      key: params.configKey as string,
      validation_status: 'valid' as const,
      validation_errors: [],
    })
  }),

  // Integration test endpoint
  http.post('*/api/settings/integrations/:integrationType/test', ({ params }) => {
    const response: IntegrationTestResponse = {
      success: true,
    }
    return HttpResponse.json(response)
  }),

  // Project Q&A endpoints
  http.get('*/api/projects/:projectId/qa/history', () => {
    return HttpResponse.json([
      {
        id: '1',
        content: 'What is the current status?',
        role: 'user' as const,
        timestamp: new Date().toISOString(),
      },
      {
        id: '2',
        content: 'The project is currently in active development.',
        role: 'assistant' as const,
        timestamp: new Date().toISOString(),
      },
    ])
  }),

  http.post('*/api/projects/:projectId/qa/ask', async ({ request }) => {
    const { message } = await request.json() as { message: string }
    return HttpResponse.json({
      response: `This is a mock response to: ${message}`,
    })
  }),
]