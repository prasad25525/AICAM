import { expect, test, type Page } from '@playwright/test'
import { apiToken, createCamera, createTestEvent, login, resetData, SCREENSHOTS } from './helpers'
import { TEST_VIDEO } from './paths'

test.setTimeout(60_000)

let cameraId: number
test.beforeEach(async ({ page, request }) => {
  await resetData(request)
  cameraId = await createCamera(request, { name: 'Prep cam', source_url: TEST_VIDEO })
  // Count generated alert tones (one oscillator per beep).
  await page.addInitScript(() => {
    const w = window as unknown as { __beeps: number }
    w.__beeps = 0
    const orig = AudioContext.prototype.createOscillator
    AudioContext.prototype.createOscillator = function () {
      w.__beeps += 1
      return orig.call(this)
    }
  })
})

const beeps = (page: Page) => page.evaluate(() => (window as unknown as { __beeps: number }).__beeps)
// Faster than the 10-15s polling, so passing proves the push channel did it.
const PUSH_TIMEOUT = 4_000

async function loginLive(page: Page) {
  await login(page)
  await expect(page.getByRole('status', { name: 'Live alerts connected' })).toBeVisible({ timeout: 10_000 })
  await page.getByText('Violations by hour (today)').click() // a user gesture, so the browser allows sound
}

test('critical alert pops up instantly, beeps, stays, and links to Events', async ({ page, request }) => {
  await loginLive(page)
  await expect(page.getByLabel('Open alerts', { exact: true })).toContainText('0')

  await createTestEvent(request, cameraId, 'no_gloves')
  const toast = page.getByRole('alert', { name: 'New alert: No gloves' })
  await expect(toast).toBeVisible({ timeout: PUSH_TIMEOUT })
  await expect(toast).toContainText('Prep cam')
  await expect(toast).toContainText('Critical')
  await expect.poll(() => toast.locator('img').evaluate((el: HTMLImageElement) => el.naturalWidth)).toBeGreaterThan(0)
  expect(await beeps(page)).toBe(3)
  await page.screenshot({ path: `${SCREENSHOTS}/18-live-alert.png` })

  // Pushed update refreshes the dashboard and badges without waiting for polling.
  await expect(page.getByLabel('Open alerts', { exact: true })).toContainText('1', { timeout: PUSH_TIMEOUT })
  await expect(page.getByRole('link', { name: 'Notifications: 1 open events' })).toBeVisible({ timeout: PUSH_TIMEOUT })

  await page.waitForTimeout(11_000)
  await expect(toast).toBeVisible() // critical alerts stay until dismissed

  await toast.getByRole('button', { name: 'View in Events & Alerts →' }).click()
  await expect(page).toHaveURL(/\/events$/)
  await expect(toast).toHaveCount(0)
})

test('info alerts fade on their own; dismiss works; changes elsewhere show up live', async ({ page, request }) => {
  await loginLive(page)

  const infoId = await createTestEvent(request, cameraId, 'bin_open')
  const info = page.getByRole('status', { name: 'New alert: Bin lid open' })
  await expect(info).toBeVisible({ timeout: PUSH_TIMEOUT })
  expect(await beeps(page)).toBe(0) // info is silent
  await expect(info).toHaveCount(0, { timeout: 9_000 }) // fades after ~6s

  await createTestEvent(request, cameraId, 'no_mask')
  const warning = page.getByRole('status', { name: 'New alert: No mask' })
  await expect(warning).toBeVisible({ timeout: PUSH_TIMEOUT })
  expect(await beeps(page)).toBe(1)
  await warning.getByRole('button', { name: 'Dismiss alert' }).click()
  await expect(warning).toHaveCount(0)

  // Someone else resolves an event: this browser's counts update without a reload.
  await expect(page.getByLabel('Open alerts', { exact: true })).toContainText('2', { timeout: PUSH_TIMEOUT })
  const headers = await apiToken(request)
  await request.patch(`/api/events/${infoId}`, { headers, data: { status: 'resolved' } })
  await expect(page.getByLabel('Open alerts', { exact: true })).toContainText('1', { timeout: PUSH_TIMEOUT })
})

test('mute silences alerts and is remembered', async ({ page, request }) => {
  await loginLive(page)
  await page.getByRole('button', { name: 'Mute alert sound' }).click()
  await expect(page.getByRole('button', { name: 'Unmute alert sound' })).toHaveAttribute('aria-pressed', 'true')

  await createTestEvent(request, cameraId, 'no_gloves')
  await expect(page.getByRole('alert', { name: 'New alert: No gloves' })).toBeVisible({ timeout: PUSH_TIMEOUT })
  expect(await beeps(page)).toBe(0)

  await page.reload()
  await expect(page.getByRole('button', { name: 'Unmute alert sound' })).toBeVisible()
})
