import { afterEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import App from './App'

function mockJsonResponse(payload: unknown): Response {
  return {
    ok: true,
    status: 200,
    json: async () => payload,
  } as Response
}

describe('App', () => {
  afterEach(() => {
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
  })

  it('shows visual surface before prompt composer and supports drawer tools flow', async () => {
    const fetchMock = vi.fn<typeof fetch>()
    fetchMock
      .mockResolvedValueOnce(
        mockJsonResponse({
          session_id: 's1',
          turn_id: 't1',
          text: 'OpenCommotion: moonwalk demo.',
          voice: { voice: 'opencommotion-local', segments: [] },
          visual_patches: [{ op: 'add', path: '/actors/guide' }],
          timeline: { duration_ms: 1200 },
        }),
      )
      .mockResolvedValueOnce(mockJsonResponse({ ok: true }))
      .mockResolvedValueOnce(
        mockJsonResponse({
          results: [{ artifact_id: 'artifact-1', title: 'Moonwalk Demo' }],
        }),
      )

    vi.stubGlobal('fetch', fetchMock)

    const user = userEvent.setup()
    render(<App />)

    const visualHeading = screen.getByRole('heading', { name: 'Visual Surface' })
    const composerHeading = screen.getByRole('heading', { name: 'Prompt Composer' })
    expect(visualHeading.compareDocumentPosition(composerHeading) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(screen.getByTestId('turn-status')).toHaveTextContent('Turn status: Ready')

    const saveButton = screen.getByRole('button', { name: 'Save' })
    expect(saveButton).toBeDisabled()

    await user.click(screen.getByRole('button', { name: 'Run Turn' }))
    await screen.findByText('OpenCommotion: moonwalk demo.')
    expect(screen.getByTestId('turn-status')).toHaveTextContent('Turn status: Completed')
    expect(screen.getByText(/Patch count:\s*1/)).toBeInTheDocument()
    expect(saveButton).toBeEnabled()

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      'http://127.0.0.1:8000/v2/orchestrate',
      expect.objectContaining({ method: 'POST' }),
    )

    await user.click(saveButton)
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      'http://127.0.0.1:8000/v1/artifacts/save',
      expect.objectContaining({ method: 'POST' }),
    )

    await user.click(screen.getByRole('button', { name: 'Tools' }))
    await screen.findByRole('heading', { name: 'Agent Run Manager' })
    await user.type(screen.getByPlaceholderText('search artifacts'), 'moonwalk')
    await user.click(screen.getByRole('button', { name: 'Search' }))

    expect(fetchMock).toHaveBeenNthCalledWith(
      3,
      'http://127.0.0.1:8000/v1/artifacts/search?q=moonwalk&mode=hybrid',
      expect.objectContaining({ headers: expect.any(Object) }),
    )
    await screen.findByText('Moonwalk Demo')
  })
})
