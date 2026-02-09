import { useState } from 'react'
import { ClipboardDocumentIcon, CheckIcon } from '@heroicons/react/24/outline'
import Modal from './Modal'
import MermaidDiagram from './MermaidDiagram'
import CodeBlock from './CodeBlock'

interface MermaidDiagramModalProps {
  isOpen: boolean
  onClose: () => void
  code: string
}

export default function MermaidDiagramModal({ isOpen, onClose, code }: MermaidDiagramModalProps) {
  const [copied, setCopied] = useState(false)

  const handleCopy = async () => {
    await navigator.clipboard.writeText(code)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Mermaid Diagram" maxWidth="6xl">
      <div className="space-y-6">
        <div className="border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden">
          <MermaidDiagram code={code} />
        </div>

        <div>
          <div className="flex items-center justify-between mb-2">
            <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Source Code
            </h4>
            <button
              onClick={handleCopy}
              className="inline-flex items-center gap-1.5 px-2 py-1 text-xs font-medium text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700 rounded transition-colors"
            >
              {copied ? (
                <>
                  <CheckIcon className="w-4 h-4 text-green-500" />
                  Copied!
                </>
              ) : (
                <>
                  <ClipboardDocumentIcon className="w-4 h-4" />
                  Copy Source
                </>
              )}
            </button>
          </div>
          <div className="max-h-64 overflow-auto rounded-lg border border-gray-200 dark:border-gray-700">
            <CodeBlock code={code} language="mermaid" />
          </div>
        </div>
      </div>
    </Modal>
  )
}
