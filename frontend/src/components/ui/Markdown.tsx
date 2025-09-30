import ReactMarkdown from 'react-markdown'

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
  const getCompactProseClasses = () => {
    // Base prose classes with compact spacing
    const baseClasses = 'prose prose-sm max-w-none'
    
    // Compact spacing for elements - reduced margins and line height
    const compactSpacing = [
      // Remove margins from first/last elements
      '[&>*:first-child]:mt-0',
      '[&>*:last-child]:mb-0',
      
      // Reduce paragraph spacing and line height
      '[&>p]:my-1',
      '[&>p]:leading-snug', // Tighter line height within paragraphs
      
      // Reduce list spacing
      '[&>ul]:my-1',
      '[&>ol]:my-1', 
      '[&>li]:my-0',
      
      // Reduce heading spacing
      '[&>h1]:my-2',
      '[&>h2]:my-2',
      '[&>h3]:my-1',
      '[&>h4]:my-1',
      '[&>h5]:my-1',
      '[&>h6]:my-1',
      
      // Reduce blockquote and code block spacing
      '[&>blockquote]:my-2',
      '[&>pre]:my-2',
      
      // Tighter line height for better compactness
      'leading-snug'
    ].join(' ')
    
    // Color classes - force white text when needed, otherwise use standard dark mode handling
    const colorClasses = forceWhiteText 
      ? 'prose-invert' // White text for colored backgrounds
      : 'dark:prose-invert' // Standard dark mode handling
    
    return `${baseClasses} ${compactSpacing} ${colorClasses}`
  }
  
  const combinedClassName = `text-left ${getCompactProseClasses()} ${className}`.trim()
  
  return (
    <div className={combinedClassName}>
      <ReactMarkdown>
        {children}
      </ReactMarkdown>
    </div>
  )
}