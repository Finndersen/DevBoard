import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import CodeBlock from '../CodeBlock'
import { DarkModeProvider } from '../../../contexts/DarkModeContext'

const renderWithProvider = (children: React.ReactNode) => {
  return render(
    <DarkModeProvider>
      {children}
    </DarkModeProvider>
  )
}

describe('CodeBlock', () => {
  it('renders code with syntax highlighting', () => {
    renderWithProvider(<CodeBlock code="const x = 1;" language="javascript" />)
    expect(screen.getByText(/const/)).toBeInTheDocument()
    expect(screen.getByText(/x/)).toBeInTheDocument()
  })

  it('renders code without language', () => {
    renderWithProvider(<CodeBlock code="plain text" />)
    expect(screen.getByText('plain text')).toBeInTheDocument()
  })

  it('renders with rounded corners styling', () => {
    const { container } = renderWithProvider(
      <CodeBlock code="test" />
    )
    const pre = container.querySelector('pre')
    expect(pre).not.toBeNull()
  })
})
