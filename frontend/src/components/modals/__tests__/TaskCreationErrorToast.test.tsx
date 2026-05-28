import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { render } from '../../../test/utils'
import TaskCreationErrorToast from '../TaskCreationErrorToast'
import { useUIStore } from '../../../stores/uiStore'
import type { ModalDraft } from '../../../stores/uiStore'

const TEST_DRAFT_ID = 'test-error-draft'

function makeErrorDraft(errorMessage: string, overrides: Partial<ModalDraft> = {}): ModalDraft {
  return {
    type: 'task',
    formData: { prompt: 'Fix auth bug' },
    previewLabel: 'Fix auth bug',
    createdAt: Date.now(),
    isCreating: false,
    creationError: errorMessage,
    ...overrides,
  }
}

describe('TaskCreationErrorToast', () => {
  beforeEach(() => {
    useUIStore.setState({ modalDrafts: {}, openModalDraft: null })
  })

  it('renders nothing when no drafts have errors', () => {
    render(<TaskCreationErrorToast />)

    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('renders nothing when draft error is empty string', () => {
    useUIStore.setState({
      modalDrafts: { [TEST_DRAFT_ID]: makeErrorDraft('') },
    })

    render(<TaskCreationErrorToast />)

    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('renders toast when a draft has a creationError', () => {
    useUIStore.setState({
      modalDrafts: { [TEST_DRAFT_ID]: makeErrorDraft('Could not reach the server.') },
    })

    render(<TaskCreationErrorToast />)

    expect(screen.getByRole('alert')).toBeInTheDocument()
    expect(screen.getByText('Task creation failed')).toBeInTheDocument()
    expect(screen.getByText('Could not reach the server.')).toBeInTheDocument()
  })

  it('renders Retry and Dismiss buttons in the toast', () => {
    useUIStore.setState({
      modalDrafts: { [TEST_DRAFT_ID]: makeErrorDraft('API error') },
    })

    render(<TaskCreationErrorToast />)

    expect(screen.getByRole('button', { name: 'Retry' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Dismiss' })).toBeInTheDocument()
  })

  it('calls openExistingDraft with draftId when Retry is clicked', async () => {
    const openExistingDraftSpy = vi.spyOn(useUIStore.getState(), 'openExistingDraft')
    const user = userEvent.setup()

    useUIStore.setState({
      modalDrafts: { [TEST_DRAFT_ID]: makeErrorDraft('Network error') },
    })

    render(<TaskCreationErrorToast />)

    await user.click(screen.getByRole('button', { name: /Retry/i }))

    expect(openExistingDraftSpy).toHaveBeenCalledWith(TEST_DRAFT_ID)
    openExistingDraftSpy.mockRestore()
  })

  it('calls removeModalDraft with draftId when Dismiss button is clicked', async () => {
    const removeModalDraftSpy = vi.spyOn(useUIStore.getState(), 'removeModalDraft')
    const user = userEvent.setup()

    useUIStore.setState({
      modalDrafts: { [TEST_DRAFT_ID]: makeErrorDraft('Network error') },
    })

    render(<TaskCreationErrorToast />)

    await user.click(screen.getByRole('button', { name: 'Dismiss' }))

    expect(removeModalDraftSpy).toHaveBeenCalledWith(TEST_DRAFT_ID)
    removeModalDraftSpy.mockRestore()
  })

  it('calls removeModalDraft with draftId when × icon button is clicked', async () => {
    const removeModalDraftSpy = vi.spyOn(useUIStore.getState(), 'removeModalDraft')
    const user = userEvent.setup()

    useUIStore.setState({
      modalDrafts: { [TEST_DRAFT_ID]: makeErrorDraft('Timeout') },
    })

    render(<TaskCreationErrorToast />)

    await user.click(screen.getByRole('button', { name: /Dismiss error/i }))

    expect(removeModalDraftSpy).toHaveBeenCalledWith(TEST_DRAFT_ID)
    removeModalDraftSpy.mockRestore()
  })

  it('renders one toast per draft with an error', () => {
    useUIStore.setState({
      modalDrafts: {
        'draft-a': makeErrorDraft('Error A'),
        'draft-b': makeErrorDraft('Error B'),
      },
    })

    render(<TaskCreationErrorToast />)

    expect(screen.getAllByRole('alert')).toHaveLength(2)
    expect(screen.getByText('Error A')).toBeInTheDocument()
    expect(screen.getByText('Error B')).toBeInTheDocument()
  })

  it('openExistingDraft sets openModalDraft and clears error state', () => {
    useUIStore.setState({
      modalDrafts: {
        [TEST_DRAFT_ID]: makeErrorDraft('Network error', { formData: { prompt: 'Do something' } }),
      },
      openModalDraft: null,
    })

    useUIStore.getState().openExistingDraft(TEST_DRAFT_ID)

    const state = useUIStore.getState()
    expect(state.openModalDraft).toBe(TEST_DRAFT_ID)
    expect(state.modalDrafts[TEST_DRAFT_ID].creationError).toBeNull()
    expect(state.modalDrafts[TEST_DRAFT_ID].isCreating).toBe(false)
    expect(state.modalDrafts[TEST_DRAFT_ID].formData).toEqual({ prompt: 'Do something' })
  })
})
