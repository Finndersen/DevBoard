import { useState, useMemo, useRef } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { Components } from 'react-markdown'
import type { ReactNode } from 'react'
import CodeBlock from './CodeBlock'
import HtmlPreview from './HtmlPreview'
import MermaidDiagram from './MermaidDiagram'
import MermaidDiagramModal from './MermaidDiagramModal'
import { generateSlug } from '../../utils/markdown'

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
  const [modalData, setModalData] = useState<{ code: string; svg: string } | null>(null)

  // Ref holds a fresh Set that is recreated before each render cycle.
  // The heading renderers (captured in the memoized `components`) read from
  // this ref, so they always use a clean Set even across re-renders.
  const slugTrackerRef = useRef(new Set<string>())
  slugTrackerRef.current = new Set<string>()

  function extractText(node: ReactNode): string {
    if (typeof node === 'string') return node
    if (typeof node === 'number') return String(node)
    if (Array.isArray(node)) return node.map(extractText).join('')
    if (node && typeof node === 'object' && 'props' in node) {
      return extractText((node as React.ReactElement).props.children)
    }
    return ''
  }

  function makeHeadingRenderer(level: number) {
    const Tag = `h${level}` as const
    return function HeadingWithId(props: React.HTMLAttributes<HTMLHeadingElement>) {
      const text = extractText(props.children as ReactNode)
      const slug = generateSlug(text, slugTrackerRef.current)
      return <Tag {...props} id={slug} />
    }
  }

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

      // Check if this is a block code (has className with language, or contains newlines) vs inline
      // Fenced code blocks without a language specifier have no className but still contain newlines
      const isBlock = className?.includes('language-') || String(children).includes('\n')

      if (!isBlock) {
        // Use bg-white/20 on coloured backgrounds (e.g. blue user bubble), otherwise use a shade
        // that contrasts with the bubble background (gray-100/gray-700).
        const inlineCodeClass = forceWhiteText
          ? 'bg-white/20 text-white rounded px-1 py-0.5 text-[0.85em] font-mono before:content-none after:content-none'
          : 'bg-gray-200 dark:bg-gray-600 text-gray-800 dark:text-gray-200 rounded px-1 py-0.5 text-[0.85em] font-mono before:content-none after:content-none'
        return (
          <code className={inlineCodeClass} {...props}>
            {children}
          </code>
        )
      }

      if (language === 'mermaid') {
        return (
          <MermaidDiagram
            code={codeString}
            onExpandClick={(svg) => setModalData({ code: codeString, svg })}
          />
        )
      }

      if (language === 'html' || language === 'svg') {
        return <HtmlPreview code={codeString} language={language} />
      }

      return <CodeBlock code={codeString} language={language} />
    },
    pre({ children }) {
      // Return children directly since CodeBlock/MermaidDiagram handle their own wrapping
      return <>{children}</>
    },
    h1: makeHeadingRenderer(1),
    h2: makeHeadingRenderer(2),
    h3: makeHeadingRenderer(3),
    h4: makeHeadingRenderer(4),
    h5: makeHeadingRenderer(5),
    h6: makeHeadingRenderer(6),
  }), [forceWhiteText])

  return (
    <>
      <div className={combinedClassName}>
        <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
          {children}
        </ReactMarkdown>
      </div>

      <MermaidDiagramModal
        isOpen={modalData !== null}
        onClose={() => setModalData(null)}
        code={modalData?.code ?? ''}
        svg={modalData?.svg ?? ''}
      />
    </>
  )
}
