import { useState, useEffect, useCallback, useRef } from 'react'
import { ChevronDownIcon, PencilIcon, TrashIcon, ExclamationTriangleIcon } from '@heroicons/react/24/outline'
import type { ConversationResponse } from '../../lib/api'
import { apiClient } from '../../lib/api'
import { formatRelativeTime } from '../../utils/formatters'

interface ProjectConversationSelectorProps {
  projectId: number
  activeConversationId: number
  onSelect: (conversationId: number) => void
  onNew: () => void
  onDelete: (conversationId: number) => void
  onRename: (conversationId: number, title: string) => void
}

const MAX_CONVERSATIONS = 20

export default function ProjectConversationSelector({
  projectId,
  activeConversationId,
  onSelect,
  onNew,
  onDelete,
  onRename,
}: ProjectConversationSelectorProps) {
  const [conversations, setConversations] = useState<ConversationResponse[]>([])
  const [isOpen, setIsOpen] = useState(false)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [editTitle, setEditTitle] = useState('')
  const editInputRef = useRef<HTMLInputElement>(null)

  const fetchConversations = useCallback(async () => {
    try {
      const data = await apiClient.getProjectConversations(projectId)
      setConversations(data)
    } catch (error) {
      console.error('Failed to fetch project conversations:', error)
    }
  }, [projectId])

  useEffect(() => {
    fetchConversations()
  }, [fetchConversations])

  // Refetch when dropdown opens
  useEffect(() => {
    if (isOpen) {
      fetchConversations()
    }
  }, [isOpen, fetchConversations])

  // Focus edit input when editing starts
  useEffect(() => {
    if (editingId !== null && editInputRef.current) {
      editInputRef.current.focus()
      editInputRef.current.select()
    }
  }, [editingId])

  const activeConversation = conversations.find(c => c.id === activeConversationId)
  const atCap = conversations.length >= MAX_CONVERSATIONS

  const handleStartRename = (e: React.MouseEvent, conv: ConversationResponse) => {
    e.stopPropagation()
    setEditingId(conv.id)
    setEditTitle(conv.title || '')
  }

  const handleSaveRename = async () => {
    if (editingId === null || !editTitle.trim()) {
      setEditingId(null)
      return
    }
    onRename(editingId, editTitle.trim())
    // Optimistically update local state
    setConversations(prev =>
      prev.map(c => c.id === editingId ? { ...c, title: editTitle.trim() } : c)
    )
    setEditingId(null)
  }

  const handleRenameKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleSaveRename()
    } else if (e.key === 'Escape') {
      setEditingId(null)
    }
  }

  const handleDelete = (e: React.MouseEvent, conversationId: number) => {
    e.stopPropagation()
    onDelete(conversationId)
    // Remove from local list
    setConversations(prev => prev.filter(c => c.id !== conversationId))
  }

  const displayTitle = activeConversation?.title || 'Untitled'

  return (
    <div className="relative">
      {/* Trigger button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-1 px-2 py-1 text-xs text-gray-400 dark:text-gray-500 bg-gray-800 border border-gray-700 rounded-md hover:bg-gray-700 hover:text-gray-300 transition-colors max-w-[200px]"
      >
        <span className="truncate">{displayTitle}</span>
        <ChevronDownIcon className="w-3 h-3 flex-shrink-0" />
      </button>

      {/* Dropdown */}
      {isOpen && (
        <>
          {/* Backdrop */}
          <div
            className="fixed inset-0 z-10"
            onClick={() => { setIsOpen(false); setEditingId(null) }}
          />

          {/* Menu */}
          <div className="absolute left-0 mt-1 w-80 bg-gray-800 border border-gray-700 rounded-lg shadow-lg z-20 overflow-hidden">
            {/* Cap warning */}
            {atCap && (
              <div className="flex items-center gap-1.5 px-3 py-1.5 bg-yellow-900/50 text-yellow-400 text-xs">
                <ExclamationTriangleIcon className="w-3.5 h-3.5 flex-shrink-0" />
                <span>{MAX_CONVERSATIONS}/{MAX_CONVERSATIONS} conversations — oldest will be removed on next creation</span>
              </div>
            )}

            {/* Conversation list */}
            <div className="max-h-64 overflow-y-auto">
              {conversations.map(conv => {
                const isActive = conv.id === activeConversationId
                const isEditing = editingId === conv.id

                return (
                  <div
                    key={conv.id}
                    onClick={() => { if (!isEditing) { onSelect(conv.id); setIsOpen(false) } }}
                    className={`flex items-center justify-between px-3 py-2 cursor-pointer border-l-2 transition-colors ${
                      isActive
                        ? 'border-blue-500 bg-blue-500/10'
                        : 'border-transparent hover:bg-gray-700/50'
                    }`}
                  >
                    <div className="min-w-0 flex-1">
                      {isEditing ? (
                        <input
                          ref={editInputRef}
                          value={editTitle}
                          onChange={e => setEditTitle(e.target.value)}
                          onKeyDown={handleRenameKeyDown}
                          onBlur={handleSaveRename}
                          onClick={e => e.stopPropagation()}
                          className="w-full text-sm bg-gray-700 border border-gray-600 rounded px-1.5 py-0.5 text-gray-200 focus:outline-none focus:border-blue-500"
                          maxLength={80}
                        />
                      ) : (
                        <>
                          <div className={`text-sm truncate ${
                            isActive ? 'text-blue-300 font-medium' :
                            conv.title ? 'text-gray-300' : 'text-gray-500 italic'
                          }`}>
                            {conv.title || 'Untitled'}
                          </div>
                          <div className="text-xs text-gray-500 mt-0.5">
                            {conv.last_activity_at ? formatRelativeTime(conv.last_activity_at) : 'No activity'}
                          </div>
                        </>
                      )}
                    </div>

                    {/* Action buttons */}
                    {!isEditing && (
                      <div className="flex gap-1 ml-2 flex-shrink-0">
                        <button
                          onClick={e => handleStartRename(e, conv)}
                          className="p-1 text-gray-500 hover:text-gray-300 transition-colors"
                          title="Rename"
                        >
                          <PencilIcon className="w-3.5 h-3.5" />
                        </button>
                        <button
                          onClick={e => handleDelete(e, conv.id)}
                          className="p-1 text-gray-500 hover:text-red-400 transition-colors"
                          title="Delete"
                        >
                          <TrashIcon className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    )}
                  </div>
                )
              })}

              {conversations.length === 0 && (
                <div className="px-3 py-4 text-sm text-gray-500 text-center">
                  No conversations yet
                </div>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  )
}
