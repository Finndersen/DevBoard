import { useState, useEffect, useRef, useCallback } from 'react'
import CodeBlock from './CodeBlock'
import HtmlRenderModal from './HtmlRenderModal'
import { borderColors, surfaces, textColors } from '../../styles/designSystem'

interface HtmlPreviewProps {
  code: string
  language: 'html' | 'svg'
}

const MAX_HEIGHT = 1000
const DEFAULT_HEIGHT = 300

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
  const [isModalOpen, setIsModalOpen] = useState(false)
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

  const openModal = () => setIsModalOpen(true)

  return (
    <div className={`border ${borderColors.default} rounded-lg overflow-hidden`}>
      <div
        role="tablist"
        className={`flex items-center gap-1 px-3 py-1.5 ${surfaces.sunken} border-b ${borderColors.default} ${activeTab === 'preview' ? 'cursor-pointer hover:brightness-95' : ''}`}
        onClick={activeTab === 'preview' ? openModal : undefined}
      >
        <button
          type="button"
          role="tab"
          aria-selected={activeTab === 'preview'}
          onClick={(e) => { e.stopPropagation(); setActiveTab('preview') }}
          className={`px-2 py-0.5 text-xs font-medium rounded transition-colors ${
            activeTab === 'preview'
              ? 'bg-white dark:bg-white/[0.06] text-gray-900 dark:text-gray-100 shadow-sm'
              : `${textColors.muted} hover:text-gray-700 dark:hover:text-gray-300`
          }`}
        >
          Preview
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={activeTab === 'source'}
          onClick={(e) => { e.stopPropagation(); setActiveTab('source') }}
          className={`px-2 py-0.5 text-xs font-medium rounded transition-colors ${
            activeTab === 'source'
              ? 'bg-white dark:bg-white/[0.06] text-gray-900 dark:text-gray-100 shadow-sm'
              : `${textColors.muted} hover:text-gray-700 dark:hover:text-gray-300`
          }`}
        >
          Source
        </button>
        <div className="ml-auto flex items-center gap-2">
          <span className={`text-xs font-medium ${textColors.muted}`}>
            {language.toUpperCase()}
          </span>
          <button
            type="button"
            onClick={(e) => { e.stopPropagation(); openModal() }}
            className={`px-2 py-0.5 text-xs font-medium rounded transition-colors ${textColors.muted} hover:text-gray-700 dark:hover:text-gray-300`}
            title="Expand to fullscreen"
            aria-label="Expand to fullscreen"
          >
            Expand ⛶
          </button>
        </div>
      </div>

      {activeTab === 'preview' ? (
        <iframe
          ref={iframeRef}
          srcDoc={srcdoc}
          sandbox="allow-scripts"
          title={`${language.toUpperCase()} Preview`}
          style={{ height: `${height}px` }}
          className="w-full border-none bg-white rounded-b-lg overflow-auto"
        />
      ) : (
        <CodeBlock code={code} language={language} />
      )}

      <HtmlRenderModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        title={`${language.toUpperCase()} Preview`}
        html={srcdoc}
      />
    </div>
  )
}
