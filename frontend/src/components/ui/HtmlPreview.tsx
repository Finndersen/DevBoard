import { useState, useEffect, useRef, useCallback } from 'react'
import CodeBlock from './CodeBlock'

interface HtmlPreviewProps {
  code: string
  language: 'html' | 'svg'
}

const MAX_HEIGHT = 500
const DEFAULT_HEIGHT = 150

const HEIGHT_MEASUREMENT_SCRIPT = `
<script>
(function() {
  function postHeight() {
    var h = document.documentElement.scrollHeight;
    window.parent.postMessage({ type: '__html_preview_resize', height: h }, '*');
  }
  window.addEventListener('load', postHeight);
  new ResizeObserver(postHeight).observe(document.documentElement);
  postHeight();
})();
</script>`

function buildSrcdoc(code: string): string {
  return `<!DOCTYPE html>
<html>
<head><style>body { margin: 0; background: white; }</style></head>
<body>${code}${HEIGHT_MEASUREMENT_SCRIPT}</body>
</html>`
}

export default function HtmlPreview({ code, language }: HtmlPreviewProps) {
  const [activeTab, setActiveTab] = useState<'preview' | 'source'>('preview')
  const [height, setHeight] = useState(DEFAULT_HEIGHT)
  const iframeRef = useRef<HTMLIFrameElement>(null)

  const handleMessage = useCallback((event: MessageEvent) => {
    if (
      event.data?.type === '__html_preview_resize' &&
      event.source === iframeRef.current?.contentWindow
    ) {
      const newHeight = Math.min(event.data.height, MAX_HEIGHT)
      setHeight(newHeight)
    }
  }, [])

  useEffect(() => {
    window.addEventListener('message', handleMessage)
    return () => window.removeEventListener('message', handleMessage)
  }, [handleMessage])

  const srcdoc = buildSrcdoc(code)

  return (
    <div className="border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden">
      <div role="tablist" className="flex items-center gap-1 px-3 py-1.5 bg-gray-50 dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700">
        <button
          type="button"
          role="tab"
          aria-selected={activeTab === 'preview'}
          onClick={() => setActiveTab('preview')}
          className={`px-2 py-0.5 text-xs font-medium rounded transition-colors ${
            activeTab === 'preview'
              ? 'bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 shadow-sm'
              : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'
          }`}
        >
          Preview
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={activeTab === 'source'}
          onClick={() => setActiveTab('source')}
          className={`px-2 py-0.5 text-xs font-medium rounded transition-colors ${
            activeTab === 'source'
              ? 'bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 shadow-sm'
              : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'
          }`}
        >
          Source
        </button>
        <span className="text-xs font-medium text-gray-500 dark:text-gray-400 ml-auto">
          {language.toUpperCase()}
        </span>
      </div>

      {activeTab === 'preview' ? (
        <iframe
          ref={iframeRef}
          srcDoc={srcdoc}
          sandbox="allow-scripts"
          title={`${language.toUpperCase()} Preview`}
          style={{ height: `${height}px` }}
          className="w-full border-none bg-white rounded-b-lg"
        />
      ) : (
        <CodeBlock code={code} language={language} />
      )}
    </div>
  )
}
