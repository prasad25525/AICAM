import { expect, test } from '@playwright/test'
import { apiToken, createCamera, createTestEvent, login, resetData, SCREENSHOTS } from './helpers'
import { TEST_VIDEO } from './paths'

test.setTimeout(60_000)
test.beforeEach(({ request }) => resetData(request))

test('turn pop-up alerts and event recording off and on', async ({ page, request }) => {
  const cameraId = await createCamera(request, { name: 'Prep cam', source_url: TEST_VIDEO })
  await login(page)
  await expect(page.getByRole('status', { name: 'Live alerts connected' })).toBeVisible({ timeout: 10_000 })
  await page.getByRole('navigation').getByRole('link', { name: 'Settings' }).click()
  await expect(page).toHaveURL(/\/settings$/)

  const popups = page.getByRole('switch', { name: 'Pop-up alerts' })
  const recording = page.getByRole('switch', { name: 'Record events' })
  await expect(popups).toHaveAttribute('aria-checked', 'true')
  await expect(recording).toHaveAttribute('aria-checked', 'true')

  await test.step('pop-ups off: event is saved, nothing pops up', async () => {
    await popups.click()
    await expect(popups).toHaveAttribute('aria-checked', 'false')
    await expect(page.getByLabel('Critical')).toBeDisabled() // severity choice only matters when pop-ups are on
    await createTestEvent(request, cameraId, 'no_gloves')
    await page.waitForTimeout(3_000)
    await expect(page.getByRole('alert', { name: /New alert/ })).toHaveCount(0)
    await expect(page.getByRole('link', { name: 'Notifications: 1 open events' })).toBeVisible() // still recorded
    await page.screenshot({ path: `${SCREENSHOTS}/25-settings.png` })
  })

  await test.step('only critical pops up', async () => {
    await popups.click()
    await page.getByLabel('Warning').uncheck()
    await page.getByLabel('Info').uncheck()
    await expect(page.getByLabel('Info')).not.toBeChecked()
    await createTestEvent(request, cameraId, 'no_mask') // warning
    await page.waitForTimeout(3_000)
    await expect(page.getByRole('status', { name: 'New alert: No mask' })).toHaveCount(0)
    await createTestEvent(request, cameraId, 'no_gloves') // critical
    await expect(page.getByRole('alert', { name: 'New alert: No gloves' })).toBeVisible({ timeout: 4_000 })
  })

  await test.step('settings are kept after a reload; Events page warns when recording is off', async () => {
    await recording.click()
    await expect(recording).toHaveAttribute('aria-checked', 'false')
    await page.reload()
    await expect(page.getByRole('switch', { name: 'Record events' })).toHaveAttribute('aria-checked', 'false')
    await expect(page.getByLabel('Warning')).not.toBeChecked()
    await page.getByRole('navigation').getByRole('link', { name: /Events & Alerts/ }).click()
    await expect(page.getByRole('status').filter({ hasText: 'Event recording is off' })).toBeVisible()
    await page.getByRole('link', { name: 'Settings →' }).click()
    await expect(page).toHaveURL(/\/settings$/)
  })

  const headers = await apiToken(request)
  const s = await (await request.get('/api/settings', { headers })).json()
  expect(s).toEqual({ events_enabled: false, notifications_enabled: true, notify_severities: ['critical'] })
})
