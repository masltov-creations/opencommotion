import { afterEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import App from './App'

function mockJsonResponse(payload: unknown): Response {
  return {
    json: async () => payload,
  } as Response
}

describe('App', () => {
  afterEach(() => {
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
  })

  it('runs a turn, saves an artifact, and shows search results', async () => {
    const fetchMock = vi.fn<typeof fetch>()
    fetchMock
      .mockResolvedValueOnce(
        mockJsonResponse({
          text: 'OpenCommotion: moonwalk demo.',
          visual_patches: [{ op: 'add', path: '/actors/guide' }],
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

    const saveButton = screen.getByRole('button', { name: 'Save' })
    expect(saveButton).toBeDisabled()

    await user.click(screen.getByRole('button', { name: 'Run Turn' }))
    await screen.findByText('OpenCommotion: moonwalk demo.')
    expect(screen.getByText(/Patch count:\s*1/)).toBeInTheDocument()
    expect(saveButton).toBeEnabled()

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      'http://127.0.0.1:8000/v1/orchestrate',
      expect.objectContaining({ method: 'POST' }),
    )

    await user.click(saveButton)
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      'http://127.0.0.1:8000/v1/artifacts/save',
      expect.objectContaining({ method: 'POST' }),
    )

    await user.type(screen.getByPlaceholderText('search artifacts'), 'moonwalk')
    await user.click(screen.getByRole('button', { name: 'Search' }))

    expect(fetchMock).toHaveBeenNthCalledWith(
      3,
      'http://127.0.0.1:8000/v1/artifacts/search?q=moonwalk',
    )
    await screen.findByText('Moonwalk Demo')
  })
})
