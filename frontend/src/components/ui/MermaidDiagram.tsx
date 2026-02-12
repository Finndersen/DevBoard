import { useEffect, useState, useId } from 'react'
import mermaid from 'mermaid'
import { ExclamationTriangleIcon } from '@heroicons/react/24/outline'
import { useDarkMode } from '../../contexts/DarkModeContext'
import CodeBlock from './CodeBlock'

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
      <div className={`border border-amber-400 dark:border-amber-600 rounded-lg overflow-hidden ${className}`}>
        <div className="bg-amber-50 dark:bg-amber-900/30 px-4 py-2 flex items-center gap-2 border-b border-amber-400 dark:border-amber-600">
          <ExclamationTriangleIcon className="w-5 h-5 text-amber-600 dark:text-amber-400" />
          <span className="text-sm font-medium text-amber-800 dark:text-amber-200">
            Diagram Error
          </span>
        </div>
        <div className="p-4 space-y-3">
          <p className="text-sm text-amber-700 dark:text-amber-300">{error}</p>
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
        <span className="text-gray-500 dark:text-gray-400 text-sm">Loading diagram...</span>
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
