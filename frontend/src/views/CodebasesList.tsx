import { useEffect, useState } from 'react'
import { CodeBracketIcon, PlusIcon, TrashIcon } from '@heroicons/react/24/outline'
import { useDataStore } from '../stores/dataStore'
import { useUIStore } from '../stores/uiStore'
import { useCodebases, useDeleteCodebase } from '../hooks/useCodebases'
import type { Codebase } from '../lib/api'
import { Button, Card, ErrorMessage } from '../components/ui'
import CreateCodebaseModal from '../components/modals/CreateCodebaseModal'
import { loadingSpinner } from '../styles/designSystem'
import ViewHeader from '../components/layout/ViewHeader'

export default function CodebasesList() {
  const { navigateTo } = useUIStore()
  const { fetchCodebases } = useDataStore()

  const { data: codebases, loading, error, refetch } = useCodebases()
  const { mutate: deleteCodebase } = useDeleteCodebase()
  const [showCreateModal, setShowCreateModal] = useState(false)

  useEffect(() => {
    fetchCodebases()
  }, [fetchCodebases])

  const handleOpenCodebase = (codebase: Codebase) => {
    navigateTo({
      type: 'codebase',
      entityId: String(codebase.id),
      title: codebase.name
    })
  }

  const handleCodebaseCreated = async () => {
    await refetch()
    await fetchCodebases()
  }

  const handleDeleteCodebase = async (codebaseId: number) => {
    if (!confirm('Are you sure you want to delete this codebase?')) return
    try {
      await deleteCodebase(codebaseId)
      await refetch()
      await fetchCodebases()
    } catch (error) {
      console.error('Failed to delete codebase:', error)
    }
  }

  return (
    <div className="h-full flex flex-col overflow-hidden">
      <ViewHeader
        icon={CodeBracketIcon}
        iconColor="text-green-600 dark:text-green-400"
        title="Codebases"
        count={codebases?.length || 0}
        actions={
          <Button onClick={() => setShowCreateModal(true)} icon={<PlusIcon />}>
            New Codebase
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

      {!codebases || codebases.length === 0 ? (
        <Card className="p-8 text-center">
          <CodeBracketIcon className="mx-auto h-12 w-12 text-gray-400 mb-3" />
          <h3 className="text-sm font-medium text-gray-900 dark:text-white mb-2">No codebases yet</h3>
          <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
            Add a codebase to track and manage your code
          </p>
          <Button onClick={() => setShowCreateModal(true)} icon={<PlusIcon />}>
            Add Codebase
          </Button>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {codebases.map((codebase) => (
            <Card key={codebase.id} className="p-4 hover:shadow-lg transition-shadow" hover onClick={() => handleOpenCodebase(codebase)}>
              <div className="flex items-start justify-between mb-2">
                <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                  {codebase.name}
                </h3>
                <button
                  onClick={(e) => { e.stopPropagation(); handleDeleteCodebase(codebase.id) }}
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

      </>
      )}
      </div>

      <CreateCodebaseModal
        isOpen={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        onSuccess={handleCodebaseCreated}
      />
    </div>
  )
}
