import { expect, test } from '@playwright/test'
import { resetData, login, SCREENSHOTS } from './helpers'

// Uses the real webcam: scans and status checks take turns on the device, so allow extra time.
test.setTimeout(60_000)
test.beforeEach(({ request }) => resetData(request))

test('cameras: add webcam, validation, edit, toggle, delete', async ({ page }) => {
  await login(page)
  await page.getByRole('navigation').getByRole('link', { name: 'Cameras' }).click()

  await test.step('empty state', async () => {
    await expect(page.getByText('No cameras yet')).toBeVisible()
    await page.screenshot({ path: `${SCREENSHOTS}/03-cameras-empty.png` })
  })

  await test.step('add webcam camera', async () => {
    await page.getByRole('button', { name: 'Add camera' }).first().click()
    const dialog = page.getByRole('dialog', { name: 'Add camera' })
    await expect(dialog).toBeVisible()
    await expect(dialog.getByRole('radio', { name: 'Webcam' })).toHaveAttribute('aria-checked', 'true')

    // Wait for the webcam scan to finish; use the detected device if there is one.
    const device = dialog.getByRole('button', { name: /^Webcam 0/ })
    const none = dialog.getByText('No webcam found')
    await expect(device.or(none)).toBeVisible({ timeout: 20_000 })
    const detected = await device.isVisible()
    test.info().annotations.push({ type: 'webcam', description: detected ? 'Webcam 0 detected' : 'No webcam detected (typed 0 manually)' })
    if (detected) await device.click()
    else await dialog.getByLabel('Webcam number').fill('0')

    await dialog.getByLabel('Name', { exact: true }).fill('Laptop Webcam')
    await dialog.getByLabel('Location').fill('Test desk')
    await page.screenshot({ path: `${SCREENSHOTS}/04-camera-form.png` })
    await dialog.getByRole('button', { name: 'Add camera' }).click()
    await expect(dialog).toBeHidden()

    const row = page.getByRole('row', { name: /Laptop Webcam/ })
    await expect(row).toContainText('Test desk')
    await expect(row).toContainText('Kitchen')
    await expect(row).toContainText('Device 0')
    await expect(page.getByText('1 camera · 1 enabled')).toBeVisible()
  })

  await test.step('duplicate name is rejected with a message', async () => {
    await page.getByRole('button', { name: 'Add camera' }).first().click()
    const dialog = page.getByRole('dialog', { name: 'Add camera' })
    await dialog.getByLabel('Name', { exact: true }).fill('laptop webcam')
    await dialog.getByLabel('Webcam number').fill('0')
    await dialog.getByRole('button', { name: 'Add camera' }).click()
    await expect(dialog.getByRole('alert')).toHaveText('A camera named "laptop webcam" already exists')
    await dialog.getByRole('button', { name: 'Cancel' }).click()
    await expect(dialog).toBeHidden()
  })

  await test.step('missing video file is rejected with a message', async () => {
    await page.getByRole('button', { name: 'Add camera' }).first().click()
    const dialog = page.getByRole('dialog', { name: 'Add camera' })
    await dialog.getByLabel('Name', { exact: true }).fill('Recorded video')
    await dialog.getByRole('radio', { name: 'Video file' }).click()
    await dialog.getByLabel('Video file path').fill('C:\\does-not-exist\\kitchen.mp4')
    await dialog.getByRole('button', { name: 'Add camera' }).click()
    await expect(dialog.getByRole('alert')).toContainText('Video file not found')
    await page.keyboard.press('Escape')
    await expect(dialog).toBeHidden()
  })

  await test.step('add RTSP camera: password is masked in the table', async () => {
    await page.getByRole('button', { name: 'Add camera' }).first().click()
    const dialog = page.getByRole('dialog', { name: 'Add camera' })
    await dialog.getByLabel('Name', { exact: true }).fill('Dining IP cam')
    await dialog.getByLabel('Area').selectOption('dining')
    await dialog.getByRole('radio', { name: 'Stream URL' }).click()
    await dialog.getByLabel('Stream URL').fill('rtsp://admin:secret123@192.168.1.10:554/stream1')
    await dialog.getByRole('button', { name: 'Add camera' }).click()
    await expect(dialog).toBeHidden()

    const row = page.getByRole('row', { name: /Dining IP cam/ })
    await expect(row).toContainText('rtsp://admin:****@192.168.1.10:554/stream1')
    await expect(row).not.toContainText('secret123')
    await expect(row).toContainText('Dining')
  })

  await test.step('edit camera location', async () => {
    await page.getByRole('button', { name: 'Edit Laptop Webcam' }).click()
    const dialog = page.getByRole('dialog', { name: 'Edit Laptop Webcam' })
    await expect(dialog.getByLabel('Name', { exact: true })).toHaveValue('Laptop Webcam')
    await dialog.getByLabel('Location').fill('Kitchen counter')
    await dialog.getByRole('button', { name: 'Save changes' }).click()
    await expect(dialog).toBeHidden()
    await expect(page.getByRole('row', { name: /Laptop Webcam/ })).toContainText('Kitchen counter')
  })

  await test.step('toggle enabled off and on', async () => {
    await page.getByRole('switch', { name: 'Disable Laptop Webcam' }).click()
    await expect(page.getByRole('switch', { name: 'Enable Laptop Webcam' })).toHaveAttribute('aria-checked', 'false')
    await expect(page.getByText('2 cameras · 1 enabled')).toBeVisible()
    await page.screenshot({ path: `${SCREENSHOTS}/05-cameras-table.png`, animations: 'disabled' })

    await page.getByRole('switch', { name: 'Enable Laptop Webcam' }).click()
    await expect(page.getByRole('switch', { name: 'Disable Laptop Webcam' })).toHaveAttribute('aria-checked', 'true')
    await expect(page.getByText('2 cameras · 2 enabled')).toBeVisible()
  })

  await test.step('changes survive a page reload', async () => {
    await page.reload()
    await expect(page.getByRole('row', { name: /Laptop Webcam/ })).toContainText('Kitchen counter')
    await expect(page.getByRole('row', { name: /Dining IP cam/ })).toBeVisible()
  })

  await test.step('delete: cancel keeps it, confirm removes it', async () => {
    await page.getByRole('button', { name: 'Delete Dining IP cam' }).click()
    let dialog = page.getByRole('dialog', { name: 'Delete camera' })
    await expect(dialog).toContainText('Dining IP cam')
    await dialog.getByRole('button', { name: 'Cancel' }).click()
    await expect(page.getByRole('row', { name: /Dining IP cam/ })).toBeVisible()

    for (const name of ['Dining IP cam', 'Laptop Webcam']) {
      await page.getByRole('button', { name: `Delete ${name}` }).click()
      dialog = page.getByRole('dialog', { name: 'Delete camera' })
      await dialog.getByRole('button', { name: 'Delete', exact: true }).click()
      await expect(dialog).toBeHidden()
      await expect(page.getByRole('row', { name: new RegExp(name) })).toHaveCount(0)
    }
    await expect(page.getByText('No cameras yet')).toBeVisible()
  })
})
