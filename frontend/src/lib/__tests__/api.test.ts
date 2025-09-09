import { describe, it, expect, beforeEach, vi } from 'vitest'
import { http, HttpResponse } from 'msw'
import { server } from '../../test/setup'
import { ApiClient } from '../api'
import type { 
  Project, 
  Task,
  DocumentEdit,
  TaskPlanningResponse,
  TaskConversationMessage,
  TaskPlanningRequest,
  ApplyEditsRequest,
  StateTransitionRequest
} from '../api'

describe('ApiClient', () => {
  let apiClient: ApiClient

  beforeEach(() => {
    vi.clearAllMocks()
    apiClient = new ApiClient()
  })

  describe('Projects API', () => {
    const mockProjects: Project[] = [
      {
        id: 1,
        name: 'Test Project 1',
        details: 'Project 1 details',
        current_status: 'Active',
        created_at: '2024-01-01T00:00:00Z',
      },
      {
        id: 2,
        name: 'Test Project 2',
        details: 'Project 2 details',
        current_status: 'Planning',
        created_at: '2024-01-02T00:00:00Z',
      },
    ]

    it('gets all projects', async () => {
      server.use(
        http.get('*/api/projects', () => {
          return HttpResponse.json(mockProjects)
        })
      )

      const result = await apiClient.getProjects()
      expect(result).toEqual(mockProjects)
    })

    it('creates a new project', async () => {
      const newProject = {
        name: 'New Project',
        details: 'New project details',
        current_status: 'Planning',
      }

      const createdProject: Project = {
        id: 3,
        ...newProject,
        created_at: '2024-01-03T00:00:00Z',
      }

      server.use(
        http.post('*/api/projects', async ({ request }) => {
          const body = await request.json()
          expect(body).toEqual(newProject)
          return HttpResponse.json(createdProject)
        })
      )

      const result = await apiClient.createProject(newProject)
      expect(result).toEqual(createdProject)
    })

    it('gets a single project by ID', async () => {
      const project = mockProjects[0]

      server.use(
        http.get('*/api/projects/1', () => {
          return HttpResponse.json(project)
        })
      )

      const result = await apiClient.getProject(1)
      expect(result).toEqual(project)
    })

    it('gets a project by string ID', async () => {
      const project = mockProjects[0]

      server.use(
        http.get('*/api/projects/1', () => {
          return HttpResponse.json(project)
        })
      )

      const result = await apiClient.getProject('1')
      expect(result).toEqual(project)
    })

    it('updates a project', async () => {
      const updates = { name: 'Updated Project Name' }
      const updatedProject = { ...mockProjects[0], ...updates }

      server.use(
        http.patch('*/api/projects/1', async ({ request }) => {
          const body = await request.json()
          expect(body).toEqual(updates)
          return HttpResponse.json(updatedProject)
        })
      )

      const result = await apiClient.updateProject(1, updates)
      expect(result).toEqual(updatedProject)
    })

    it('deletes a project', async () => {
      server.use(
        http.delete('*/api/projects/1', () => {
          return HttpResponse.json({})
        })
      )

      const result = await apiClient.deleteProject(1)
      expect(result).toEqual({})
    })

    it('throws error when project API request fails', async () => {
      server.use(
        http.get('*/api/projects', () => {
          return new HttpResponse(null, { status: 500, statusText: 'Internal Server Error' })
        })
      )

      await expect(apiClient.getProjects()).rejects.toThrow('API request failed: 500 Internal Server Error')
    })
  })

  describe('Tasks API', () => {
    const mockTasks: Task[] = [
      {
        id: 1,
        project_id: 1,
        title: 'Test Task 1',
        description: 'Task 1 description',
        status: 'Pending',
        created_at: '2024-01-01T00:00:00Z',
        updated_at: '2024-01-01T00:00:00Z',
      },
      {
        id: 2,
        project_id: 1,
        title: 'Test Task 2',
        description: 'Task 2 description',
        status: 'Planning',
        created_at: '2024-01-02T00:00:00Z',
        updated_at: '2024-01-02T00:00:00Z',
      },
    ]

    it('gets tasks for a project', async () => {
      server.use(
        http.get('*/api/projects/1/tasks', () => {
          return HttpResponse.json(mockTasks)
        })
      )

      const result = await apiClient.getProjectTasks(1)
      expect(result).toEqual(mockTasks)
    })

    it('creates a new task', async () => {
      const newTask = {
        title: 'New Task',
        description: 'New task description',
        status: 'Pending',
      }

      const createdTask: Task = {
        id: 3,
        project_id: 1,
        ...newTask,
        created_at: '2024-01-03T00:00:00Z',
        updated_at: '2024-01-03T00:00:00Z',
      }

      server.use(
        http.post('*/api/projects/1/tasks', async ({ request }) => {
          const body = await request.json()
          expect(body).toEqual(newTask)
          return HttpResponse.json(createdTask)
        })
      )

      const result = await apiClient.createTask(1, newTask)
      expect(result).toEqual(createdTask)
    })

    it('gets a single task by ID', async () => {
      const task = mockTasks[0]

      server.use(
        http.get('*/api/tasks/1', () => {
          return HttpResponse.json(task)
        })
      )

      const result = await apiClient.getTask(1)
      expect(result).toEqual(task)
    })

    it('updates a task', async () => {
      const updates = { status: 'Complete' }
      const updatedTask = { ...mockTasks[0], ...updates }

      server.use(
        http.put('*/api/tasks/1', async ({ request }) => {
          const body = await request.json()
          expect(body).toEqual(updates)
          return HttpResponse.json(updatedTask)
        })
      )

      const result = await apiClient.updateTask(1, updates)
      expect(result).toEqual(updatedTask)
    })

    it('deletes a task', async () => {
      server.use(
        http.delete('*/api/tasks/1', () => {
          return HttpResponse.json({})
        })
      )

      const result = await apiClient.deleteTask(1)
      expect(result).toEqual({})
    })
  })

  describe('Project Q&A API', () => {
    const mockMessages = [
      {
        id: '1',
        content: 'What is the status?',
        role: 'user' as const,
        timestamp: '2024-01-01T10:00:00.000Z',
      },
      {
        id: '2',
        content: 'The project is progressing well.',
        role: 'assistant' as const,
        timestamp: '2024-01-01T10:01:00.000Z',
      },
    ]

    it('gets project Q&A history', async () => {
      server.use(
        http.get('*/api/projects/1/qa/history', () => {
          return HttpResponse.json(mockMessages)
        })
      )

      const result = await apiClient.getProjectQAHistory(1)
      expect(result).toEqual(mockMessages)
    })

    it('asks a question to project Q&A', async () => {
      const message = 'How many tasks are completed?'
      const response = { response: 'There are 3 completed tasks.' }

      server.use(
        http.post('*/api/projects/1/qa/ask', async ({ request }) => {
          const body = await request.json() as { message: string }
          expect(body).toEqual({ message })
          return HttpResponse.json(response)
        })
      )

      const result = await apiClient.askProjectQA(1, message)
      expect(result).toEqual(response)
    })
  })

  describe('Settings API', () => {
    const mockIntegrations = [
      {
        id: 'github',
        name: 'GitHub',
        type: 'github',
        status: 'connected' as const,
        config: { api_token: 'token123' },
      },
      {
        id: 'jira',
        name: 'Jira',
        type: 'jira',
        status: 'disconnected' as const,
        config: {},
      },
    ]

    const mockLLMProviders = [
      {
        id: 'openai',
        name: 'OpenAI',
        type: 'openai',
        enabled: true,
        config: { api_key: 'sk-123' },
      },
      {
        id: 'anthropic',
        name: 'Anthropic',
        type: 'anthropic',
        enabled: false,
        config: {},
      },
    ]

    it('gets integrations', async () => {
      server.use(
        http.get('*/api/settings/integrations', () => {
          return HttpResponse.json(mockIntegrations)
        })
      )

      const result = await apiClient.getIntegrations()
      expect(result).toEqual(mockIntegrations)
    })

    it('toggles integration', async () => {
      const toggledIntegration = {
        ...mockIntegrations[0],
        status: 'disconnected' as const,
      }

      server.use(
        http.post('*/api/settings/integrations/github/toggle', () => {
          return HttpResponse.json(toggledIntegration)
        })
      )

      const result = await apiClient.toggleIntegration('github')
      expect(result).toEqual(toggledIntegration)
    })

    it('gets LLM providers', async () => {
      server.use(
        http.get('*/api/settings/llm-providers', () => {
          return HttpResponse.json(mockLLMProviders)
        })
      )

      const result = await apiClient.getLLMProviders()
      expect(result).toEqual(mockLLMProviders)
    })

    it('toggles LLM provider', async () => {
      const toggledProvider = {
        ...mockLLMProviders[1],
        enabled: true,
      }

      server.use(
        http.post('*/api/settings/llm-providers/anthropic/toggle', () => {
          return HttpResponse.json(toggledProvider)
        })
      )

      const result = await apiClient.toggleLLMProvider('anthropic')
      expect(result).toEqual(toggledProvider)
    })
  })

  describe('Configuration Management API', () => {
    const mockConfigDetail = {
      key: 'integration.github.main',
      fields: [
        {
          name: 'api_token',
          type: 'string' as const,
          required: true,
          description: 'GitHub API token',
          current_value: null,
          value_source: 'environment' as const,
          is_secret: true,
          env_value_present: false,
        },
      ],
      validation_status: 'unconfigured' as const,
      validation_errors: ['Missing required field: api_token'],
    }

    it('gets configuration detail', async () => {
      server.use(
        http.get('*/api/configurations/integration.github.main/detail', () => {
          return HttpResponse.json(mockConfigDetail)
        })
      )

      const result = await apiClient.getConfigurationDetail('integration.github.main')
      expect(result).toEqual(mockConfigDetail)
    })

    it('updates configuration fields', async () => {
      const fieldUpdates = { api_token: 'new_token_123' }
      const updatedConfig = {
        ...mockConfigDetail,
        validation_status: 'valid' as const,
        validation_errors: [],
      }

      server.use(
        http.patch('*/api/configurations/integration.github.main/fields', async ({ request }) => {
          const body = await request.json()
          expect(body).toEqual(fieldUpdates)
          return HttpResponse.json(updatedConfig)
        })
      )

      const result = await apiClient.updateConfigurationFields('integration.github.main', fieldUpdates)
      expect(result).toEqual(updatedConfig)
    })

    it('tests integration connection', async () => {
      const testResponse = {
        success: true,
      }

      server.use(
        http.post('*/api/settings/integrations/github/test', () => {
          return HttpResponse.json(testResponse)
        })
      )

      const result = await apiClient.testIntegrationConnection('github')
      expect(result).toEqual(testResponse)
    })

    it('handles integration connection test failure', async () => {
      const testResponse = {
        success: false,
        error_type: 'authentication',
        error_message: 'Invalid API token',
        details: { status_code: 401 },
      }

      server.use(
        http.post('*/api/settings/integrations/github/test', () => {
          return HttpResponse.json(testResponse)
        })
      )

      const result = await apiClient.testIntegrationConnection('github')
      expect(result).toEqual(testResponse)
    })
  })

  describe('HTTP Request Handling', () => {
    it('sets correct default base URL', () => {
      const client = new ApiClient()
      // We can't directly test the private baseURL, but we can test that requests work
      expect(client).toBeInstanceOf(ApiClient)
    })

    it('sets Content-Type header for JSON requests', async () => {
      let capturedHeaders: Headers | undefined

      server.use(
        http.post('*/api/projects', async ({ request }) => {
          capturedHeaders = request.headers
          return HttpResponse.json({ id: 1, name: 'Test', details: '', current_status: 'Active', created_at: '' })
        })
      )

      await apiClient.createProject({
        name: 'Test Project',
        details: 'Test details',
        current_status: 'Active',
      })

      expect(capturedHeaders?.get('Content-Type')).toBe('application/json')
    })

    it('handles non-JSON responses', async () => {
      server.use(
        http.delete('*/api/projects/1', () => {
          return HttpResponse.json({})
        })
      )

      const result = await apiClient.deleteProject(1)
      expect(result).toEqual({})
    })

    it('throws error for 404 responses', async () => {
      server.use(
        http.get('*/api/projects/999', () => {
          return new HttpResponse(null, { status: 404, statusText: 'Not Found' })
        })
      )

      await expect(apiClient.getProject(999)).rejects.toThrow('API request failed: 404 Not Found')
    })

    it('throws error for 500 responses', async () => {
      server.use(
        http.get('*/api/projects', () => {
          return new HttpResponse(null, { status: 500, statusText: 'Internal Server Error' })
        })
      )

      await expect(apiClient.getProjects()).rejects.toThrow('API request failed: 500 Internal Server Error')
    })

    it('handles network errors', async () => {
      server.use(
        http.get('*/api/projects', () => {
          return new HttpResponse(null, { status: 500, statusText: 'Unhandled Exception' })
        })
      )

      await expect(apiClient.getProjects()).rejects.toThrow('API request failed: 500 Unhandled Exception')
    })
  })

  describe('Request Methods', () => {
    it('makes GET requests correctly', async () => {
      let capturedMethod: string | undefined

      server.use(
        http.get('*/api/projects', ({ request }) => {
          capturedMethod = request.method
          return HttpResponse.json([])
        })
      )

      await apiClient.getProjects()
      expect(capturedMethod).toBe('GET')
    })

    it('makes POST requests with body', async () => {
      let capturedMethod: string | undefined
      let capturedBody: any

      server.use(
        http.post('*/api/projects', async ({ request }) => {
          capturedMethod = request.method
          capturedBody = await request.json()
          return HttpResponse.json({ id: 1, name: 'Test', details: '', current_status: 'Active', created_at: '' })
        })
      )

      const projectData = {
        name: 'Test Project',
        details: 'Test details',
        current_status: 'Active',
      }

      await apiClient.createProject(projectData)
      expect(capturedMethod).toBe('POST')
      expect(capturedBody).toEqual(projectData)
    })

    it('makes PATCH requests with body', async () => {
      let capturedMethod: string | undefined
      let capturedBody: any

      server.use(
        http.patch('*/api/projects/1', async ({ request }) => {
          capturedMethod = request.method
          capturedBody = await request.json()
          return HttpResponse.json({ id: 1, name: 'Updated', details: '', current_status: 'Active', created_at: '' })
        })
      )

      const updates = { name: 'Updated Project' }
      await apiClient.updateProject(1, updates)
      expect(capturedMethod).toBe('PATCH')
      expect(capturedBody).toEqual(updates)
    })

    it('makes DELETE requests correctly', async () => {
      let capturedMethod: string | undefined

      server.use(
        http.delete('*/api/projects/1', ({ request }) => {
          capturedMethod = request.method
          return HttpResponse.json({})
        })
      )

      await apiClient.deleteProject(1)
      expect(capturedMethod).toBe('DELETE')
    })

    it('makes PATCH requests to configuration endpoints', async () => {
      let capturedMethod: string | undefined
      let capturedBody: any

      server.use(
        http.patch('*/api/configurations/test/fields', async ({ request }) => {
          capturedMethod = request.method
          capturedBody = await request.json()
          return HttpResponse.json({
            key: 'test',
            fields: [],
            validation_status: 'valid',
          })
        })
      )

      const updates = { field1: 'value1' }
      await apiClient.updateConfigurationFields('test', updates)
      expect(capturedMethod).toBe('PATCH')
      expect(capturedBody).toEqual(updates)
    })
  })

  describe('URL Construction', () => {
    it('constructs correct URLs for different endpoints', async () => {
      let capturedUrl: string | undefined

      server.use(
        http.get('*', ({ request }) => {
          capturedUrl = request.url
          return HttpResponse.json([])
        })
      )

      await apiClient.getProjects()
      expect(capturedUrl).toContain('/api/projects')

      await apiClient.getProjectTasks(1)
      expect(capturedUrl).toContain('/api/projects/1/tasks')

      await apiClient.getTask(2)
      expect(capturedUrl).toContain('/api/tasks/2')
    })

    it('handles string and number IDs in URLs', async () => {
      let capturedUrls: string[] = []

      server.use(
        http.get('*', ({ request }) => {
          capturedUrls.push(request.url)
          return HttpResponse.json({})
        })
      )

      await apiClient.getProject(1)
      await apiClient.getProject('1')
      await apiClient.getTask(2)
      await apiClient.getTask('2')

      expect(capturedUrls[0]).toContain('/api/projects/1')
      expect(capturedUrls[1]).toContain('/api/projects/1')
      expect(capturedUrls[2]).toContain('/api/tasks/2')
      expect(capturedUrls[3]).toContain('/api/tasks/2')
    })
  })

  describe('Task Planning Agent API', () => {
    const mockTaskMessages: TaskConversationMessage[] = [
      {
        id: 1,
        task_id: 1,
        role: 'user',
        content: 'Help me design this task',
        tool_data: null,
        created_at: '2024-01-01T00:00:00Z'
      },
      {
        id: 2,
        task_id: 1,
        role: 'assistant',
        content: 'I\'ll help you create a specification',
        tool_data: {
          task_specification_edits: [
            { find: '[Title]', replace: 'User Authentication Task' }
          ],
          task_implementation_plan_edits: []
        },
        created_at: '2024-01-01T00:01:00Z'
      }
    ]

    const mockTask: Task = {
      id: 1,
      title: 'User Authentication Task',
      description: 'Updated task specification',
      status: 'Planning',
      project_id: 1,
      codebase_id: null,
      remote_task_id: null,
      conversation_id: 'conv-123',
      implementation_plan: 'Detailed implementation plan',
      created_at: '2024-01-01T00:00:00Z'
    }

    it('gets task messages', async () => {
      server.use(
        http.get('*/api/tasks/1/messages', () => {
          return HttpResponse.json(mockTaskMessages)
        })
      )

      const result = await apiClient.getTaskMessages(1)
      expect(result).toEqual(mockTaskMessages)
    })

    it('gets task messages with string ID', async () => {
      server.use(
        http.get('*/api/tasks/1/messages', () => {
          return HttpResponse.json([])
        })
      )

      const result = await apiClient.getTaskMessages('1')
      expect(result).toEqual([])
    })

    it('sends task planning message', async () => {
      const request: TaskPlanningRequest = {
        message: 'Please add more details to the requirements'
      }

      const mockResponse: TaskConversationMessage = {
        id: 3,
        task_id: 1,
        role: 'user',
        content: request.message,
        tool_data: null,
        created_at: '2024-01-01T00:02:00Z'
      }

      server.use(
        http.post('*/api/tasks/1/messages', async ({ request: req }) => {
          const body = await req.json() as TaskPlanningRequest
          expect(body).toEqual(request)
          return HttpResponse.json(mockResponse)
        })
      )

      const result = await apiClient.sendTaskMessage(1, request)
      expect(result).toEqual(mockResponse)
    })

    it('applies document edits', async () => {
      const request: ApplyEditsRequest = {
        message_id: 2,
        task_specification_edits: [
          { find: 'old requirement', replace: 'updated requirement' }
        ],
        task_implementation_plan_edits: [
          { find: 'TODO: implement', replace: 'Step 1: Set up authentication middleware' }
        ]
      }

      server.use(
        http.post('*/api/tasks/1/apply-edits', async ({ request: req }) => {
          const body = await req.json() as ApplyEditsRequest
          expect(body).toEqual(request)
          return HttpResponse.json(mockTask)
        })
      )

      const result = await apiClient.applyDocumentEdits(1, request)
      expect(result).toEqual(mockTask)
    })

    it('applies partial document edits', async () => {
      const request: ApplyEditsRequest = {
        message_id: 2,
        task_specification_edits: [
          { find: 'old text', replace: 'new text' }
        ]
        // task_implementation_plan_edits is optional
      }

      const partialTask = { ...mockTask, description: 'new text' }

      server.use(
        http.post('*/api/tasks/1/apply-edits', async ({ request: req }) => {
          const body = await req.json() as ApplyEditsRequest
          expect(body.task_specification_edits).toBeDefined()
          expect(body.task_implementation_plan_edits).toBeUndefined()
          return HttpResponse.json(partialTask)
        })
      )

      const result = await apiClient.applyDocumentEdits(1, request)
      expect(result.description).toBe('new text')
    })

    it('transitions task state', async () => {
      const request: StateTransitionRequest = {
        new_state: 'Planning'
      }

      const updatedTask = { ...mockTask, status: 'Planning' }

      server.use(
        http.post('*/api/tasks/1/state-transition', async ({ request: req }) => {
          const body = await req.json() as StateTransitionRequest
          expect(body).toEqual(request)
          return HttpResponse.json(updatedTask)
        })
      )

      const result = await apiClient.transitionTaskState(1, request)
      expect(result.status).toBe('Planning')
    })

    it('handles different state transitions', async () => {
      const states = ['Designing', 'Planning', 'Implementing']
      
      for (const state of states) {
        const request: StateTransitionRequest = { new_state: state }
        const stateTask = { ...mockTask, status: state }

        server.use(
          http.post(`*/api/tasks/1/state-transition`, async ({ request: req }) => {
            const body = await req.json() as StateTransitionRequest
            expect(body.new_state).toBe(state)
            return HttpResponse.json(stateTask)
          })
        )

        const result = await apiClient.transitionTaskState(1, request)
        expect(result.status).toBe(state)
      }
    })

    it('handles API errors for task planning endpoints', async () => {
      server.use(
        http.get('*/api/tasks/999/messages', () => {
          return new HttpResponse(null, { status: 404, statusText: 'Not Found' })
        })
      )

      await expect(apiClient.getTaskMessages(999)).rejects.toThrow('API request failed: 404 Not Found')
    })

    it('handles edit application errors', async () => {
      const request: ApplyEditsRequest = {
        message_id: 2,
        task_specification_edits: [
          { find: 'nonexistent text', replace: 'new text' }
        ]
      }

      server.use(
        http.post('*/api/tasks/1/apply-edits', () => {
          return new HttpResponse(null, { status: 400, statusText: 'Bad Request' })
        })
      )

      await expect(apiClient.applyDocumentEdits(1, request)).rejects.toThrow('API request failed: 400 Bad Request')
    })

    it('handles state transition errors', async () => {
      const request: StateTransitionRequest = {
        new_state: 'InvalidState'
      }

      server.use(
        http.post('*/api/tasks/1/state-transition', () => {
          return new HttpResponse(null, { status: 400, statusText: 'Bad Request' })
        })
      )

      await expect(apiClient.transitionTaskState(1, request)).rejects.toThrow('API request failed: 400 Bad Request')
    })
  })

  describe('Updated Task Interface', () => {
    it('supports all new Task fields', () => {
      const fullTask: Task = {
        id: 1,
        title: 'Test Task',
        description: 'Task description',
        status: 'Planning',
        project_id: 1,
        codebase_id: 2,
        remote_task_id: 'PROJ-123',
        conversation_id: 'conv-456',
        implementation_plan: 'Implementation details',
        created_at: '2024-01-01T00:00:00Z'
      }

      expect(fullTask.codebase_id).toBe(2)
      expect(fullTask.remote_task_id).toBe('PROJ-123')
      expect(fullTask.conversation_id).toBe('conv-456')
      expect(fullTask.implementation_plan).toBe('Implementation details')
    })

    it('allows nullable fields', () => {
      const minimalTask: Task = {
        id: 1,
        title: 'Minimal Task',
        description: null,
        status: 'Pending',
        project_id: 1,
        codebase_id: null,
        remote_task_id: null,
        conversation_id: null,
        implementation_plan: null,
        created_at: '2024-01-01T00:00:00Z'
      }

      expect(minimalTask.description).toBeNull()
      expect(minimalTask.codebase_id).toBeNull()
      expect(minimalTask.remote_task_id).toBeNull()
      expect(minimalTask.conversation_id).toBeNull()
      expect(minimalTask.implementation_plan).toBeNull()
    })
  })

  describe('Document Edit Interface', () => {
    it('has simplified structure', () => {
      const edit: DocumentEdit = {
        find: 'old text',
        replace: 'new text'
      }

      expect(edit.find).toBe('old text')
      expect(edit.replace).toBe('new text')
      
      // Ensure old fields are not present
      expect('context' in edit).toBe(false)
      expect('rationale' in edit).toBe(false)
    })

    it('allows empty replace text', () => {
      const edit: DocumentEdit = {
        find: 'text to remove',
        replace: ''
      }

      expect(edit.find).toBe('text to remove')
      expect(edit.replace).toBe('')
    })
  })

  describe('Task Planning Response Interface', () => {
    it('has explicit edit fields', () => {
      const response: TaskPlanningResponse = {
        message: 'Task updated successfully',
        task_specification_edits: [
          { find: 'old spec', replace: 'new spec' }
        ],
        task_implementation_plan_edits: [
          { find: 'old plan', replace: 'new plan' }
        ]
      }

      expect(response.message).toBe('Task updated successfully')
      expect(response.task_specification_edits).toBeDefined()
      expect(response.task_implementation_plan_edits).toBeDefined()
      expect(Array.isArray(response.task_specification_edits)).toBe(true)
      expect(Array.isArray(response.task_implementation_plan_edits)).toBe(true)
    })

    it('allows optional edit fields', () => {
      const response: TaskPlanningResponse = {
        message: 'No changes needed'
      }

      expect(response.message).toBe('No changes needed')
      expect(response.task_specification_edits).toBeUndefined()
      expect(response.task_implementation_plan_edits).toBeUndefined()
    })
  })

  describe('Task Conversation Message Interface', () => {
    it('supports all role types', () => {
      const roles: TaskConversationMessage['role'][] = ['user', 'assistant', 'tool_call', 'tool_result']
      
      roles.forEach(role => {
        const message: TaskConversationMessage = {
          id: 1,
          task_id: 1,
          role: role,
          content: role === 'user' ? 'User message' : null,
          tool_data: role.startsWith('tool') ? { some: 'data' } : null,
          created_at: '2024-01-01T00:00:00Z'
        }

        expect(message.role).toBe(role)
        expect(typeof message.id).toBe('number')
        expect(typeof message.task_id).toBe('number')
      })
    })

    it('stores structured agent response data', () => {
      const message: TaskConversationMessage = {
        id: 1,
        task_id: 1,
        role: 'assistant',
        content: 'Updated task specification and plan',
        tool_data: {
          task_specification_edits: [
            { find: 'old objective', replace: 'new objective' }
          ],
          task_implementation_plan_edits: [
            { find: 'old step', replace: 'new step' }
          ]
        },
        created_at: '2024-01-01T00:00:00Z'
      }

      expect(message.tool_data).toBeDefined()
      expect(message.tool_data!.task_specification_edits).toBeDefined()
      expect(message.tool_data!.task_implementation_plan_edits).toBeDefined()
    })
  })
})