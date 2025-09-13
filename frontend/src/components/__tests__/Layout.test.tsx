import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import Layout from '../Layout'

// Helper function to render Layout with specific location
const renderWithRouter = (initialEntries: string[] = ['/']) => {
  return render(
    <MemoryRouter initialEntries={initialEntries}>
      <Layout>
        <div>Test Content</div>
      </Layout>
    </MemoryRouter>
  )
}

describe('Layout', () => {

  it('renders navigation header with logo and links', () => {
    renderWithRouter()

    // Check logo
    expect(screen.getByText('DevBoard')).toBeInTheDocument()
    
    // Check navigation links
    expect(screen.getByRole('link', { name: /projects/i })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /settings/i })).toBeInTheDocument()
  })

  it('renders children content in main area', () => {
    render(
      <MemoryRouter>
        <Layout>
          <div data-testid="child-content">Test Content</div>
        </Layout>
      </MemoryRouter>
    )

    expect(screen.getByTestId('child-content')).toBeInTheDocument()
    expect(screen.getByText('Test Content')).toBeInTheDocument()
  })

  it('has correct navigation link hrefs', () => {
    renderWithRouter()

    const logoLink = screen.getByText('DevBoard').closest('a')
    expect(logoLink).toHaveAttribute('href', '/')

    const projectsLink = screen.getByRole('link', { name: /projects/i })
    expect(projectsLink).toHaveAttribute('href', '/projects')

    const settingsLink = screen.getByRole('link', { name: /settings/i })
    expect(settingsLink).toHaveAttribute('href', '/settings')
  })

  it('highlights active navigation link based on current route', () => {
    renderWithRouter(['/projects'])

    const projectsLink = screen.getByRole('link', { name: /projects/i })
    const settingsLink = screen.getByRole('link', { name: /settings/i })

    // Projects link should be active
    expect(projectsLink).toHaveClass('text-blue-600', 'bg-blue-50')
    
    // Settings link should not be active
    expect(settingsLink).toHaveClass('text-gray-700')
    expect(settingsLink).not.toHaveClass('text-blue-600')
  })

  it('highlights settings link when on settings page', () => {
    renderWithRouter(['/settings'])

    const projectsLink = screen.getByRole('link', { name: /projects/i })
    const settingsLink = screen.getByRole('link', { name: /settings/i })

    // Settings link should be active
    expect(settingsLink).toHaveClass('text-blue-600', 'bg-blue-50')
    
    // Projects link should not be active
    expect(projectsLink).toHaveClass('text-gray-700')
    expect(projectsLink).not.toHaveClass('text-blue-600')
  })

  it('highlights projects link for project detail pages', () => {
    renderWithRouter(['/projects/1'])

    const projectsLink = screen.getByRole('link', { name: /projects/i })
    
    // Projects link should be active for project detail pages
    expect(projectsLink).toHaveClass('text-blue-600', 'bg-blue-50')
  })

  it('does not highlight projects link for task detail pages', () => {
    renderWithRouter(['/tasks/1'])

    const projectsLink = screen.getByRole('link', { name: /projects/i })
    
    // Projects link should not be active for task detail pages
    expect(projectsLink).toHaveClass('text-gray-700')
    expect(projectsLink).not.toHaveClass('text-blue-600')
  })

  it('does not highlight any link for unknown routes', () => {
    renderWithRouter(['/unknown'])

    const projectsLink = screen.getByRole('link', { name: /projects/i })
    const settingsLink = screen.getByRole('link', { name: /settings/i })

    // No link should be active
    expect(projectsLink).toHaveClass('text-gray-700')
    expect(settingsLink).toHaveClass('text-gray-700')
    expect(projectsLink).not.toHaveClass('text-blue-600')
    expect(settingsLink).not.toHaveClass('text-blue-600')
  })

  it('has responsive design classes', () => {
    renderWithRouter()

    // Check for responsive layout structure
    const nav = screen.getByRole('navigation')
    expect(nav).toHaveClass('border-b')
    
    const container = nav.querySelector('.max-w-7xl')
    expect(container).toHaveClass('mx-auto', 'px-4')
  })

  it('displays DevBoard logo correctly', () => {
    renderWithRouter()

    // Should have DB logo icon and DevBoard text
    expect(screen.getByText('DB')).toBeInTheDocument()
    expect(screen.getByText('DevBoard')).toBeInTheDocument()
  })

  it('has proper semantic HTML structure', () => {
    renderWithRouter()

    expect(screen.getByRole('navigation')).toBeInTheDocument()
    expect(screen.getByRole('main')).toBeInTheDocument()
  })

  it('supports dark mode classes', () => {
    renderWithRouter()

    const nav = screen.getByRole('navigation')
    expect(nav).toHaveClass('dark:border-gray-700', 'dark:bg-gray-800')
  })

  it('renders logo as a link to home page', () => {
    renderWithRouter()

    const logoLink = screen.getByText('DevBoard').closest('a')
    expect(logoLink).toHaveAttribute('href', '/')
    expect(logoLink).toHaveClass('flex', 'items-center', 'space-x-2')
    
    // DevBoard text should have the font classes
    const logoText = screen.getByText('DevBoard')
    expect(logoText).toHaveClass('text-xl', 'font-bold')
  })

  it('maintains consistent spacing and layout', () => {
    renderWithRouter()

    const main = screen.getByRole('main')
    expect(main).toHaveClass('max-w-7xl', 'mx-auto', 'py-6')
  })

  it('handles navigation link hover states', () => {
    renderWithRouter()

    const projectsLink = screen.getByRole('link', { name: /projects/i })
    // Check for transition-colors class which enables hover effects
    expect(projectsLink).toHaveClass('transition-colors')
  })

  it('properly structures navigation links', () => {
    renderWithRouter()

    // Check navigation links are present
    const projectsLink = screen.getByRole('link', { name: /projects/i })
    const settingsLink = screen.getByRole('link', { name: /settings/i })
    
    expect(projectsLink).toBeInTheDocument()
    expect(settingsLink).toBeInTheDocument()
  })

  it('supports keyboard navigation', () => {
    renderWithRouter()

    const projectsLink = screen.getByRole('link', { name: /projects/i })
    const settingsLink = screen.getByRole('link', { name: /settings/i })

    // Links should be focusable by default (no explicit tabIndex needed)
    expect(projectsLink).toBeVisible()
    expect(settingsLink).toBeVisible()
  })
})