import { useState } from 'react'
import { Link } from 'react-router-dom'
import { PlusIcon, FolderIcon, ChatBubbleLeftIcon } from '@heroicons/react/24/outline'
import { useProjects, useCreateProject } from '../hooks'
import { Button, Card, Modal, Input, Textarea, StatusBadge, ErrorMessage } from '../components/ui'
import { loadingSpinner, layouts, textColors } from '../styles/designSystem'

export default function ProjectDashboard() {
  const { data: projects, loading, error, refetch } = useProjects()
  const { mutate: createProject, loading: creating, error: createError } = useCreateProject()
  const [showCreateModal, setShowCreateModal] = useState(false)
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

  const handleCreateProject = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      await createProject(newProject)
      await refetch()
      setShowCreateModal(false)
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

  if (loading) {
    return (
      <div className={`${layouts.flexCenter} h-64`}>
        <div className={loadingSpinner}></div>
      </div>
    )
  }

  if (error) {
    return (
      <ErrorMessage error={error} retry={refetch} className="max-w-lg mx-auto mt-8" />
    )
  }

  return (
    <div>
      {/* Header */}
      <div className={`${layouts.flexBetween} mb-8`}>
        <div>
          <h1 className={`text-3xl font-bold ${textColors.primary}`}>Projects</h1>
          <p className={`${textColors.secondary} mt-2`}>
            Manage your development projects and AI-powered workflows
          </p>
        </div>
        <Button
          onClick={() => setShowCreateModal(true)}
          icon={<PlusIcon />}
        >
          New Project
        </Button>
      </div>

      {/* Projects Grid */}
      {!projects || projects.length === 0 ? (
        <div className="text-center py-12">
          <FolderIcon className="mx-auto h-12 w-12 text-gray-400" />
          <h3 className={`mt-2 text-sm font-medium ${textColors.primary}`}>No projects</h3>
          <p className={`mt-1 text-sm ${textColors.secondary}`}>
            Get started by creating a new project.
          </p>
          <div className="mt-6">
            <Button
              onClick={() => setShowCreateModal(true)}
              icon={<PlusIcon />}
            >
              New Project
            </Button>
          </div>
        </div>
      ) : (
        <div className={layouts.gridAuto}>
          {projects.map((project) => (
            <Card key={project.id} hover>
              <div className={`${layouts.flexBetween} mb-4`}>
                <h3 className={`text-lg font-semibold ${textColors.primary} truncate`}>
                  {project.name}
                </h3>
                <div className="flex-shrink-0">
                  <StatusBadge variant="info">Project</StatusBadge>
                </div>
              </div>
              
              <p className={`${textColors.secondary} text-sm mb-4 line-clamp-3`}>
                {project.description}
              </p>
              
              <div className={`${layouts.flexBetween}`}>
                <span className={`text-xs ${textColors.muted}`}>
                  Created {new Date(project.created_at).toLocaleDateString()}
                </span>
                <Link to={`/projects/${project.id}`}>
                  <Button variant="secondary" size="sm" icon={<ChatBubbleLeftIcon />}>
                    Open
                  </Button>
                </Link>
              </div>
            </Card>
          ))}
        </div>
      )}

      {/* Create Project Modal */}
      <Modal
        isOpen={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        title="Create New Project"
      >
        <form onSubmit={handleCreateProject}>
          {createError && (
            <ErrorMessage error={createError} className="mb-4" />
          )}
          
          <div className="space-y-4">
            <Input
              label="Project Name"
              type="text"
              required
              value={newProject.name}
              onChange={(e) => setNewProject({ ...newProject, name: e.target.value })}
              placeholder="Enter project name"
            />
            
            <Textarea
              label="Description"
              required
              value={newProject.description}
              onChange={(e) => setNewProject({ ...newProject, description: e.target.value })}
              rows={3}
              placeholder="Describe your project, its goals, and key features..."
            />
          </div>
          
          <div className="flex justify-end space-x-3 mt-6">
            <Button
              type="button"
              variant="secondary"
              onClick={() => setShowCreateModal(false)}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              loading={creating}
            >
              Create Project
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  )
}