import { useState, useEffect, useCallback } from 'react'
import { ChevronDownIcon, ChevronUpIcon, CheckCircleIcon } from '@heroicons/react/24/outline'
import { CheckCircleIcon as CheckCircleSolidIcon } from '@heroicons/react/24/solid'
import { apiClient } from '../../lib/api'
import type { TodoItem } from '../../lib/api'
import { useToolResultHandler } from '../../hooks/useConversationEventHandlers'
import { textColors } from '../../styles/designSystem'

interface TodoPanelProps {
  conversationId: number
  engine: string
}

const TodoPanel = ({ conversationId, engine }: TodoPanelProps) => {
  const [todos, setTodos] = useState<TodoItem[]>([])
  const [isCollapsed, setIsCollapsed] = useState(true)
  const [hasUpdates, setHasUpdates] = useState(false)
  const [isLoading, setIsLoading] = useState(false)

  const fetchTodos = useCallback(async () => {
    if (engine !== 'claude_code') return

    setIsLoading(true)
    try {
      const data = await apiClient.getConversationTodos(conversationId)
      setTodos(data)
    } catch (error) {
      console.error('Failed to fetch todos:', error)
    } finally {
      setIsLoading(false)
    }
  }, [conversationId, engine])

  useEffect(() => {
    fetchTodos()
  }, [fetchTodos])

  // Register handler for TodoWrite tool results to trigger refresh
  useToolResultHandler((toolName) => {
    if (toolName === 'TodoWrite') {
      fetchTodos()
      if (isCollapsed) {
        setHasUpdates(true)
      }
    }
  })

  // Clear update indicator when panel is expanded
  useEffect(() => {
    if (!isCollapsed) {
      setHasUpdates(false)
    }
  }, [isCollapsed])

  // Don't render for non-Claude Code conversations or when no todos exist
  if (engine !== 'claude_code' || (todos.length === 0 && !isLoading)) {
    return null
  }

  const completedCount = todos.filter(t => t.status === 'completed').length
  const totalCount = todos.length
  const inProgressTodo = todos.find(t => t.status === 'in_progress')

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircleSolidIcon className="w-4 h-4 text-green-500" />
      case 'in_progress':
        return (
          <div className="w-4 h-4 rounded-full border-2 border-blue-500 border-t-transparent animate-spin" />
        )
      case 'pending':
      default:
        return <CheckCircleIcon className="w-4 h-4 text-gray-400 dark:text-gray-500" />
    }
  }

  const getStatusTextClass = (status: string) => {
    switch (status) {
      case 'completed':
        return 'text-gray-500 dark:text-gray-400 line-through'
      case 'in_progress':
        return 'text-blue-600 dark:text-blue-400 font-medium'
      case 'pending':
      default:
        return textColors.secondary
    }
  }

  return (
    <div className="border-b border-gray-200 dark:border-gray-600 flex-shrink-0">
      {/* Collapsed bar */}
      <button
        onClick={() => setIsCollapsed(!isCollapsed)}
        className={`w-full px-3 py-2 flex items-center justify-between hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors ${
          hasUpdates ? 'animate-pulse bg-blue-50 dark:bg-blue-900/20' : ''
        }`}
      >
        <div className="flex items-center space-x-2">
          <span className={`text-sm font-medium ${textColors.secondary}`}>
            Tasks: {completedCount}/{totalCount} completed
          </span>
          {inProgressTodo && (
            <span className="text-xs text-blue-600 dark:text-blue-400 truncate max-w-[200px]">
              — {inProgressTodo.active_form || inProgressTodo.content}
            </span>
          )}
        </div>
        <div className="flex items-center">
          {isCollapsed ? (
            <ChevronDownIcon className="w-4 h-4 text-gray-500" />
          ) : (
            <ChevronUpIcon className="w-4 h-4 text-gray-500" />
          )}
        </div>
      </button>

      {/* Expanded content */}
      {!isCollapsed && (
        <div className="px-3 py-2 space-y-1 max-h-48 overflow-y-auto">
          {todos.map((todo, index) => (
            <div
              key={todo.id || index}
              className="flex items-start space-x-2 py-1"
            >
              <div className="flex-shrink-0 mt-0.5">
                {getStatusIcon(todo.status)}
              </div>
              <span className={`text-sm ${getStatusTextClass(todo.status)}`}>
                {todo.status === 'in_progress' && todo.active_form
                  ? todo.active_form
                  : todo.content}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default TodoPanel
