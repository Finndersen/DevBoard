/**
 * Modal component for rendering HTML content in a sandboxed iframe.
 * Opened from the Expand button in HtmlPreview for full-screen viewing.
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
        className="w-full h-[75vh] border-none"
      />
    </Modal>
  )
}
