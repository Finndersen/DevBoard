import { useState, useEffect } from 'react'
import { Modal, Button, Input } from '../ui'
import { textColors, statusColors, borderColors } from '../../styles/designSystem'
import { standardInputClasses } from '../../styles/inputStyles'
import { apiClient } from '../../lib/api'
import type {
  MCPServerConfig,
  MCPServerConfigCreate,
  MCPServerType,
  StdioMCPConfig,
  HttpMCPConfig,
  HttpAuthType
} from '../../lib/api'

interface MCPServerFormProps {
  server: MCPServerConfig | null
  onSubmit: (server: MCPServerConfig) => void
  onClose: () => void
}

interface FormData {
  name: string
  server_type: MCPServerType
  command: string
  args: string
  env: string
  url: string
  auth_type: HttpAuthType
  bearer_token: string
  client_id: string
  client_secret: string
  scopes: string
}

export function MCPServerForm({ server, onSubmit, onClose }: MCPServerFormProps) {
  const isEditing = server !== null

  const [formData, setFormData] = useState<FormData>(() => {
    if (server) {
      if (server.server_type === 'stdio' && 'command' in server.config_json) {
        const config = server.config_json as StdioMCPConfig
        return {
          name: server.name,
          server_type: 'stdio',
          command: config.command,
          args: config.args?.join(' ') || '',
          env: config.env ? Object.entries(config.env).map(([k, v]) => `${k}=${v}`).join('\n') : '',
          url: '',
          auth_type: 'none',
          bearer_token: '',
          client_id: '',
          client_secret: '',
          scopes: ''
        }
      } else if (server.server_type === 'http' && 'url' in server.config_json) {
        const config = server.config_json as HttpMCPConfig
        return {
          name: server.name,
          server_type: 'http',
          command: '',
          args: '',
          env: '',
          url: config.url,
          auth_type: config.auth_type || 'none',
          bearer_token: config.bearer_token || '',
          client_id: config.client_id || '',
          client_secret: config.client_secret || '',
          scopes: config.scopes || ''
        }
      }
    }
    return {
      name: '',
      server_type: 'stdio',
      command: '',
      args: '',
      env: '',
      url: '',
      auth_type: 'none',
      bearer_token: '',
      client_id: '',
      client_secret: '',
      scopes: ''
    }
  })

  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleChange = (field: keyof FormData, value: string) => {
    setFormData(prev => ({ ...prev, [field]: value }))
    setError(null)
  }

  const parseArgs = (argsString: string): string[] => {
    if (!argsString.trim()) return []
    return argsString.trim().split(/\s+/)
  }

  const parseEnv = (envString: string): Record<string, string> | null => {
    if (!envString.trim()) return null
    const result: Record<string, string> = {}
    for (const line of envString.split('\n')) {
      const trimmed = line.trim()
      if (!trimmed) continue
      const eqIndex = trimmed.indexOf('=')
      if (eqIndex > 0) {
        const key = trimmed.substring(0, eqIndex).trim()
        const value = trimmed.substring(eqIndex + 1).trim()
        result[key] = value
      }
    }
    return Object.keys(result).length > 0 ? result : null
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    if (!formData.name.trim()) {
      setError('Name is required')
      return
    }

    if (formData.server_type === 'stdio' && !formData.command.trim()) {
      setError('Command is required for STDIO servers')
      return
    }

    if (formData.server_type === 'http' && !formData.url.trim()) {
      setError('URL is required for HTTP servers')
      return
    }

    setLoading(true)
    setError(null)

    try {
      let configJson: StdioMCPConfig | HttpMCPConfig

      if (formData.server_type === 'stdio') {
        configJson = {
          command: formData.command.trim(),
          args: parseArgs(formData.args),
          env: parseEnv(formData.env)
        }
      } else {
        configJson = {
          url: formData.url.trim(),
          auth_type: formData.auth_type,
          bearer_token: formData.auth_type === 'bearer' ? formData.bearer_token : null,
          client_id: formData.auth_type === 'oauth' && formData.client_id.trim() ? formData.client_id.trim() : null,
          client_secret: formData.auth_type === 'oauth' && formData.client_secret.trim() ? formData.client_secret.trim() : null,
          scopes: formData.auth_type === 'oauth' && formData.scopes.trim() ? formData.scopes.trim() : null
        }
      }

      const data: MCPServerConfigCreate = {
        name: formData.name.trim(),
        server_type: formData.server_type,
        config_json: configJson
      }

      let result: MCPServerConfig
      if (isEditing && server) {
        result = await apiClient.updateMCPServer(server.id, data)
      } else {
        result = await apiClient.createMCPServer(data)
      }

      onSubmit(result)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save server')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Modal
      isOpen={true}
      onClose={onClose}
      title={isEditing ? 'Edit MCP Server' : 'Add MCP Server'}
      maxWidth="lg"
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        {error && (
          <div className={`p-3 ${statusColors.error.bg} border ${statusColors.error.border} rounded-md`}>
            <p className={`text-sm ${statusColors.error.text}`}>{error}</p>
          </div>
        )}

        <Input
          label="Server Name"
          value={formData.name}
          onChange={(e) => handleChange('name', e.target.value)}
          placeholder="My MCP Server"
          required
        />

        <div>
          <label className={`block text-sm font-medium ${textColors.secondary} mb-2`}>
            Server Type
          </label>
          <select
            value={formData.server_type}
            onChange={(e) => handleChange('server_type', e.target.value as MCPServerType)}
            className={standardInputClasses}
          >
            <option value="stdio">STDIO (Local Process)</option>
            <option value="http">HTTP (Remote Server)</option>
          </select>
        </div>

        {formData.server_type === 'stdio' && (
          <>
            <Input
              label="Command"
              value={formData.command}
              onChange={(e) => handleChange('command', e.target.value)}
              placeholder="npx -y @modelcontextprotocol/server-filesystem"
              required
            />

            <Input
              label="Arguments"
              value={formData.args}
              onChange={(e) => handleChange('args', e.target.value)}
              placeholder="--directory /path/to/project --flag"
              helpText="Space-separated arguments (as you would type in a terminal)"
            />

            <div>
              <label className={`block text-sm font-medium ${textColors.secondary} mb-2`}>
                Environment Variables
              </label>
              <textarea
                value={formData.env}
                onChange={(e) => handleChange('env', e.target.value)}
                placeholder="KEY=value&#10;ANOTHER_KEY=another_value"
                rows={3}
                className={standardInputClasses}
              />
              <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
                One variable per line in KEY=value format
              </p>
            </div>
          </>
        )}

        {formData.server_type === 'http' && (
          <>
            <Input
              label="URL"
              type="url"
              value={formData.url}
              onChange={(e) => handleChange('url', e.target.value)}
              placeholder="https://mcp-server.example.com/mcp"
              required
            />

            <div>
              <label className={`block text-sm font-medium ${textColors.secondary} mb-2`}>
                Authentication
              </label>
              <select
                value={formData.auth_type}
                onChange={(e) => handleChange('auth_type', e.target.value as HttpAuthType)}
                className={standardInputClasses}
              >
                <option value="none">None</option>
                <option value="bearer">Bearer Token</option>
                <option value="oauth">OAuth 2.0</option>
              </select>
            </div>

            {formData.auth_type === 'bearer' && (
              <Input
                label="Bearer Token"
                type="password"
                value={formData.bearer_token}
                onChange={(e) => handleChange('bearer_token', e.target.value)}
                placeholder="Enter your bearer token"
              />
            )}

            {formData.auth_type === 'oauth' && (
              <div className={`space-y-3 p-3 border ${borderColors.default} rounded-md`}>
                <p className="text-sm text-gray-500 dark:text-gray-400">
                  OAuth will be initiated when you verify the server. Leave fields blank for automatic discovery and registration.
                </p>
                <Input
                  label="Client ID"
                  value={formData.client_id}
                  onChange={(e) => handleChange('client_id', e.target.value)}
                  placeholder="Leave blank for auto-registration"
                  helpText="Only needed if the server doesn't support Dynamic Client Registration"
                />
                <Input
                  label="Client Secret"
                  type="password"
                  value={formData.client_secret}
                  onChange={(e) => handleChange('client_secret', e.target.value)}
                  placeholder="Leave blank for auto-registration"
                  helpText="Only needed if the server doesn't support Dynamic Client Registration"
                />
                <Input
                  label="Scopes"
                  value={formData.scopes}
                  onChange={(e) => handleChange('scopes', e.target.value)}
                  placeholder="read write"
                  helpText="Space-separated list of OAuth scopes"
                />
              </div>
            )}
          </>
        )}

        <div className="flex justify-end gap-3 pt-4">
          <Button variant="secondary" onClick={onClose} type="button">
            Cancel
          </Button>
          <Button type="submit" loading={loading}>
            {isEditing ? 'Save Changes' : 'Add Server'}
          </Button>
        </div>
      </form>
    </Modal>
  )
}
