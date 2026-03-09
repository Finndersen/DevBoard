import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { PlusIcon, FolderIcon } from '@heroicons/react/24/outline'
import { useUIStore } from '../stores/uiStore'
import { useProjects, useCreateProject } from '../hooks'
import type { Project } from '../lib/api'
import { Button, Card, Modal, Input, Textarea, ErrorMessage } from '../components/ui'
import { loadingSpinner } from '../styles/designSystem'
import ViewHeader from '../components/layout/ViewHeader'

export default function ProjectsList() {
  const navigate = useNavigate()
  const { openTab } = useUIStore()

  const { data: projects, loading, error, refetch } = useProjects()
  const { mutate: createProject, loading: creatingProject } = useCreateProject()
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [newProject, setNewProject] = useState({ name: '', description: '' })

  const handleOpenProject = (project: Project) => {
    openTab({
      type: 'project',
      entityId: String(project.id),
      title: project.name
    })
  }

  const handleCreateProject = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      const createdProject = await createProject({
        name: newProject.name,
        description: newProject.description,
        specification: {
          id: 0,
          document_type: 'project_specification',
          content: '',
          content_hash: '',
          created_at: '',
          updated_at: ''
        },
        default_conversation_id: null
      })
      await refetch()
      setShowCreateModal(false)
      setNewProject({ name: '', description: '' })
      navigate(`/projects/${createdProject.id}?tab=settings`)
    } catch (error) {
      console.error('Failed to create project:', error)
    }
  }

  return (
    <div className="h-full flex flex-col overflow-hidden">
      <ViewHeader
        icon={FolderIcon}
        title="Projects"
        count={projects?.length || 0}
        actions={
          <Button onClick={() => setShowCreateModal(true)} icon={<PlusIcon />}>
            New Project
          </Button>
        }
      />

      <div className="flex-1 overflow-auto py-6 space-y-6">
      {loading ? (
        <div className="flex justify-center items-center h-64">
          <div className={loadingSpinner}></div>
        </div>
      ) : (
      <>
      {error && <ErrorMessage error={error} retry={refetch} className="mb-4" />}

      {!projects || projects.length === 0 ? (
        <Card className="p-8 text-center">
          <FolderIcon className="mx-auto h-12 w-12 text-gray-400 mb-3" />
          <h3 className="text-sm font-medium text-gray-900 dark:text-white mb-2">No projects yet</h3>
          <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
            Get started by creating your first project
          </p>
          <Button onClick={() => setShowCreateModal(true)} icon={<PlusIcon />}>
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
              <p className="text-sm text-gray-600 dark:text-gray-400 line-clamp-2">
                {project.description}
              </p>
            </Card>
          ))}
        </div>
      )}
      </>
      )}
      </div>

      <Modal
        isOpen={showCreateModal}
        onClose={() => setShowCreateModal(false)}
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
            <Button type="button" onClick={() => setShowCreateModal(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={creatingProject || !newProject.name}>
              {creatingProject ? 'Creating...' : 'Create Project'}
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  )

}
