import { useState, useEffect } from 'react'
import { FolderIcon, PlusIcon, PencilIcon, CheckIcon, XMarkIcon, TrashIcon, DocumentIcon, SparklesIcon } from '@heroicons/react/24/outline'
import ReactMarkdown from 'react-markdown'
import { apiClient } from '../lib/api'
import type { Codebase, ArchitectureDocument } from '../lib/api'

export default function Codebases() {
  const [codebases, setCodebases] = useState<Codebase[]>([])
  const [selectedCodebase, setSelectedCodebase] = useState<Codebase | null>(null)
  const [isEditing, setIsEditing] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showCreateModal, setShowCreateModal] = useState(false)
  
  const [editForm, setEditForm] = useState({
    name: '',
    description: '',
    local_path: ''
  })

  // Architecture-related state
  const [architectureDocument, setArchitectureDocument] = useState<ArchitectureDocument | null>(null)
  const [loadingArchitecture, setLoadingArchitecture] = useState(false)
  const [generatingArchitecture, setGeneratingArchitecture] = useState(false)
  const [architectureError, setArchitectureError] = useState<string | null>(null)
  const [isEditingArchitecture, setIsEditingArchitecture] = useState(false)
  const [editedArchitectureContent, setEditedArchitectureContent] = useState('')
  const [originalContentHash, setOriginalContentHash] = useState<string | null>(null)

  useEffect(() => {
    fetchCodebases()
  }, [])

  useEffect(() => {
    if (selectedCodebase) {
      fetchArchitectureDocument()
    } else {
      setArchitectureDocument(null)
    }
  }, [selectedCodebase])

  const fetchCodebases = async () => {
    try {
      setLoading(true)
      const data = await apiClient.getCodebases()
      setCodebases(data)
      if (data.length > 0 && !selectedCodebase) {
        setSelectedCodebase(data[0])
      }
      setError(null)
    } catch (err) {
      setError('Failed to fetch codebases')
      console.error('Failed to fetch codebases:', err)
    } finally {
      setLoading(false)
    }
  }

  const handleCreateCodebase = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      setLoading(true)
      const newCodebase = await apiClient.createCodebase(editForm)
      setCodebases([...codebases, newCodebase])
      setSelectedCodebase(newCodebase)
      setShowCreateModal(false)
      setEditForm({ name: '', description: '', local_path: '' })
      setError(null)
    } catch (err) {
      setError('Failed to create codebase')
      console.error('Failed to create codebase:', err)
    } finally {
      setLoading(false)
    }
  }

  const handleUpdateCodebase = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!selectedCodebase) return
    
    try {
      setLoading(true)
      const updatedCodebase = await apiClient.updateCodebase(selectedCodebase.id, editForm)
      setCodebases(codebases.map(cb => cb.id === selectedCodebase.id ? updatedCodebase : cb))
      setSelectedCodebase(updatedCodebase)
      setIsEditing(false)
      setError(null)
    } catch (err) {
      setError('Failed to update codebase')
      console.error('Failed to update codebase:', err)
    } finally {
      setLoading(false)
    }
  }

  const handleDeleteCodebase = async (codebase: Codebase) => {
    if (!confirm(`Are you sure you want to delete "${codebase.name}"?`)) {
      return
    }
    
    try {
      setLoading(true)
      await apiClient.deleteCodebase(codebase.id)
      const newCodebases = codebases.filter(cb => cb.id !== codebase.id)
      setCodebases(newCodebases)
      setSelectedCodebase(newCodebases[0] || null)
      setIsEditing(false)
      setError(null)
    } catch (err) {
      setError('Failed to delete codebase')
      console.error('Failed to delete codebase:', err)
    } finally {
      setLoading(false)
    }
  }

  const handleStartEdit = () => {
    if (selectedCodebase) {
      setEditForm({
        name: selectedCodebase.name,
        description: selectedCodebase.description,
        local_path: selectedCodebase.local_path
      })
      setIsEditing(true)
    }
  }

  const handleCancelEdit = () => {
    setIsEditing(false)
    setEditForm({ name: '', description: '', local_path: '' })
  }

  const handleStartCreate = () => {
    setEditForm({ name: '', description: '', local_path: '' })
    setShowCreateModal(true)
  }

  // Architecture-related functions
  const fetchArchitectureDocument = async () => {
    if (!selectedCodebase) return
    
    try {
      setLoadingArchitecture(true)
      const document = await apiClient.getArchitectureDocument(selectedCodebase.id)
      setArchitectureDocument(document)
      setArchitectureError(null)
    } catch (err) {
      setArchitectureError('Failed to fetch architecture document')
      console.error('Failed to fetch architecture document:', err)
    } finally {
      setLoadingArchitecture(false)
    }
  }

  const handleGenerateArchitecture = async () => {
    if (!selectedCodebase) return
    
    try {
      setGeneratingArchitecture(true)
      const result = await apiClient.generateArchitecture(selectedCodebase.id)
      
      if (result.success) {
        // Refresh architecture document
        await fetchArchitectureDocument()
        setArchitectureError(null)
      } else {
        setArchitectureError(result.error_message || 'Failed to generate architecture document')
      }
    } catch (err) {
      setArchitectureError('Failed to generate architecture document')
      console.error('Failed to generate architecture:', err)
    } finally {
      setGeneratingArchitecture(false)
    }
  }

  const handleSaveArchitecture = async () => {
    if (!selectedCodebase || editedArchitectureContent === undefined) return
    
    try {
      setLoading(true)
      const result = await apiClient.updateArchitectureDocument(selectedCodebase.id, {
        content: editedArchitectureContent,
        original_hash: originalContentHash
      })
      
      if (result.success) {
        // Update local state with new content and hash
        setArchitectureDocument({
          exists: true,
          content: editedArchitectureContent,
          content_hash: result.content_hash,
          file_path: architectureDocument?.file_path || null,
          size_bytes: editedArchitectureContent.length
        })
        setIsEditingArchitecture(false)
        setArchitectureError(null)
      }
    } catch (err: any) {
      // Check if it's a conflict error
      if (err.message?.includes('409')) {
        // Parse the error detail from the API response
        try {
          const errorDetail = JSON.parse(err.message.split('409 Conflict: ')[1])
          setArchitectureError(errorDetail.message || 'Document has been modified by another process')
          // Update the original hash for retry
          if (errorDetail.current_hash) {
            setOriginalContentHash(errorDetail.current_hash)
          }
        } catch {
          setArchitectureError('The architecture document has been modified by another process. Please review the changes and try again.')
        }
      } else {
        setArchitectureError('Failed to save architecture document')
        console.error('Failed to save architecture:', err)
      }
    } finally {
      setLoading(false)
    }
  }

  if (loading && codebases.length === 0) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
      </div>
    )
  }

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold text-gray-900 dark:text-white">Codebases</h1>
          <p className="text-gray-600 dark:text-gray-400 mt-2">
            Manage your local code repositories and development environments
          </p>
        </div>
        <button
          onClick={handleStartCreate}
          className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
        >
          <PlusIcon className="w-4 h-4 mr-2" />
          New Codebase
        </button>
      </div>

      {error && (
        <div className="mb-6 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-md p-4">
          <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
        </div>
      )}

      {/* Codebase Selection Dropdown */}
      <div className="mb-6">
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
          Select Codebase
        </label>
        {codebases.length === 0 ? (
          <div className="text-center py-8">
            <FolderIcon className="mx-auto h-12 w-12 text-gray-400 mb-4" />
            <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-2">No codebases</h3>
            <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
              Get started by adding your first codebase
            </p>
          </div>
        ) : (
          <select
            value={selectedCodebase?.id || ''}
            onChange={(e) => {
              const codebaseId = parseInt(e.target.value)
              const codebase = codebases.find(cb => cb.id === codebaseId)
              setSelectedCodebase(codebase || null)
              setIsEditing(false)
              setIsEditingArchitecture(false)
            }}
            className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white"
          >
            <option value="" className="text-gray-900 dark:text-white">Choose a codebase...</option>
            {codebases.map((codebase) => (
              <option key={codebase.id} value={codebase.id} className="text-gray-900 dark:text-white">
                {codebase.name} - {codebase.local_path}
              </option>
            ))}
          </select>
        )}
      </div>

      {/* Codebase Details */}
      <div className="w-full">
          {selectedCodebase ? (
            <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700">
              <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-700">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="text-lg font-medium text-gray-900 dark:text-white">
                      {isEditing ? 'Edit Codebase' : selectedCodebase.name}
                    </h3>
                    <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
                      {isEditing ? 'Update codebase details' : selectedCodebase.local_path}
                    </p>
                  </div>
                  {!isEditing && (
                    <div className="flex items-center space-x-2">
                      <button
                        onClick={handleStartEdit}
                        className="inline-flex items-center px-3 py-1.5 text-sm font-medium text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-md hover:bg-gray-50 dark:hover:bg-gray-600 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
                      >
                        <PencilIcon className="w-4 h-4 mr-1" />
                        Edit
                      </button>
                      <button
                        onClick={() => handleDeleteCodebase(selectedCodebase)}
                        className="inline-flex items-center px-3 py-1.5 text-sm font-medium text-red-600 dark:text-red-400 bg-white dark:bg-gray-700 border border-red-300 dark:border-red-600 rounded-md hover:bg-red-50 dark:hover:bg-red-900/20 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500"
                      >
                        <TrashIcon className="w-4 h-4 mr-1" />
                        Delete
                      </button>
                    </div>
                  )}
                </div>
              </div>

              <div className="p-6">
                {isEditing ? (
                  <form onSubmit={handleUpdateCodebase} className="space-y-6">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                        Name *
                      </label>
                      <input
                        type="text"
                        required
                        value={editForm.name}
                        onChange={(e) => setEditForm({ ...editForm, name: e.target.value })}
                        className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white"
                      />
                    </div>
                    
                    <div>
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                        Description *
                      </label>
                      <textarea
                        required
                        value={editForm.description}
                        onChange={(e) => setEditForm({ ...editForm, description: e.target.value })}
                        rows={6}
                        className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white font-mono text-sm"
                        placeholder="Enter description in Markdown format..."
                      />
                      <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                        You can use Markdown formatting
                      </p>
                    </div>
                    
                    <div>
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                        Local Path *
                      </label>
                      <input
                        type="text"
                        required
                        value={editForm.local_path}
                        onChange={(e) => setEditForm({ ...editForm, local_path: e.target.value })}
                        className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white"
                      />
                    </div>
                    
                    <div className="flex justify-end space-x-3">
                      <button
                        type="button"
                        onClick={handleCancelEdit}
                        className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-md hover:bg-gray-50 dark:hover:bg-gray-600 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
                      >
                        Cancel
                      </button>
                      <button
                        type="submit"
                        disabled={loading}
                        className="px-4 py-2 text-sm font-medium text-white bg-blue-600 border border-transparent rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50"
                      >
                        {loading ? 'Saving...' : 'Save Changes'}
                      </button>
                    </div>
                  </form>
                ) : (
                  <div className="space-y-6">
                    <div>
                      <h4 className="text-sm font-medium text-gray-900 dark:text-white mb-3">Description</h4>
                      <div className="prose prose-sm dark:prose-invert max-w-none text-left">
                        <ReactMarkdown>{selectedCodebase.description}</ReactMarkdown>
                      </div>
                    </div>
                    
                    <div>
                      <h4 className="text-sm font-medium text-gray-900 dark:text-white mb-3">Local Path</h4>
                      <code className="px-3 py-2 bg-gray-100 dark:bg-gray-700 text-gray-800 dark:text-gray-200 rounded-md text-sm block">
                        {selectedCodebase.local_path}
                      </code>
                    </div>
                    
                    {selectedCodebase.repository_url && (
                      <div>
                        <h4 className="text-sm font-medium text-gray-900 dark:text-white mb-3">Repository URL</h4>
                        <a
                          href={selectedCodebase.repository_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-blue-600 dark:text-blue-400 hover:underline text-sm break-all"
                        >
                          {selectedCodebase.repository_url}
                        </a>
                      </div>
                    )}

                    {/* Architecture Documentation Section */}
                    <div>
                      <div className="flex items-center justify-between mb-3">
                        <h4 className="text-sm font-medium text-gray-900 dark:text-white">Architecture Documentation</h4>
                        <div className="flex items-center space-x-2">
                          {architectureDocument?.content && !isEditingArchitecture && (
                            <button
                              onClick={() => {
                                setIsEditingArchitecture(true)
                                setEditedArchitectureContent(architectureDocument.content || '')
                                setOriginalContentHash(architectureDocument.content_hash)
                              }}
                              className="inline-flex items-center px-2 py-1 text-xs font-medium text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded hover:bg-gray-50 dark:hover:bg-gray-600 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
                            >
                              <PencilIcon className="w-3 h-3 mr-1" />
                              Edit
                            </button>
                          )}
                          {isEditingArchitecture && (
                            <>
                              <button
                                onClick={handleSaveArchitecture}
                                disabled={loading}
                                className="inline-flex items-center px-2 py-1 text-xs font-medium text-white bg-green-600 border border-transparent rounded hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-green-500 disabled:opacity-50"
                              >
                                <CheckIcon className="w-3 h-3 mr-1" />
                                {loading ? 'Saving...' : 'Save'}
                              </button>
                              <button
                                onClick={() => {
                                  setIsEditingArchitecture(false)
                                  setEditedArchitectureContent('')
                                }}
                                className="inline-flex items-center px-2 py-1 text-xs font-medium text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded hover:bg-gray-50 dark:hover:bg-gray-600 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
                              >
                                <XMarkIcon className="w-3 h-3 mr-1" />
                                Cancel
                              </button>
                            </>
                          )}
                          <button
                            onClick={handleGenerateArchitecture}
                            disabled={generatingArchitecture || isEditingArchitecture}
                            className="inline-flex items-center px-2 py-1 text-xs font-medium text-white bg-blue-600 border border-transparent rounded hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50"
                          >
                            <SparklesIcon className="w-3 h-3 mr-1" />
                            {generatingArchitecture ? 'Generating...' : architectureDocument?.exists ? 'Regenerate' : 'Generate'}
                          </button>
                        </div>
                      </div>

                      {architectureError && (
                        <div className="mb-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-md p-3">
                          <p className="text-sm text-red-600 dark:text-red-400">{architectureError}</p>
                        </div>
                      )}

                      {loadingArchitecture && !architectureDocument && (
                        <div className="flex items-center justify-center py-8 text-gray-400 dark:text-gray-500">
                          <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-600 mr-3"></div>
                          Loading architecture document...
                        </div>
                      )}

                      {architectureDocument && !loadingArchitecture && (
                        <>
                          {architectureDocument.exists ? (
                            <div>
                              <div className="flex items-center text-sm text-green-600 dark:text-green-400 mb-3">
                                <DocumentIcon className="w-4 h-4 mr-2" />
                                <span>ARCHITECTURE.md exists</span>
                                {architectureDocument.size_bytes && (
                                  <span className="text-gray-500 dark:text-gray-400 ml-2">
                                    ({(architectureDocument.size_bytes / 1024).toFixed(1)} KB)
                                  </span>
                                )}
                              </div>
                              
                              {isEditingArchitecture ? (
                                <div className="mt-4">
                                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                                    Edit Architecture Document (Markdown)
                                  </label>
                                  <textarea
                                    value={editedArchitectureContent}
                                    onChange={(e) => setEditedArchitectureContent(e.target.value)}
                                    rows={20}
                                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white font-mono text-sm"
                                    placeholder="Enter architecture documentation in Markdown format..."
                                  />
                                </div>
                              ) : (
                                architectureDocument.content && (
                                  <div className="mt-4 prose prose-sm dark:prose-invert max-w-none text-left">
                                    <ReactMarkdown>{architectureDocument.content}</ReactMarkdown>
                                  </div>
                                )
                              )}
                            </div>
                          ) : (
                            <div>
                              <div className="flex items-center text-sm text-gray-500 dark:text-gray-400 py-4">
                                <DocumentIcon className="w-4 h-4 mr-2" />
                                <span>No architecture document found. Click "Generate" to create one or click below to create manually.</span>
                              </div>
                              {!isEditingArchitecture && (
                                <button
                                  onClick={() => {
                                    setIsEditingArchitecture(true)
                                    setEditedArchitectureContent('')
                                    setOriginalContentHash(null)  // null for new document
                                  }}
                                  className="inline-flex items-center px-3 py-1.5 text-sm font-medium text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-md hover:bg-gray-50 dark:hover:bg-gray-600 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
                                >
                                  <PencilIcon className="w-4 h-4 mr-1" />
                                  Create Manually
                                </button>
                              )}
                              {isEditingArchitecture && (
                                <div className="mt-4">
                                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                                    Create Architecture Document (Markdown)
                                  </label>
                                  <textarea
                                    value={editedArchitectureContent}
                                    onChange={(e) => setEditedArchitectureContent(e.target.value)}
                                    rows={20}
                                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white font-mono text-sm"
                                    placeholder="Enter architecture documentation in Markdown format..."
                                  />
                                </div>
                              )}
                            </div>
                          )}
                        </>
                      )}
                    </div>
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-8 text-center">
              <FolderIcon className="mx-auto h-12 w-12 text-gray-400" />
              <h3 className="mt-4 text-lg font-medium text-gray-900 dark:text-white">
                Select a codebase
              </h3>
              <p className="mt-2 text-sm text-gray-600 dark:text-gray-400">
                Choose a codebase from the list to view its details
              </p>
            </div>
          )}
      </div>

      {/* Create Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
          <div className="bg-white dark:bg-gray-800 rounded-lg max-w-md w-full p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-medium text-gray-900 dark:text-white">
                Add New Codebase
              </h3>
              <button
                onClick={() => setShowCreateModal(false)}
                className="text-gray-400 hover:text-gray-500 dark:text-gray-500 dark:hover:text-gray-400"
              >
                <XMarkIcon className="w-5 h-5" />
              </button>
            </div>
            
            <form onSubmit={handleCreateCodebase} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Name *
                </label>
                <input
                  type="text"
                  required
                  value={editForm.name}
                  onChange={(e) => setEditForm({ ...editForm, name: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white"
                  placeholder="My Project"
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Description *
                </label>
                <textarea
                  required
                  value={editForm.description}
                  onChange={(e) => setEditForm({ ...editForm, description: e.target.value })}
                  rows={4}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white"
                  placeholder="Brief description of the codebase (Markdown supported)"
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Local Path *
                </label>
                <input
                  type="text"
                  required
                  value={editForm.local_path}
                  onChange={(e) => setEditForm({ ...editForm, local_path: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white"
                  placeholder="/path/to/your/project"
                />
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                  Absolute path to the directory containing your code
                </p>
              </div>
              
              <div className="flex justify-end space-x-3 pt-4">
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-md hover:bg-gray-50 dark:hover:bg-gray-600 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={loading}
                  className="px-4 py-2 text-sm font-medium text-white bg-blue-600 border border-transparent rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50"
                >
                  {loading ? 'Creating...' : 'Create Codebase'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}