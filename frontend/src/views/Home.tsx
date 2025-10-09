import { useEffect, useState } from 'react'
import { PlusIcon, FolderIcon, CodeBracketIcon, TrashIcon } from '@heroicons/react/24/outline'
import { useDataStore } from '../stores/dataStore'
import { useUIStore } from '../stores/uiStore'
import { useProjects, useCreateProject } from '../hooks'
import { useCodebases, useCreateCodebase, useDeleteCodebase } from '../hooks/useCodebases'
import type { Project, Codebase } from '../lib/api'
import { Button, Card, Modal, Input, Textarea, ErrorMessage } from '../components/ui'
import { loadingSpinner } from '../styles/designSystem'

export default function Home() {
  const { openTab } = useUIStore()
  const { fetchProjects, fetchCodebases } = useDataStore()

  // Projects
  const { data: projects, loading: projectsLoading, error: projectsError, refetch: refetchProjects } = useProjects()
  const { mutate: createProject, loading: creatingProject } = useCreateProject()
  const [showCreateProjectModal, setShowCreateProjectModal] = useState(false)
  const [newProject, setNewProject] = useState({
    name: '',
    description: '',
    specification: {
      id: 0,
      document_type: 'project_specification',
      content: '',
      content_hash: '',
      created_at: '',
      updated_at: ''
    }
  })

  // Codebases
  const { data: codebases, loading: codebasesLoading, error: codebasesError, refetch: refetchCodebases } = useCodebases()
  const { mutate: createCodebase, loading: creatingCodebase } = useCreateCodebase()
  const { mutate: deleteCodebase } = useDeleteCodebase()
  const [showCreateCodebaseModal, setShowCreateCodebaseModal] = useState(false)
  const [newCodebase, setNewCodebase] = useState({
    name: '',
    description: '',
    local_path: ''
  })

  useEffect(() => {
    fetchProjects()
    fetchCodebases()
  }, [fetchProjects, fetchCodebases])

  const handleOpenProject = (project: Project) => {
    openTab({
      type: 'project',
      entityId: String(project.id),
      title: project.name
    })
  }

  const handleOpenCodebase = (codebase: Codebase) => {
    openTab({
      type: 'codebase',
      entityId: String(codebase.id),
      title: codebase.name
    })
  }

  const handleCreateProject = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      const projectData = {
        name: newProject.name,
        description: newProject.description,
        specification: newProject.specification,
        default_conversation_id: null
      }
      await createProject(projectData)
      await refetchProjects()
      setShowCreateProjectModal(false)
      setNewProject({
        name: '',
        description: '',
        specification: {
          id: 0,
          document_type: 'project_specification',
          content: '',
          content_hash: '',
          created_at: '',
          updated_at: ''
        }
      })
    } catch (error) {
      console.error('Failed to create project:', error)
    }
  }

  const handleCreateCodebase = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      await createCodebase(newCodebase)
      await refetchCodebases()
      setShowCreateCodebaseModal(false)
      setNewCodebase({ name: '', description: '', local_path: '' })
    } catch (error) {
      console.error('Failed to create codebase:', error)
    }
  }

  const handleDeleteCodebase = async (codebaseId: number) => {
    if (!confirm('Are you sure you want to delete this codebase?')) return
    try {
      await deleteCodebase(codebaseId)
      await refetchCodebases()
    } catch (error) {
      console.error('Failed to delete codebase:', error)
    }
  }

  const isLoading = projectsLoading || codebasesLoading

  if (isLoading) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className={loadingSpinner}></div>
      </div>
    )
  }

  return (
    <div className="space-y-8">
      {/* Welcome Header */}
      <div>
        <h1 className="text-3xl font-bold text-gray-900 dark:text-white">
          Welcome to DevBoard
        </h1>
        <p className="mt-2 text-gray-600 dark:text-gray-400">
          Your developer command center for managing projects, tasks, and codebases
        </p>
      </div>

      {/* Projects Section */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <FolderIcon className="w-6 h-6 text-blue-600 dark:text-blue-400" />
            <h2 className="text-2xl font-bold text-gray-900 dark:text-white">
              Projects
            </h2>
            <span className="text-sm text-gray-500 dark:text-gray-400">
              ({projects?.length || 0})
            </span>
          </div>
          <Button onClick={() => setShowCreateProjectModal(true)} icon={<PlusIcon />}>
            New Project
          </Button>
        </div>

        {projectsError && (
          <ErrorMessage error={projectsError} retry={refetchProjects} className="mb-4" />
        )}

        {!projects || projects.length === 0 ? (
          <Card className="p-8 text-center">
            <FolderIcon className="mx-auto h-12 w-12 text-gray-400 mb-3" />
            <h3 className="text-sm font-medium text-gray-900 dark:text-white mb-2">No projects yet</h3>
            <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
              Get started by creating your first project
            </p>
            <Button onClick={() => setShowCreateProjectModal(true)} icon={<PlusIcon />}>
              Create Project
            </Button>
          </Card>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {projects.map((project) => (
              <Card
                key={project.id}
                className="p-4 hover:shadow-lg transition-shadow cursor-pointer"
                onClick={() => handleOpenProject(project)}
                hover
              >
                <div className="flex items-start justify-between mb-2">
                  <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                    {project.name}
                  </h3>
                </div>
                <p className="text-sm text-gray-600 dark:text-gray-400 line-clamp-2 mb-3">
                  {project.description}
                </p>
                <p className="text-xs text-gray-500 dark:text-gray-500">
                  Created {new Date(project.created_at).toLocaleDateString()}
                </p>
              </Card>
            ))}
          </div>
        )}
      </div>

      {/* Codebases Section */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <CodeBracketIcon className="w-6 h-6 text-green-600 dark:text-green-400" />
            <h2 className="text-2xl font-bold text-gray-900 dark:text-white">
              Codebases
            </h2>
            <span className="text-sm text-gray-500 dark:text-gray-400">
              ({codebases?.length || 0})
            </span>
          </div>
          <Button onClick={() => setShowCreateCodebaseModal(true)} icon={<PlusIcon />}>
            New Codebase
          </Button>
        </div>

        {codebasesError && (
          <ErrorMessage error={codebasesError} retry={refetchCodebases} className="mb-4" />
        )}

        {!codebases || codebases.length === 0 ? (
          <Card className="p-8 text-center">
            <CodeBracketIcon className="mx-auto h-12 w-12 text-gray-400 mb-3" />
            <h3 className="text-sm font-medium text-gray-900 dark:text-white mb-2">No codebases yet</h3>
            <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
              Add a codebase to track and manage your code
            </p>
            <Button onClick={() => setShowCreateCodebaseModal(true)} icon={<PlusIcon />}>
              Add Codebase
            </Button>
          </Card>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {codebases.map((codebase) => (
              <Card
                key={codebase.id}
                className="p-4 hover:shadow-lg transition-shadow"
                hover
              >
                <div className="flex items-start justify-between mb-2">
                  <h3
                    className="text-lg font-semibold text-gray-900 dark:text-white cursor-pointer hover:text-blue-600 dark:hover:text-blue-400"
                    onClick={() => handleOpenCodebase(codebase)}
                  >
                    {codebase.name}
                  </h3>
                  <button
                    onClick={() => handleDeleteCodebase(codebase.id)}
                    className="text-gray-400 hover:text-red-600 dark:hover:text-red-400"
                    title="Delete codebase"
                  >
                    <TrashIcon className="w-4 h-4" />
                  </button>
                </div>
                <p className="text-sm text-gray-600 dark:text-gray-400 line-clamp-2 mb-2">
                  {codebase.description}
                </p>
                <p className="text-xs text-gray-500 dark:text-gray-500 font-mono truncate">
                  {codebase.local_path}
                </p>
              </Card>
            ))}
          </div>
        )}
      </div>

      {/* Create Project Modal */}
      <Modal
        isOpen={showCreateProjectModal}
        onClose={() => setShowCreateProjectModal(false)}
        title="Create New Project"
      >
        <form onSubmit={handleCreateProject} className="space-y-4">
          <Input
            label="Name"
            value={newProject.name}
            onChange={(e) => setNewProject({ ...newProject, name: e.target.value })}
            required
            autoFocus
          />
          <Textarea
            label="Description"
            value={newProject.description}
            onChange={(e) => setNewProject({ ...newProject, description: e.target.value })}
            rows={3}
          />
          <div className="flex justify-end gap-2 pt-4">
            <Button
              type="button"
              onClick={() => setShowCreateProjectModal(false)}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={creatingProject || !newProject.name}
            >
              {creatingProject ? 'Creating...' : 'Create Project'}
            </Button>
          </div>
        </form>
      </Modal>

      {/* Create Codebase Modal */}
      <Modal
        isOpen={showCreateCodebaseModal}
        onClose={() => setShowCreateCodebaseModal(false)}
        title="Add New Codebase"
      >
        <form onSubmit={handleCreateCodebase} className="space-y-4">
          <Input
            label="Name"
            value={newCodebase.name}
            onChange={(e) => setNewCodebase({ ...newCodebase, name: e.target.value })}
            required
            autoFocus
          />
          <Textarea
            label="Description"
            value={newCodebase.description}
            onChange={(e) => setNewCodebase({ ...newCodebase, description: e.target.value })}
            rows={3}
          />
          <Input
            label="Local Path"
            value={newCodebase.local_path}
            onChange={(e) => setNewCodebase({ ...newCodebase, local_path: e.target.value })}
            placeholder="/path/to/your/codebase"
            required
          />
          <div className="flex justify-end gap-2 pt-4">
            <Button
              type="button"
              onClick={() => setShowCreateCodebaseModal(false)}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={creatingCodebase || !newCodebase.name || !newCodebase.local_path}
            >
              {creatingCodebase ? 'Adding...' : 'Add Codebase'}
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  )
}
