import { expect, test } from '@playwright/test'
import { apiToken, createCamera, createTestEvent, deleteAllCameras, deleteAllEvents, login, SCREENSHOTS } from './helpers'
import { TEST_VIDEO } from './paths'

test.beforeEach(async ({ request }) => {
  await deleteAllEvents(request)
  await deleteAllCameras(request)
})

const tile = (page: import('@playwright/test').Page, label: string) => page.getByLabel(label, { exact: true })

test('empty dashboard shows real zeros, not sample data', async ({ page }) => {
  await login(page)
  await expect(tile(page, 'Hygiene score')).toContainText('100/100')
  await expect(tile(page, 'Open alerts')).toContainText('0')
  await expect(tile(page, 'Violations today')).toContainText('0')
  await expect(page.getByText('No violations today.')).toBeVisible()
  await expect(page.getByText('No alerts yet.')).toBeVisible()
  await expect(page.getByText('No cameras added.')).toBeVisible()
  await expect(page.getByText('Showing sample data')).toHaveCount(0)
})

test('dashboard reflects events, score, and false alarms', async ({ page, request }) => {
  const cameraId = await createCamera(request, { name: 'Test pattern', source_url: TEST_VIDEO })
  await createTestEvent(request, cameraId, 'no_gloves') // critical: -5
  await createTestEvent(request, cameraId, 'no_mask') // warning: -2
  const binId = await createTestEvent(request, cameraId, 'bin_open') // info: -0.5
  await login(page)

  // 100 - 5 - 2 - 0.5 = 92.5 -> 92 (rounded half to even) or 93; accept either rounding.
  await expect(tile(page, 'Hygiene score')).toContainText(/9[23]\/100/)
  await expect(tile(page, 'Hygiene score')).toHaveAttribute('title', /100 − 5 per critical/)
  await expect(tile(page, 'Open alerts')).toContainText('3')
  await expect(tile(page, 'Open alerts')).toContainText('1 critical')
  await expect(tile(page, 'Violations today')).toContainText('3')

  const byType = page.getByRole('list', { name: 'Violations by type' })
  await expect(byType.getByRole('listitem')).toHaveCount(3)
  await expect(byType).toContainText('No gloves')

  const recent = page.getByRole('table', { name: 'Recent alerts' })
  await expect(recent.getByRole('row')).toHaveCount(4) // header + 3
  await expect(recent).toContainText('Test pattern')
  await expect(page.getByRole('list', { name: 'Camera status' })).toContainText('Test pattern')
  await page.screenshot({ path: `${SCREENSHOTS}/13-dashboard-live.png`, fullPage: true })

  // A false alarm no longer counts against the score.
  const headers = await apiToken(request)
  await request.patch(`/api/events/${binId}`, { headers, data: { status: 'false_alarm' } })
  await page.reload()
  await expect(tile(page, 'Hygiene score')).toContainText('93/100')
  await expect(tile(page, 'Violations today')).toContainText('2')
  await expect(tile(page, 'Open alerts')).toContainText('2')

  await tile(page, 'Open alerts').click()
  await expect(page).toHaveURL(/\/events$/)
})
