import { useState, useCallback, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { PlusIcon, FolderIcon } from '@heroicons/react/24/outline'
import { useUIStore } from '../stores/uiStore'
import { useProjects, useCreateProject, useUpdateProject } from '../hooks'
import { apiClient } from '../lib/api'
import type { Project, CustomFieldDefinition } from '../lib/api'
import Alert from '../components/ui/Alert'
import { Button, Card, Modal, Input, Textarea, ErrorMessage } from '../components/ui'
import { loadingSpinner, textColors, projectColors, initiativeColors } from '../styles/designSystem'
import ViewHeader from '../components/layout/ViewHeader'
import { CustomFieldInputs } from '../components/common/CustomFieldInputs'

export default function ProjectsList() {
  const navigate = useNavigate()
  const { navigateTo } = useUIStore()

  const { data: activeProjects, loading: activeLoading, error: activeError, refetch: refetchActive } = useProjects()
  const { data: completeProjects, loading: completeLoading, refetch: refetchComplete } = useProjects({ complete: true })
  const { mutate: createProject, loading: creatingProject } = useCreateProject()
  const { mutate: updateProject } = useUpdateProject()

  const [showCreateModal, setShowCreateModal] = useState(false)
  const [presetParentId, setPresetParentId] = useState<number | null>(null)
  const [newProject, setNewProject] = useState({ name: '', description: '', parent_project_id: null as number | null })

  const [createProjectError, setCreateProjectError] = useState<string | null>(null)
  const [customFieldDefinitions, setCustomFieldDefinitions] = useState<CustomFieldDefinition[]>([])
  const [customFieldValues, setCustomFieldValues] = useState<Record<string, unknown>>({})
  const [customFieldsLoading, setCustomFieldsLoading] = useState(false)

  useEffect(() => {
    if (showCreateModal) {
      setCustomFieldsLoading(true)
      apiClient.getCustomFieldDefinitions('project')
        .then(fields => {
          setCustomFieldDefinitions(fields)
          const initialValues: Record<string, unknown> = {}
          fields.forEach(field => {
            initialValues[field.name] = field.type === 'boolean' ? false : ''
          })
          setCustomFieldValues(initialValues)
        })
        .catch(err => console.error('Failed to load project custom fields:', err))
        .finally(() => setCustomFieldsLoading(false))
    } else {
      setCustomFieldDefinitions([])
      setCustomFieldValues({})
    }
  }, [showCreateModal])

  const handleCustomFieldChange = useCallback((fieldName: string, value: unknown) => {
    setCustomFieldValues(prev => ({ ...prev, [fieldName]: value }))
  }, [])

  const areMandatoryFieldsFilled = useCallback(() => {
    const mandatoryFields = customFieldDefinitions.filter(f => f.mandatory)
    return mandatoryFields.every(field => {
      const value = customFieldValues[field.name]
      return value !== undefined && value !== null && value !== ''
    })
  }, [customFieldDefinitions, customFieldValues])

  const handleOpenProject = (project: Project) => {
    navigateTo({
      type: 'project',
      entityId: String(project.id),
      title: project.name
    })
  }

  const openCreateModal = (parentId: number | null = null) => {
    setPresetParentId(parentId)
    setNewProject({ name: '', description: '', parent_project_id: parentId })
    setCreateProjectError(null)
    setShowCreateModal(true)
  }

  const handleCloseModal = () => {
    setShowCreateModal(false)
    setPresetParentId(null)
    setCreateProjectError(null)
  }

  const handleCreateProject = async (e: React.FormEvent) => {
    e.preventDefault()
    setCreateProjectError(null)
    try {
      const customFields: Record<string, unknown> = {}
      Object.entries(customFieldValues).forEach(([name, value]) => {
        if (value !== '' && value !== null && value !== undefined) {
          customFields[name] = value
        }
      })

      const createdProject = await createProject({
        name: newProject.name,
        description: newProject.description,
        parent_project_id: newProject.parent_project_id ?? undefined,
        custom_fields: Object.keys(customFields).length > 0 ? customFields : null,
      })
      await Promise.all([refetchActive(), refetchComplete()])
      setShowCreateModal(false)
      navigate(`/projects/${createdProject.id}?tab=settings`)
    } catch (error) {
      console.error('Failed to create project:', error)
      setCreateProjectError(error instanceof Error ? error.message : 'Failed to create project')
    }
  }

  const handleToggleComplete = async (e: React.MouseEvent, project: Project) => {
    e.stopPropagation()
    try {
      await updateProject({ id: project.id, project: { complete: !project.complete } })
      await Promise.all([refetchActive(), refetchComplete()])
    } catch (error) {
      console.error('Failed to update project:', error)
    }
  }

  const loading = activeLoading || completeLoading
  const error = activeError

  // Group active initiatives by parent
  const topLevelActive = (activeProjects ?? []).filter(p => !p.parent_project_id)
  const initiativesByParent = (activeProjects ?? [])
    .filter(p => p.parent_project_id !== null)
    .reduce<Record<number, Project[]>>((acc, init) => {
      const parentId = init.parent_project_id!
      acc[parentId] = [...(acc[parentId] ?? []), init]
      return acc
    }, {})

  // Top-level projects available as parent choices in the create modal
  const topLevelForSelect = topLevelActive

  const totalActiveCount = (activeProjects ?? []).length
  const completeCount = (completeProjects ?? []).length

  return (
    <div className="h-full flex flex-col overflow-hidden">
      <ViewHeader
        icon={FolderIcon}
        title="Projects"
        count={totalActiveCount}
        actions={
          <Button onClick={() => openCreateModal(null)} icon={<PlusIcon />}>
            New Project
          </Button>
        }
      />

      <div className="flex-1 overflow-auto py-6 space-y-8">
        {loading ? (
          <div className="flex justify-center items-center h-64">
            <div className={loadingSpinner}></div>
          </div>
        ) : (
          <>
            {error && <ErrorMessage error={error} retry={refetchActive} className="mb-4" />}

            {totalActiveCount === 0 && completeCount === 0 ? (
              <Card className="p-8 text-center">
                <FolderIcon className="mx-auto h-12 w-12 text-gray-400 mb-3" />
                <h3 className={`text-sm font-medium ${textColors.primary} mb-2`}>No projects yet</h3>
                <p className={`text-sm ${textColors.secondary} mb-4`}>
                  Get started by creating your first project
                </p>
                <Button onClick={() => openCreateModal(null)} icon={<PlusIcon />}>
                  Create Project
                </Button>
              </Card>
            ) : (
              <div className="space-y-4">
                {topLevelActive.map((project) => (
                  <div key={project.id}>
                    <Card
                      className="p-4 cursor-pointer"
                      onClick={() => handleOpenProject(project)}
                      hover
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div className="flex items-center gap-2 min-w-0">
                          <span className={`${projectColors.icon} text-base shrink-0`} aria-hidden>◆</span>
                          <h3 className={`text-base font-semibold ${textColors.primary} truncate`}>
                            {project.name}
                          </h3>
                        </div>
                        <div className="flex items-center gap-2 shrink-0">
                          <Button
                            onClick={(e) => { e.stopPropagation(); openCreateModal(project.id) }}
                            icon={<PlusIcon />}
                          >
                            Initiative
                          </Button>
                          <Button
                            onClick={(e) => handleToggleComplete(e, project)}
                          >
                            Complete
                          </Button>
                        </div>
                      </div>
                      {project.description && (
                        <p className={`text-sm ${textColors.secondary} line-clamp-2 mt-1 ml-6`}>
                          {project.description}
                        </p>
                      )}
                    </Card>

                    {(initiativesByParent[project.id] ?? []).map((initiative) => (
                      <div key={initiative.id} className="ml-8 mt-2">
                        <Card
                          className="p-3 cursor-pointer"
                          onClick={() => handleOpenProject(initiative)}
                          hover
                        >
                          <div className="flex items-start justify-between gap-2">
                            <div className="flex items-center gap-2 min-w-0">
                              <span className={`${initiativeColors.icon} text-base shrink-0`} aria-hidden>▸</span>
                              <h3 className={`text-sm font-semibold ${textColors.primary} truncate`}>
                                {initiative.name}
                              </h3>
                            </div>
                            <Button
                              onClick={(e) => handleToggleComplete(e, initiative)}
                            >
                              Complete
                            </Button>
                          </div>
                          {initiative.description && (
                            <p className={`text-sm ${textColors.secondary} line-clamp-1 mt-1 ml-6`}>
                              {initiative.description}
                            </p>
                          )}
                        </Card>
                      </div>
                    ))}
                  </div>
                ))}
              </div>
            )}

            {completeCount > 0 && (
              <div className="space-y-2">
                <h3 className={`text-sm font-medium ${textColors.muted} uppercase tracking-wide`}>
                  Completed ({completeCount})
                </h3>
                {(completeProjects ?? []).map((project) => (
                  <Card
                    key={project.id}
                    className="p-3 opacity-60 cursor-pointer"
                    onClick={() => handleOpenProject(project)}
                    hover
                  >
                    <div className="flex items-center justify-between gap-2">
                      <div className="flex items-center gap-2 min-w-0">
                        <span
                          className={`${project.parent_project_id ? initiativeColors.icon : projectColors.icon} text-sm shrink-0`}
                          aria-hidden
                        >
                          {project.parent_project_id ? '▸' : '◆'}
                        </span>
                        <span className={`text-sm font-medium ${textColors.muted} truncate`}>
                          {project.name}
                        </span>
                        {project.parent_project_name && (
                          <span className={`text-xs ${textColors.muted} shrink-0`}>
                            ({project.parent_project_name})
                          </span>
                        )}
                      </div>
                      <Button
                        onClick={(e) => handleToggleComplete(e, project)}
                      >
                        Restore
                      </Button>
                    </div>
                  </Card>
                ))}
              </div>
            )}
          </>
        )}
      </div>

      <Modal
        isOpen={showCreateModal}
        onClose={handleCloseModal}
        title={presetParentId ? 'Create Initiative' : 'Create New Project'}
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
          {topLevelForSelect.length > 0 && (
            <div>
              <label className={`block text-sm font-medium ${textColors.primary} mb-1`}>
                Parent Project
              </label>
              <select
                className={`w-full rounded-md border px-3 py-2 text-sm ${textColors.primary} bg-white dark:bg-gray-700 border-gray-300 dark:border-gray-600 focus:outline-none focus:ring-2 focus:ring-blue-500`}
                value={newProject.parent_project_id ?? ''}
                onChange={(e) => setNewProject({
                  ...newProject,
                  parent_project_id: e.target.value ? Number(e.target.value) : null
                })}
              >
                <option value="">None (top-level project)</option>
                {topLevelForSelect.map(p => (
                  <option key={p.id} value={p.id}>{p.name}</option>
                ))}
              </select>
            </div>
          )}
          <CustomFieldInputs
            definitions={customFieldDefinitions}
            values={customFieldValues}
            onChange={handleCustomFieldChange}
            loading={customFieldsLoading}
          />
          {createProjectError && <Alert variant="error">{createProjectError}</Alert>}
          <div className="flex justify-end gap-2 pt-4">
            <Button type="button" onClick={handleCloseModal}>
              Cancel
            </Button>
            <Button type="submit" disabled={creatingProject || !newProject.name || !areMandatoryFieldsFilled()}>
              {creatingProject ? 'Creating...' : (presetParentId ? 'Create Initiative' : 'Create Project')}
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  )
}
