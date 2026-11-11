import { expect, test } from '@playwright/test'
import { createCamera, deleteAllCameras, deleteAllEvents, login, SCREENSHOTS } from './helpers'
import { TEST_VIDEO } from './paths'

// The e2e backend runs the fake engine: one person, no mask, all other items worn.
test.setTimeout(90_000)

test.beforeEach(async ({ request }) => {
  await deleteAllEvents(request)
  await deleteAllCameras(request)
})

test('turn on detection, see boxes live, get an automatic event, turn it off', async ({ page, request }) => {
  await createCamera(request, { name: 'Line cam', source_url: TEST_VIDEO })
  await login(page)
  await expect(page.getByLabel('Detection status')).toContainText('Detection off')
  await page.getByRole('navigation').getByRole('link', { name: 'Cameras' }).click()

  await test.step('configure: alert after 1 second, all four checks', async () => {
    await page.getByRole('button', { name: 'Detection settings for Line cam' }).click()
    const dialog = page.getByRole('dialog', { name: 'Detection · Line cam' })
    for (const item of ['Hair cap / hairnet', 'Face mask', 'Gloves', 'Apron']) await expect(dialog.getByLabel(item)).toBeChecked()
    await dialog.getByLabel('Alert after (seconds)').fill('1')
    await dialog.getByText('Detect violations').click() // the switch is a styled label around a hidden checkbox
    await expect(dialog.getByLabel('Detect violations')).toBeChecked()
    await page.screenshot({ path: `${SCREENSHOTS}/14-detection-settings.png` })
    await dialog.getByRole('button', { name: 'Save' }).click()
    await expect(dialog).toBeHidden()
    await expect(page.getByRole('switch', { name: 'Stop detection on Line cam' })).toHaveAttribute('aria-checked', 'true')
    await expect(page.getByLabel('Detection status')).toContainText('Detecting on 1 camera', { timeout: 15_000 })
  })

  await test.step('live view draws the detection over the video', async () => {
    await page.getByRole('navigation').getByRole('link', { name: 'Live View' }).click()
    const tile = page.getByRole('figure').filter({ hasText: 'Line cam' })
    await expect(tile.getByLabel('Detection rate')).toContainText(/AI \d+\.\d\/s/, { timeout: 15_000 })
    const person = tile.getByTestId('detection-person')
    await expect(person).toHaveAttribute('data-violations', 'no_mask', { timeout: 10_000 })
    await expect(tile.getByRole('img', { name: 'Detections' })).toContainText('No mask')
    await expect(page.getByText('1 with detection')).toBeVisible()
    await page.screenshot({ path: `${SCREENSHOTS}/15-live-detection.png` })

    await page.getByLabel('Show detections').uncheck()
    await expect(tile.getByTestId('detection-person')).toHaveCount(0)
    await page.getByLabel('Show detections').check()
  })

  await test.step('an event was recorded automatically, with an annotated snapshot', async () => {
    await page.getByRole('navigation').getByRole('link', { name: /Events & Alerts/ }).click()
    const row = page.getByRole('row', { name: /No mask/ })
    await expect(row).toBeVisible({ timeout: 15_000 })
    await expect(row).toContainText('Line cam')
    await expect(row).not.toContainText('Test') // real detection, not a test event
    await expect(page.getByRole('row', { name: /No gloves|No apron|No hair cap/ })).toHaveCount(0) // worn items don't alert
    await row.click()
    const dialog = page.getByRole('dialog', { name: 'No mask' })
    await expect(dialog).toContainText('95%') // confidence
    const img = dialog.getByRole('img', { name: 'Snapshot of No mask' })
    await expect.poll(() => img.evaluate((el: HTMLImageElement) => el.naturalWidth)).toBe(640)
    await page.screenshot({ path: `${SCREENSHOTS}/16-detected-event.png` })
    await page.keyboard.press('Escape')
  })

  await test.step('turning detection off stops it', async () => {
    await page.getByRole('navigation').getByRole('link', { name: 'Cameras' }).click()
    await page.getByRole('switch', { name: 'Stop detection on Line cam' }).click()
    await expect(page.getByRole('switch', { name: 'Start detection on Line cam' })).toHaveAttribute('aria-checked', 'false')
    await expect(page.getByLabel('Detection status')).toContainText('Detection off', { timeout: 15_000 })
  })
})

test('detection switch is locked while the camera is disabled', async ({ page, request }) => {
  await createCamera(request, { name: 'Spare cam', source_url: TEST_VIDEO, enabled: false })
  await login(page)
  await page.getByRole('navigation').getByRole('link', { name: 'Cameras' }).click()
  await expect(page.getByRole('switch', { name: 'Start detection on Spare cam' })).toBeDisabled()
})
