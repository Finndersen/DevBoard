import { statusColors } from '../../styles/designSystem'

interface AgentReasoningProps {
  reasoning: string | null
}

export default function AgentReasoning({ reasoning }: AgentReasoningProps) {
  if (!reasoning) {
    return null
  }

  return (
    <div>
      <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
        Agent Reasoning:
      </h3>
      <div className={`${statusColors.info.bg} border ${statusColors.info.border} rounded-lg p-4`}>
        <p className="text-sm text-gray-700 dark:text-gray-300">
          {reasoning}
        </p>
      </div>
    </div>
  )
}
