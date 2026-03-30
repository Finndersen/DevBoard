import { useEffect, useState, useId } from 'react'
import mermaid from 'mermaid'
import { ExclamationTriangleIcon } from '@heroicons/react/24/outline'
import { useDarkMode } from '../../contexts/DarkModeContext'
import CodeBlock from './CodeBlock'
import { statusColors, textColors } from '../../styles/designSystem'

interface MermaidDiagramProps {
  code: string
  onExpandClick?: () => void
  className?: string
}

export default function MermaidDiagram({ code, onExpandClick, className = '' }: MermaidDiagramProps) {
  const { isDarkMode } = useDarkMode()
  const [svg, setSvg] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const uniqueId = useId().replace(/:/g, '-')

  useEffect(() => {
    const renderDiagram = async () => {
      try {
        mermaid.initialize({
          startOnLoad: false,
          theme: isDarkMode ? 'dark' : 'default',
          securityLevel: 'strict',
        })

        const { svg: renderedSvg } = await mermaid.render(`mermaid-${uniqueId}`, code)
        setSvg(renderedSvg)
        setError(null)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to render diagram')
        setSvg(null)
      }
    }

    renderDiagram()
  }, [code, isDarkMode, uniqueId])

  if (error) {
    return (
      <div className={`border ${statusColors.warning.border} rounded-lg overflow-hidden ${className}`}>
        <div className={`${statusColors.warning.bg} px-4 py-2 flex items-center gap-2 border-b ${statusColors.warning.border}`}>
          <ExclamationTriangleIcon className={`w-5 h-5 ${statusColors.warning.text}`} />
          <span className={`text-sm font-medium ${statusColors.warning.text}`}>
            Diagram Error
          </span>
        </div>
        <div className="p-4 space-y-3">
          <p className={`text-sm ${statusColors.warning.text}`}>{error}</p>
          <div className="max-h-64 overflow-auto">
            <CodeBlock code={code} language="mermaid" />
          </div>
        </div>
      </div>
    )
  }

  if (!svg) {
    return (
      <div className={`bg-gray-100 dark:bg-gray-800 rounded-lg p-4 flex items-center justify-center ${className}`}>
        <span className={`${textColors.muted} text-sm`}>Loading diagram...</span>
      </div>
    )
  }

  const containerClasses = onExpandClick
    ? 'cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors'
    : ''

  return (
    <div
      className={`bg-white dark:bg-gray-900 rounded-lg p-4 overflow-auto ${containerClasses} ${className}`}
      onClick={onExpandClick}
      role={onExpandClick ? 'button' : undefined}
      tabIndex={onExpandClick ? 0 : undefined}
      onKeyDown={onExpandClick ? (e) => { if (e.key === 'Enter' || e.key === ' ') onExpandClick() } : undefined}
    >
      <div
        className="flex justify-center items-center h-full [&>svg]:max-w-full"
        dangerouslySetInnerHTML={{ __html: svg }}
      />
    </div>
  )
}
