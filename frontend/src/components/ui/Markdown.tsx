import { useState, useMemo } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { Components } from 'react-markdown'
import CodeBlock from './CodeBlock'
import MermaidDiagram from './MermaidDiagram'
import MermaidDiagramModal from './MermaidDiagramModal'

interface MarkdownProps {
  children: string
  forceWhiteText?: boolean
  className?: string
}

export default function Markdown({
  children,
  forceWhiteText = false,
  className = ''
}: MarkdownProps) {
  const [modalCode, setModalCode] = useState<string | null>(null)

  const getCompactProseClasses = () => {
    const baseClasses = 'prose prose-sm max-w-none'

    const compactSpacing = [
      '[&>*:first-child]:mt-0',
      '[&>*:last-child]:mb-0',
      '[&>p]:my-1',
      '[&>p]:leading-snug',
      '[&>ul]:my-1',
      '[&>ol]:my-1',
      '[&>li]:my-0',
      '[&>h1]:my-2',
      '[&>h2]:my-2',
      '[&>h3]:my-1',
      '[&>h4]:my-1',
      '[&>h5]:my-1',
      '[&>h6]:my-1',
      '[&>blockquote]:my-2',
      '[&>pre]:my-2',
      '[&>table]:my-2',
      'leading-snug'
    ].join(' ')

    const colorClasses = forceWhiteText
      ? 'prose-invert'
      : 'dark:prose-invert'

    return `${baseClasses} ${compactSpacing} ${colorClasses}`
  }

  const combinedClassName = `text-left ${getCompactProseClasses()} ${className}`.trim()

  const components: Components = useMemo(() => ({
    code({ className, children, ...props }) {
      const match = /language-(\w+)/.exec(className || '')
      const language = match ? match[1] : undefined
      const codeString = String(children).replace(/\n$/, '')

      // Check if this is a block code (has className with language) vs inline
      const isBlock = className?.includes('language-')

      if (!isBlock) {
        return (
          <code className={className} {...props}>
            {children}
          </code>
        )
      }

      if (language === 'mermaid') {
        return (
          <MermaidDiagram
            code={codeString}
            onExpandClick={() => setModalCode(codeString)}
          />
        )
      }

      return <CodeBlock code={codeString} language={language} />
    },
    pre({ children }) {
      // Return children directly since CodeBlock/MermaidDiagram handle their own wrapping
      return <>{children}</>
    }
  }), [])

  return (
    <>
      <div className={combinedClassName}>
        <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
          {children}
        </ReactMarkdown>
      </div>

      <MermaidDiagramModal
        isOpen={modalCode !== null}
        onClose={() => setModalCode(null)}
        code={modalCode || ''}
      />
    </>
  )
}
