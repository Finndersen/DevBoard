import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { oneDark, oneLight } from 'react-syntax-highlighter/dist/esm/styles/prism'
import { useDarkMode } from '../../contexts/DarkModeContext'

interface CodeBlockProps {
  code: string
  language?: string
  className?: string
}

export default function CodeBlock({ code, language, className = '' }: CodeBlockProps) {
  const { isDarkMode } = useDarkMode()

  return (
    <SyntaxHighlighter
      language={language || 'text'}
      style={isDarkMode ? oneDark : oneLight}
      className={`rounded-md ${className}`}
      customStyle={{
        margin: 0,
        fontSize: '0.875rem',
        lineHeight: '1.5',
      }}
    >
      {code}
    </SyntaxHighlighter>
  )
}
