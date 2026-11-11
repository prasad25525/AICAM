import { expect, test, type Page } from '@playwright/test'
import { createCamera, resetData, login, SCREENSHOTS } from './helpers'
import { TEST_VIDEO, UNREACHABLE_RTSP } from './paths'

// Unreachable streams take ~5s to time out.
test.setTimeout(60_000)
test.beforeEach(({ request }) => resetData(request))

async function openCameras(page: Page) {
  await login(page)
  await page.getByRole('navigation').getByRole('link', { name: 'Cameras' }).click()
  await expect(page).toHaveURL(/\/cameras$/)
  await expect(page.getByRole('heading', { level: 1, name: 'Cameras' })).toBeVisible()
}

test('test connection in the form: success preview, failure message, reset on change', async ({ page }) => {
  await openCameras(page)
  await page.getByRole('button', { name: 'Add camera' }).first().click()
  const dialog = page.getByRole('dialog', { name: 'Add camera' })
  await dialog.getByRole('radio', { name: 'Video file' }).click()
  await dialog.getByLabel('Video file path').fill(TEST_VIDEO)

  await dialog.getByRole('button', { name: 'Test connection' }).click()
  await expect(dialog.getByRole('status')).toContainText('Connected · 640×360 · 10 fps', { timeout: 15_000 })
  const preview = dialog.getByRole('img', { name: 'Test snapshot' })
  await expect(preview).toBeVisible()
  expect(await preview.evaluate((img: HTMLImageElement) => img.naturalWidth)).toBeGreaterThan(0)
  await page.screenshot({ path: `${SCREENSHOTS}/06-test-connection.png` })

  // Editing the source hides the old result.
  await dialog.getByLabel('Video file path').fill(`${TEST_VIDEO}x`)
  await expect(dialog.getByRole('status')).toHaveCount(0)

  await dialog.getByRole('radio', { name: 'Stream URL' }).click()
  await dialog.getByLabel('Stream URL').fill(UNREACHABLE_RTSP)
  await dialog.getByRole('button', { name: 'Test connection' }).click()
  await expect(dialog.getByRole('button', { name: 'Testing…' })).toBeDisabled()
  await expect(dialog.getByRole('status')).toContainText(/not reachable|Could not connect|Timed out/, { timeout: 25_000 })
  await expect(dialog.getByRole('img', { name: 'Test snapshot' })).toHaveCount(0)
})

test('status column: online, offline, disabled; snapshot viewer', async ({ page, request }) => {
  await createCamera(request, { name: 'Test pattern', source_url: TEST_VIDEO })
  await createCamera(request, { name: 'Dead IP cam', source_url: UNREACHABLE_RTSP })
  await createCamera(request, { name: 'Spare cam', source_url: TEST_VIDEO, enabled: false })
  await openCameras(page)

  // Opening the page runs a check of all enabled cameras.
  const good = page.getByRole('row', { name: /Test pattern/ })
  const dead = page.getByRole('row', { name: /Dead IP cam/ })
  const spare = page.getByRole('row', { name: /Spare cam/ })
  await expect(good).toContainText('Online', { timeout: 25_000 })
  await expect(good).toContainText('640×360')
  await expect(dead).toContainText('Offline')
  await expect(dead).toContainText(/not reachable|Could not connect|Timed out/)
  await expect(spare).toContainText('Disabled')
  await expect(page.getByText('3 cameras · 2 enabled · 1 online')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Snapshot Spare cam' })).toBeDisabled()
  await page.screenshot({ path: `${SCREENSHOTS}/07-camera-status.png`, animations: 'disabled' })

  await test.step('snapshot of a working camera, then refresh', async () => {
    await page.getByRole('button', { name: 'Snapshot Test pattern' }).click()
    const dialog = page.getByRole('dialog', { name: 'Snapshot · Test pattern' })
    const img = dialog.getByRole('img', { name: 'Snapshot from Test pattern' })
    await expect(img).toBeVisible({ timeout: 15_000 })
    expect(await img.evaluate((el: HTMLImageElement) => el.naturalWidth)).toBe(640)
    await expect(dialog).toContainText(/640×360 · taken at \d\d:\d\d:\d\d/)
    await page.screenshot({ path: `${SCREENSHOTS}/08-snapshot.png` })

    await dialog.getByRole('button', { name: 'Refresh' }).click()
    await expect(dialog.getByRole('button', { name: 'Refresh' })).toBeEnabled({ timeout: 15_000 })
    await expect(img).toBeVisible()
    await dialog.getByRole('button', { name: 'Close' }).first().click()
    await expect(dialog).toBeHidden()
  })

  await test.step('snapshot of an unreachable camera shows the reason', async () => {
    await page.getByRole('button', { name: 'Snapshot Dead IP cam' }).click()
    const dialog = page.getByRole('dialog', { name: 'Snapshot · Dead IP cam' })
    await expect(dialog.getByText('Connecting to camera…')).toBeVisible()
    await expect(dialog.getByRole('alert')).toContainText(/not reachable|Could not connect|Timed out/, { timeout: 25_000 })
    await expect(dialog.getByText('Camera unavailable')).toBeVisible()
    await page.keyboard.press('Escape')
  })

  await test.step('enabling a camera checks it straight away', async () => {
    await page.getByRole('switch', { name: 'Enable Spare cam' }).click()
    await expect(spare).toContainText('Online', { timeout: 25_000 })
    await expect(spare).toContainText('640×360')
    await page.getByRole('switch', { name: 'Disable Spare cam' }).click()
    await expect(spare).toContainText('Disabled')
  })

  await test.step('Check now re-checks all cameras', async () => {
    await page.getByRole('button', { name: 'Check now' }).click()
    await expect(page.getByRole('button', { name: 'Checking…' })).toBeDisabled()
    await expect(good).toContainText('Checking…')
    await expect(page.getByRole('button', { name: 'Check now' })).toBeEnabled({ timeout: 25_000 })
    await expect(good).toContainText('Online')
    await expect(dead).toContainText('Offline')
  })
})
