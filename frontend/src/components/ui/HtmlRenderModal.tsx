/**
 * Modal component for rendering HTML content in a sandboxed iframe.
 * Used by the render_html tool to display rich visualizations.
 */

import Modal from './Modal'

interface HtmlRenderModalProps {
  isOpen: boolean
  onClose: () => void
  title: string
  html: string
}

export default function HtmlRenderModal({ isOpen, onClose, title, html }: HtmlRenderModalProps) {
  return (
    <Modal isOpen={isOpen} onClose={onClose} title={title} maxWidth="screen" scrollable={false}>
      <iframe
        srcDoc={html}
        sandbox="allow-scripts"
        title={title}
        className="w-full h-full border-none"
      />
    </Modal>
  )
}
