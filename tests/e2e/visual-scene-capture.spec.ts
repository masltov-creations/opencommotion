/**
 * Visual scene screenshot suite — captures rendering output for each test prompt.
 * Run: npx playwright test tests/e2e/visual-scene-capture.spec.ts
 *
 * Screenshots go to docs/assets/scenes/ for the docs.
 */

import { expect, test, type Page } from '@playwright/test'
import * as path from 'path'
import * as fs from 'fs'

const OUT_DIR = path.resolve(__dirname, '..', '..', 'docs', 'assets', 'scenes')

async function submitPromptAndWait(page: Page, prompt: string): Promise<void> {
  const textarea = page.getByRole('textbox', { name: /prompt input/i })
  await textarea.fill(prompt)
  await page.getByRole('button', { name: /Run Turn/i }).click()
  // Wait for the turn-status to read "Completed" or "Failed"
  const statusEl = page.getByTestId('turn-status')
  await expect(statusEl).toContainText(/Completed|Failed/, { timeout: 30_000 })
  // Let the animation begin to play
  await page.waitForTimeout(2_000)
}

async function saveSceneShot(page: Page, label: string, testInfo: { attach: (name: string, options: { body: Buffer; contentType: string }) => Promise<void> }): Promise<void> {
  fs.mkdirSync(OUT_DIR, { recursive: true })
  const buf = await page.screenshot({ fullPage: false })
  const file = path.join(OUT_DIR, `${label}.png`)
  fs.writeFileSync(file, buf)
  await testInfo.attach(label, { body: buf, contentType: 'image/png' })
}

const SCENE_PROMPTS: [string, string][] = [
  ['ui-baseline', ''],
  ['rocket-motion', 'draw a rocket with motion'],
  ['house', 'draw a house'],
  ['sunset', 'draw a sunset'],
  ['planet-ring', 'draw a planet'],
  ['butterfly-3d', 'draw a 3D butterfly'],
  ['cloud', 'draw a cloud'],
  ['moon', 'show the moon'],
  ['car-red', 'draw a red car'],
  ['wave-ocean', 'show the ocean'],
]

for (const [label, prompt] of SCENE_PROMPTS) {
  test(`capture: ${label}`, async ({ page }, testInfo) => {
    testInfo.setTimeout(90_000)
    await page.setViewportSize({ width: 1366, height: 768 })
    await page.goto('/')
    await expect(page.locator('[data-testid="visual-stage-card"]')).toBeVisible({ timeout: 15_000 })

    if (prompt) {
      await submitPromptAndWait(page, prompt)
    } else {
      await page.waitForTimeout(1_500)
    }

    await saveSceneShot(page, label, testInfo)
  })
}

test('entity decomposition: rocket API response has move op', async ({ page }) => {
  // Verify via orchestrator API that "draw a rocket with motion" produces a move op
  const res = await page.request.post('http://127.0.0.1:8001/v1/orchestrate', {
    data: {
      session_id: 'screenshot-test-rocket',
      prompt: 'draw a rocket with motion',
    },
  })
  expect(res.ok()).toBeTruthy()
  const payload = await res.json()
  const strokes: { kind: string; params: { program?: { commands: { op: string; target_id?: string }[] } } }[] =
    payload.visual_strokes ?? []
  const script = strokes.find((s) => s.kind === 'runScreenScript')
  expect(script).toBeTruthy()
  const cmds = script!.params.program!.commands
  const moveOp = cmds.find((c) => c.op === 'move' && c.target_id === 'rocket_body')
  expect(moveOp).toBeTruthy()
})

test('entity decomposition: house API response has rect walls', async ({ page }) => {
  const res = await page.request.post('http://127.0.0.1:8001/v1/orchestrate', {
    data: {
      session_id: 'screenshot-test-house',
      prompt: 'draw a house',
    },
  })
  expect(res.ok()).toBeTruthy()
  const payload = await res.json()
  const strokes = payload.visual_strokes ?? []
  const script = strokes.find((s: { kind: string }) => s.kind === 'runScreenScript')
  expect(script).toBeTruthy()
  const cmds = (script as { params: { program: { commands: { op: string; id?: string }[] } } }).params.program.commands
  expect(cmds.some((c) => c.op === 'rect' && c.id === 'house_walls')).toBeTruthy()
  expect(cmds.some((c) => c.op === 'polygon' && c.id === 'house_roof')).toBeTruthy()
})

test('market growth prompt never produces chart strokes', async ({ page }) => {
  // Pre-canned scenes are fully deleted — market-growth prompt must never return drawAdoptionCurve
  const res = await page.request.post('http://127.0.0.1:8001/v1/orchestrate', {
    data: {
      session_id: 'screenshot-test-market',
      prompt: 'animated presentation showcasing market growth and increases in segmented attach',
    },
  })
  expect(res.ok()).toBeTruthy()
  const payload = await res.json()
  const strokes: { kind: string }[] = payload.visual_strokes ?? []
  const kinds = strokes.map((s) => s.kind)
  expect(kinds).not.toContain('drawAdoptionCurve')
  expect(kinds).not.toContain('drawSegmentedAttachBars')
})
