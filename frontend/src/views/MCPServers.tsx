import { useState, useEffect, useCallback } from 'react'
import { useSearchParams } from 'react-router-dom'
import { PlusIcon, ServerIcon, ServerStackIcon } from '@heroicons/react/24/outline'
import { Button, Card } from '../components/ui'
import { MCPServerList } from '../components/mcp/MCPServerList'
import { MCPServerDetail } from '../components/mcp/MCPServerDetail'
import { MCPServerForm } from '../components/mcp/MCPServerForm'
import { textColors } from '../styles/designSystem'
import { apiClient } from '../lib/api'
import type { MCPServerConfig, MCPServerDetail as MCPServerDetailType, MCPTool } from '../lib/api'
import ViewHeader from '../components/layout/ViewHeader'

export default function MCPServersView() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [servers, setServers] = useState<MCPServerConfig[]>([])
  const [serverDetail, setServerDetail] = useState<MCPServerDetailType | null>(null)
  const [loading, setLoading] = useState(true)
  const [detailLoading, setDetailLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [isFormOpen, setIsFormOpen] = useState(false)
  const [editingServer, setEditingServer] = useState<MCPServerConfig | null>(null)
  const [verifying, setVerifying] = useState(false)

  const serverParam = searchParams.get('server')
  const selectedServerId = serverParam ? parseInt(serverParam, 10) : null

  const setSelectedServerId = useCallback((id: number | null) => {
    setSearchParams(prev => {
      if (id !== null) {
        prev.set('server', String(id))
      } else {
        prev.delete('server')
      }
      return prev
    }, { replace: true })
  }, [setSearchParams])

  const loadServers = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)
      const data = await apiClient.listMCPServers()
      setServers(data)
      // Auto-select first server if none selected via URL
      if (data.length > 0 && !serverParam) {
        setSelectedServerId(data[0].id)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load MCP servers')
    } finally {
      setLoading(false)
    }
  }, [serverParam, setSelectedServerId])

  const loadServerDetail = useCallback(async (serverId: number) => {
    try {
      setDetailLoading(true)
      const detail = await apiClient.getMCPServerDetail(serverId)
      setServerDetail(detail)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load server details')
    } finally {
      setDetailLoading(false)
    }
  }, [])

  useEffect(() => {
    loadServers()
  }, [loadServers])

  useEffect(() => {
    if (selectedServerId !== null) {
      loadServerDetail(selectedServerId)
    } else {
      setServerDetail(null)
    }
  }, [selectedServerId, loadServerDetail])

  const handleCreate = () => {
    setEditingServer(null)
    setIsFormOpen(true)
  }

  const handleSelect = (server: MCPServerConfig) => {
    setSelectedServerId(server.id)
  }

  const handleEdit = () => {
    if (serverDetail) {
      setEditingServer(serverDetail)
      setIsFormOpen(true)
    }
  }

  const handleDelete = async () => {
    if (!serverDetail) return
    try {
      await apiClient.deleteMCPServer(serverDetail.id)
      setServers(prev => prev.filter(s => s.id !== serverDetail.id))
      setSelectedServerId(servers.find(s => s.id !== serverDetail.id)?.id ?? null)
      setServerDetail(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete server')
    }
  }

  const handleVerify = async () => {
    if (!serverDetail) return
    try {
      setVerifying(true)
      const result = await apiClient.verifyMCPServer(serverDetail.id)
      setServerDetail(result)
      // Update server in list with new verification status
      setServers(prev => prev.map(s =>
        s.id === result.id ? {
          ...s,
          last_verified_at: result.last_verified_at,
          last_verified_success: result.last_verified_success,
          last_verified_error: result.last_verified_error
        } : s
      ))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Verification failed')
    } finally {
      setVerifying(false)
    }
  }

  const handleToolUpdate = (updatedTool: MCPTool) => {
    if (!serverDetail) return
    setServerDetail({
      ...serverDetail,
      tools: serverDetail.tools.map(t => t.id === updatedTool.id ? updatedTool : t)
    })
  }

  const handleFormSubmit = async (data: MCPServerConfig) => {
    const isNewServer = !editingServer
    if (editingServer) {
      setServers(prev => prev.map(s => s.id === data.id ? data : s))
      // Refresh detail if this is the selected server
      if (selectedServerId === data.id) {
        loadServerDetail(data.id)
      }
    } else {
      setServers(prev => [...prev, data])
      setSelectedServerId(data.id)
    }
    setIsFormOpen(false)
    setEditingServer(null)

    // Auto-verify new servers to populate tools list
    if (isNewServer) {
      try {
        setVerifying(true)
        const result = await apiClient.verifyMCPServer(data.id)
        setServerDetail(result)
        setServers(prev => prev.map(s =>
          s.id === result.id ? {
            ...s,
            last_verified_at: result.last_verified_at,
            last_verified_success: result.last_verified_success,
            last_verified_error: result.last_verified_error
          } : s
        ))
      } catch {
        // Verification failure is not critical - user can retry manually
      } finally {
        setVerifying(false)
      }
    }
  }

  const handleFormClose = () => {
    setIsFormOpen(false)
    setEditingServer(null)
  }

  return (
    <div className="h-full flex flex-col">
      <ViewHeader
        icon={ServerIcon}
        iconColor="text-purple-600 dark:text-purple-400"
        title="MCP Servers"
        actions={
          <Button onClick={handleCreate} icon={<PlusIcon className="w-4 h-4" />}>
            Add Server
          </Button>
        }
      />

      {error && (
        <Card className="mx-6 mt-4 border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-900/20">
          <p className="text-red-600 dark:text-red-400">{error}</p>
        </Card>
      )}

      {/* Two-panel layout */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left panel - server list */}
        <div className="w-64 border-r border-gray-200 dark:border-gray-700 overflow-y-auto bg-gray-50 dark:bg-gray-900">
          {loading ? (
            <div className="flex justify-center py-12">
              <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-600" />
            </div>
          ) : (
            <MCPServerList
              servers={servers}
              selectedId={selectedServerId}
              onSelect={handleSelect}
            />
          )}
        </div>

        {/* Right panel - server detail */}
        <div className="flex-1 flex flex-col overflow-hidden">
          {detailLoading ? (
            <div className="flex justify-center py-12">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
            </div>
          ) : serverDetail ? (
            <MCPServerDetail
              server={serverDetail}
              onEdit={handleEdit}
              onDelete={handleDelete}
              onVerify={handleVerify}
              onToolUpdate={handleToolUpdate}
              verifying={verifying}
            />
          ) : (
            <div className="flex flex-col items-center justify-center h-full text-center p-6">
              <ServerStackIcon className="w-16 h-16 text-gray-400 mb-4" />
              <h3 className={`text-lg font-medium ${textColors.primary} mb-2`}>
                {servers.length === 0 ? 'No MCP Servers' : 'Select a Server'}
              </h3>
              <p className={`${textColors.secondary} mb-4`}>
                {servers.length === 0
                  ? 'Add an MCP server to enable tool integrations for your agents.'
                  : 'Select a server from the list to view its details and tools.'}
              </p>
              {servers.length === 0 && (
                <Button onClick={handleCreate} icon={<PlusIcon className="w-4 h-4" />}>
                  Add Server
                </Button>
              )}
            </div>
          )}
        </div>
      </div>

      {isFormOpen && (
        <MCPServerForm
          server={editingServer}
          onSubmit={handleFormSubmit}
          onClose={handleFormClose}
        />
      )}
    </div>
  )
}
