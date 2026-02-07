interface AgentRole {
  key: string
  name: string
  description: string
}

interface AgentRoleListProps {
  roles: AgentRole[]
  selectedRole: string
  onSelectRole: (roleKey: string) => void
}

export function AgentRoleList({ roles, selectedRole, onSelectRole }: AgentRoleListProps) {
  return (
    <div className="divide-y divide-gray-200 dark:divide-gray-700">
      {roles.map((role) => (
        <button
          key={role.key}
          onClick={() => onSelectRole(role.key)}
          className={`w-full text-left px-4 py-3 transition-colors ${
            selectedRole === role.key
              ? 'bg-blue-50 dark:bg-blue-900/20 border-l-2 border-blue-500'
              : 'hover:bg-gray-50 dark:hover:bg-gray-800 border-l-2 border-transparent'
          }`}
        >
          <div className={`text-sm font-medium ${
            selectedRole === role.key
              ? 'text-blue-700 dark:text-blue-400'
              : 'text-gray-900 dark:text-white'
          }`}>
            {role.name}
          </div>
          <div className="text-xs text-gray-500 dark:text-gray-400 mt-0.5 line-clamp-2">
            {role.description}
          </div>
        </button>
      ))}
    </div>
  )
}
