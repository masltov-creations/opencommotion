import { expect, test, type Page } from '@playwright/test'

async function ensureToolsDrawerOpen(page: Page) {
  const drawer = page.locator('.tools-drawer')
  const isOpen = await drawer.evaluate((element) => element.classList.contains('open'))
  if (!isOpen) {
    await page.locator('.tools-toggle').click()
  }
}

test('typed + voice + artifact flow', async ({ page }) => {
  await page.setViewportSize({ width: 1366, height: 768 })
  await page.goto('/')

  const stageCard = page.locator('[data-testid="visual-stage-card"]')
  const composerCard = page.locator('[data-testid="prompt-composer"]')
  await expect(stageCard).toBeVisible()
  await expect(composerCard).toBeVisible()
  const stageBox = await stageCard.boundingBox()
  const composerBox = await composerCard.boundingBox()
  const viewport = page.viewportSize()
  expect(stageBox).toBeTruthy()
  expect(composerBox).toBeTruthy()
  expect(viewport).toBeTruthy()
  expect((stageBox?.y || 0) + (stageBox?.height || 0)).toBeLessThanOrEqual(viewport?.height || 0)
  expect((composerBox?.y || 0) + (composerBox?.height || 0)).toBeLessThanOrEqual(viewport?.height || 0)
  expect((stageBox?.y || 0)).toBeLessThan(composerBox?.y || 0)

  await ensureToolsDrawerOpen(page)
  await page.getByLabel('voice file').setInputFiles('tests/e2e/fixtures/voice-hint.txt')
  await page.getByRole('button', { name: 'Transcribe Audio' }).click()
  await expect(page.locator('.voice-panel .muted')).toHaveText(/moonwalk adoption voice sample/i)
  await page.getByRole('button', { name: 'Close', exact: true }).click()

  await page.getByRole('button', { name: 'Run Turn' }).click()
  await expect(page.getByText(/Patch count:/)).toBeVisible()
  await ensureToolsDrawerOpen(page)
  await expect(page.getByText(/OpenCommotion:/)).toBeVisible()
  await page.getByRole('button', { name: 'Close', exact: true }).click()

  await page.getByRole('button', { name: 'Save', exact: true }).click()

  await page.getByRole('button', { name: 'Open Tools' }).click()
  await page.getByPlaceholder('search artifacts').fill('Turn')
  await page.getByRole('button', { name: 'Search' }).click()
  await expect(page.locator('.results li').first()).toBeVisible()
})

test('setup wizard + run manager flow', async ({ page }) => {
  await page.goto('/?setup=1')
  await ensureToolsDrawerOpen(page)
  await page.getByRole('button', { name: 'Load Wizard' }).click()
  await page.getByRole('button', { name: 'Validate Setup' }).click()
  await expect(page.getByText(/Setup validation passed|Unsupported/).first()).toBeVisible()

  await page.getByRole('button', { name: 'Create Run' }).click()
  await page.getByPlaceholder('queue prompt').fill('agent-run moonwalk verification')
  await page.getByRole('button', { name: 'Enqueue' }).click()
  await page.getByRole('button', { name: 'Run Once' }).click()

  await expect(page.getByText(/queue: q=/)).toBeVisible()
})
