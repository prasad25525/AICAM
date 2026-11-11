import { expect, test } from '@playwright/test'
import { apiToken, createCamera, login, resetData, SCREENSHOTS } from './helpers'
import { TEST_VIDEO } from './paths'

// The e2e fake detector: one person at the bottom-centre, a cup at the top-left (0.1-0.15).
test.setTimeout(90_000)

let cameraId: number
test.beforeEach(async ({ request }) => {
  await resetData(request)
  cameraId = await createCamera(request, { name: 'Dining cam', source_url: TEST_VIDEO })
})

test('zone rules: warnings for missing zones, then a "table not cleared" alert', async ({ page }) => {
  const headers = await apiToken(page.request)
  await page.request.post(`/api/cameras/${cameraId}/zones`, {
    headers,
    data: { name: 'Table 1', zone_type: 'dining_table', polygon: [[0, 0], [0.3, 0], [0.3, 0.3], [0, 0.3]] },
  })

  await login(page)
  await page.getByRole('navigation').getByRole('link', { name: 'Cameras' }).click()
  await page.getByRole('button', { name: 'Detection settings for Dining cam' }).click()
  const dialog = page.getByRole('dialog', { name: 'Detection · Dining cam' })

  await test.step('rules show which zones they need', async () => {
    const skipped = dialog.getByText('Hand wash skipped before prep').locator('..')
    await expect(skipped).toContainText('Needs a Hand-wash sink zone and a prep zone — none drawn yet')
    await expect(dialog.getByText('Table not cleared').locator('..')).toContainText('Uses Dining table zones')
    await expect(dialog.getByRole('link', { name: 'Zones page' })).toBeVisible()
    await expect(dialog.getByLabel('Wash at least (s)')).toHaveValue('20')
  })

  await test.step('only the table rule, cleared within 0.1 min (6s)', async () => {
    for (const label of ['Hair cap / hairnet', 'Face mask', 'Gloves', 'Apron', 'Hand wash skipped before prep', 'Hand wash too short']) {
      await dialog.getByLabel(label).uncheck()
    }
    await expect(dialog.getByLabel('Wash at least (s)')).toHaveCount(0) // hand-wash settings hide when unused
    await dialog.getByLabel('Clear table within (min)').fill('0.1')
    await dialog.getByText('Detect violations').click()
    await page.screenshot({ path: `${SCREENSHOTS}/21-zone-rules-settings.png` })
    await dialog.getByRole('button', { name: 'Save' }).click()
    await expect(dialog).toBeHidden()
  })

  await test.step('live view draws the tableware and the table timer', async () => {
    await page.getByRole('navigation').getByRole('link', { name: 'Live View' }).click()
    const overlay = page.getByRole('img', { name: 'Detections' })
    await expect(overlay.getByTestId('detection-object')).toHaveCount(1, { timeout: 20_000 })
    await expect(overlay.getByTestId('detection-object')).toContainText('cup')
    const badge = overlay.getByTestId('detection-table')
    await expect(badge).toContainText(/Table 1: (not cleared \d:\d\d \/ 0:06|NOT CLEARED)/)
    await expect(badge).toHaveAttribute('data-state', 'not_cleared', { timeout: 15_000 })
    await page.screenshot({ path: `${SCREENSHOTS}/26-live-table.png` })
  })

  await test.step('an alert arrives with the zone and what was left', async () => {
    const toast = page.getByRole('status', { name: 'New alert: Table not cleared' })
    await expect(toast).toBeVisible({ timeout: 30_000 })
    await page.getByRole('navigation').getByRole('link', { name: /Events & Alerts/ }).click()
    const row = page.getByRole('row', { name: /Table not cleared/ })
    await expect(row).toContainText('Table 1')
    await row.click()
    const detail = page.getByRole('dialog', { name: 'Table not cleared' })
    await expect(detail).toContainText(/Table 1 not cleared for \d+s \(cup left\)/) // under a minute, so shown in seconds
    // Shown visually: time left uncleared against the limit, and the items still on the table.
    const gauge = detail.getByRole('meter', { name: 'Left uncleared' })
    await expect(gauge).toContainText('/ 0.1 min limit')
    expect(Number(await gauge.getAttribute('aria-valuenow'))).toBeGreaterThanOrEqual(0.1)
    await expect(detail.getByRole('region', { name: 'Violation' })).toContainText('Still on the table:cup')
    await expect.poll(() => detail.getByRole('img').evaluate((el: HTMLImageElement) => el.naturalWidth)).toBe(640)
    await page.screenshot({ path: `${SCREENSHOTS}/22-table-event.png` })
  })

  await page.request.put(`/api/detection/cameras/${cameraId}/config`, { headers, data: { enabled: false } })
})
