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
      <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-4">
        <p className="text-sm text-gray-700 dark:text-gray-300">
          {reasoning}
        </p>
      </div>
    </div>
  )
}
