import { useState, useEffect, useCallback, useMemo } from 'react'
import { FolderIcon, ArrowUpIcon } from '@heroicons/react/24/outline'
import Modal from '../ui/Modal'
import Button from '../ui/Button'
import { useListDirectory } from '../../hooks/useFilesystem'

interface DirectoryBrowserModalProps {
  isOpen: boolean
  onClose: () => void
  onSelect: (path: string) => void
  initialPath?: string
}

export default function DirectoryBrowserModal({
  isOpen,
  onClose,
  onSelect,
  initialPath,
}: DirectoryBrowserModalProps) {
  const { data, loading, error, listDirectory } = useListDirectory()
  const [selectedPath, setSelectedPath] = useState<string | null>(null)

  // Load initial directory when modal opens
  useEffect(() => {
    if (isOpen) {
      listDirectory(initialPath || undefined).catch(() => {
        // Error is already captured in the hook's error state
      })
      setSelectedPath(null)
    }
  }, [isOpen, initialPath, listDirectory])

  const handleNavigate = useCallback(
    (dirName: string) => {
      if (data?.current_path) {
        const newPath = `${data.current_path}/${dirName}`
        listDirectory(newPath).catch(() => {
          // Error is captured in hook's error state
        })
        setSelectedPath(null)
      }
    },
    [data?.current_path, listDirectory]
  )

  const handleGoUp = useCallback(() => {
    if (data?.parent_path) {
      listDirectory(data.parent_path).catch(() => {
        // Error is captured in hook's error state
      })
      setSelectedPath(null)
    }
  }, [data?.parent_path, listDirectory])

  const handleSelect = useCallback(() => {
    if (selectedPath) {
      onSelect(selectedPath)
      onClose()
    } else if (data?.current_path) {
      onSelect(data.current_path)
      onClose()
    }
  }, [selectedPath, data?.current_path, onSelect, onClose])

  const handleDirectoryClick = useCallback(
    (dirName: string) => {
      if (data?.current_path) {
        const fullPath = `${data.current_path}/${dirName}`
        setSelectedPath(fullPath)
      }
    },
    [data?.current_path]
  )

  const handleDirectoryDoubleClick = useCallback(
    (dirName: string) => {
      handleNavigate(dirName)
    },
    [handleNavigate]
  )

  // Parse current path into breadcrumb segments
  const pathSegments = useMemo(
    () => (data?.current_path ? data.current_path.split('/').filter(Boolean) : []),
    [data?.current_path]
  )

  const handleBreadcrumbClick = useCallback(
    (index: number) => {
      const newPath = '/' + pathSegments.slice(0, index + 1).join('/')
      listDirectory(newPath).catch(() => {
        // Error is captured in hook's error state
      })
      setSelectedPath(null)
    },
    [pathSegments, listDirectory]
  )

  const handleNavigateToRoot = useCallback(() => {
    listDirectory('/').catch(() => {
      // Error is captured in hook's error state
    })
  }, [listDirectory])

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Select Directory" maxWidth="lg">
      <div className="space-y-4">
        {/* Breadcrumb navigation */}
        <div className="flex items-center gap-1 text-sm bg-gray-50 dark:bg-gray-900 p-2 rounded-lg overflow-x-auto">
          <button
            onClick={handleNavigateToRoot}
            className="text-blue-600 dark:text-blue-400 hover:underline shrink-0"
          >
            /
          </button>
          {pathSegments.map((segment, index) => (
            <span key={index} className="flex items-center shrink-0">
              <span className="text-gray-400 mx-1">/</span>
              <button
                onClick={() => handleBreadcrumbClick(index)}
                className="text-blue-600 dark:text-blue-400 hover:underline"
              >
                {segment}
              </button>
            </span>
          ))}
        </div>

        {/* Go up button */}
        {data?.parent_path && (
          <button
            onClick={handleGoUp}
            className="flex items-center gap-2 w-full p-2 text-left hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
          >
            <ArrowUpIcon className="w-5 h-5 text-gray-500" />
            <span className="text-gray-600 dark:text-gray-300">..</span>
          </button>
        )}

        {/* Directory list */}
        <div className="border border-gray-200 dark:border-gray-600 rounded-lg max-h-64 overflow-y-auto">
          {loading && (
            <div className="p-4 text-center text-gray-500 dark:text-gray-400">
              Loading...
            </div>
          )}

          {error && (
            <div className="p-4 text-center text-red-500 dark:text-red-400">
              {error}
            </div>
          )}

          {!loading && !error && data?.directories.length === 0 && (
            <div className="p-4 text-center text-gray-500 dark:text-gray-400">
              No subdirectories
            </div>
          )}

          {!loading &&
            !error &&
            data?.directories.map((dir) => {
              const fullPath = `${data.current_path}/${dir}`
              const isSelected = selectedPath === fullPath
              return (
                <button
                  key={dir}
                  onClick={() => handleDirectoryClick(dir)}
                  onDoubleClick={() => handleDirectoryDoubleClick(dir)}
                  className={`flex items-center gap-2 w-full p-2 text-left transition-colors ${
                    isSelected
                      ? 'bg-blue-100 dark:bg-blue-900'
                      : 'hover:bg-gray-100 dark:hover:bg-gray-700'
                  }`}
                >
                  <FolderIcon className="w-5 h-5 text-yellow-500" />
                  <span className="text-gray-800 dark:text-gray-200 truncate">
                    {dir}
                  </span>
                </button>
              )
            })}
        </div>

        {/* Selected path display */}
        <div className="text-sm text-gray-600 dark:text-gray-400">
          <span className="font-medium">Selected: </span>
          <span className="font-mono">
            {selectedPath || data?.current_path || ''}
          </span>
        </div>

        {/* Action buttons */}
        <div className="flex justify-end space-x-3 pt-2">
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button
            variant="primary"
            onClick={handleSelect}
            disabled={loading}
          >
            Select
          </Button>
        </div>
      </div>
    </Modal>
  )
}
