import { expect, test } from '@playwright/test'

test('typed + voice + artifact flow', async ({ page }) => {
  await page.goto('/')

  await page.getByLabel('voice file').setInputFiles('tests/e2e/fixtures/voice-hint.txt')
  await page.getByRole('button', { name: 'Transcribe Audio' }).click()
  await expect(page.locator('.voice-panel .muted')).toHaveText(/moonwalk adoption voice sample/i)

  await page.getByRole('button', { name: 'Run Turn' }).click()
  await expect(page.getByText(/OpenCommotion:/)).toBeVisible()
  await expect(page.getByText(/Patch count:/)).toBeVisible()

  await page.getByRole('button', { name: 'Save', exact: true }).click()

  await page.getByPlaceholder('search artifacts').fill('Turn')
  await page.getByRole('button', { name: 'Search' }).click()
  await expect(page.locator('.results li').first()).toBeVisible()
})

test('setup wizard + run manager flow', async ({ page }) => {
  await page.goto('/?setup=1')
  await page.getByRole('button', { name: 'Load Wizard' }).click()
  await page.getByRole('button', { name: 'Validate Setup' }).click()
  await expect(page.getByText(/Setup validation passed|Unsupported/).first()).toBeVisible()

  await page.getByRole('button', { name: 'Create Run' }).click()
  await page.getByPlaceholder('queue prompt').fill('agent-run moonwalk verification')
  await page.getByRole('button', { name: 'Enqueue' }).click()
  await page.getByRole('button', { name: 'Run Once' }).click()

  await expect(page.getByText(/queue: q=/)).toBeVisible()
})
