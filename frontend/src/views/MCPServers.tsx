import { useState, useEffect, useCallback } from 'react'
import { PlusIcon } from '@heroicons/react/24/outline'
import { Button, Card } from '../components/ui'
import { MCPServerList } from '../components/mcp/MCPServerList'
import { MCPServerForm } from '../components/mcp/MCPServerForm'
import { VerifyResultModal } from '../components/mcp/VerifyResultModal'
import { textColors } from '../styles/designSystem'
import { apiClient } from '../lib/api'
import type { MCPServerConfig, VerifyResult } from '../lib/api'

export default function MCPServersView() {
  const [servers, setServers] = useState<MCPServerConfig[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [isFormOpen, setIsFormOpen] = useState(false)
  const [editingServer, setEditingServer] = useState<MCPServerConfig | null>(null)
  const [verifyResult, setVerifyResult] = useState<VerifyResult | null>(null)
  const [verifyingServerId, setVerifyingServerId] = useState<number | null>(null)

  const loadServers = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)
      const data = await apiClient.listMCPServers()
      setServers(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load MCP servers')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadServers()
  }, [loadServers])

  const handleCreate = () => {
    setEditingServer(null)
    setIsFormOpen(true)
  }

  const handleEdit = (server: MCPServerConfig) => {
    setEditingServer(server)
    setIsFormOpen(true)
  }

  const handleDelete = async (server: MCPServerConfig) => {
    try {
      await apiClient.deleteMCPServer(server.id)
      setServers(prev => prev.filter(s => s.id !== server.id))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete server')
    }
  }

  const handleVerify = async (server: MCPServerConfig) => {
    try {
      setVerifyingServerId(server.id)
      const result = await apiClient.verifyMCPServer(server.id)
      setVerifyResult(result)
    } catch (err) {
      setVerifyResult({
        success: false,
        tools: null,
        error: err instanceof Error ? err.message : 'Verification failed'
      })
    } finally {
      setVerifyingServerId(null)
    }
  }

  const handleFormSubmit = async (data: MCPServerConfig) => {
    if (editingServer) {
      setServers(prev => prev.map(s => s.id === data.id ? data : s))
    } else {
      setServers(prev => [...prev, data])
    }
    setIsFormOpen(false)
    setEditingServer(null)
  }

  const handleFormClose = () => {
    setIsFormOpen(false)
    setEditingServer(null)
  }

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <div className="flex justify-between items-center mb-6">
        <div>
          <h1 className={`text-2xl font-semibold ${textColors.primary}`}>
            MCP Servers
          </h1>
          <p className={`mt-1 text-sm ${textColors.secondary}`}>
            Configure and manage Model Context Protocol server connections
          </p>
        </div>
        <Button onClick={handleCreate} icon={<PlusIcon />}>
          Add Server
        </Button>
      </div>

      {error && (
        <Card className="mb-4 border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-900/20">
          <p className="text-red-600 dark:text-red-400">{error}</p>
        </Card>
      )}

      {loading ? (
        <div className="flex justify-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
        </div>
      ) : (
        <MCPServerList
          servers={servers}
          onEdit={handleEdit}
          onDelete={handleDelete}
          onVerify={handleVerify}
          verifyingServerId={verifyingServerId}
        />
      )}

      {isFormOpen && (
        <MCPServerForm
          server={editingServer}
          onSubmit={handleFormSubmit}
          onClose={handleFormClose}
        />
      )}

      {verifyResult && (
        <VerifyResultModal
          result={verifyResult}
          onClose={() => setVerifyResult(null)}
        />
      )}
    </div>
  )
}
