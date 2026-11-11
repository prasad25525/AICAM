import { expect, test, type Page } from '@playwright/test'
import { createCamera, createTestEvent, deleteAllCameras, deleteAllEvents, login, SCREENSHOTS } from './helpers'
import { TEST_VIDEO } from './paths'

test.setTimeout(60_000)

let cameraId: number
test.beforeEach(async ({ request }) => {
  await deleteAllEvents(request)
  await deleteAllCameras(request)
  cameraId = await createCamera(request, { name: 'Test pattern', source_url: TEST_VIDEO })
})

async function openEvents(page: Page) {
  await login(page)
  await page.getByRole('navigation').getByRole('link', { name: /Events & Alerts/ }).click()
  await expect(page).toHaveURL(/\/events$/)
}

const tab = (page: Page, name: string) => page.getByRole('tab', { name: new RegExp(`^${name}`) })

test('create a test event from the UI; badges update', async ({ page }) => {
  await openEvents(page)
  await expect(page.getByText('No events')).toBeVisible()
  await expect(page.getByRole('link', { name: 'Notifications: no open events' })).toBeVisible()

  await page.getByRole('button', { name: 'Create test event' }).first().click()
  const dialog = page.getByRole('dialog', { name: 'Create test event' })
  await dialog.getByLabel('Camera').selectOption({ label: 'Test pattern' })
  await dialog.getByLabel('Violation').selectOption({ label: 'No mask · Warning' })
  await dialog.getByRole('button', { name: 'Create' }).click()
  await expect(dialog).toBeHidden({ timeout: 15_000 })

  const row = page.getByRole('row', { name: /No mask/ })
  await expect(row).toContainText('Test pattern')
  await expect(row).toContainText('Test')
  await expect(row).toContainText('Warning')
  await expect(row).toContainText('Open')
  // Thumbnail loaded through the media token.
  await expect.poll(() => row.locator('img').evaluate((el: HTMLImageElement) => el.naturalWidth)).toBeGreaterThan(0)

  await expect(page.getByLabel('1 open events', { exact: true })).toBeVisible() // sidebar badge
  await expect(page.getByRole('link', { name: 'Notifications: 1 open events' })).toBeVisible()
})

test('review workflow: acknowledge, detail with note, resolve, reopen, filter, bulk', async ({ page, request }) => {
  for (const t of ['no_gloves', 'no_mask', 'bin_open']) await createTestEvent(request, cameraId, t)
  await openEvents(page)

  await expect(tab(page, 'Open')).toContainText('3')
  // Every thumbnail actually loads (not just the first ones).
  const thumbs = page.locator('tbody img')
  await expect(thumbs).toHaveCount(3)
  await expect
    .poll(() => thumbs.evaluateAll((imgs: HTMLImageElement[]) => imgs.filter((i) => i.complete && i.naturalWidth > 0).length), { timeout: 10_000 })
    .toBe(3)
  await page.screenshot({ path: `${SCREENSHOTS}/11-events.png` })

  await test.step('quick acknowledge moves it to the Acknowledged tab', async () => {
    const row = page.getByRole('row', { name: /Bin lid open/ })
    await row.getByRole('button', { name: /^Acknowledge event/ }).click()
    await expect(page.getByRole('row', { name: /Bin lid open/ })).toHaveCount(0)
    await expect(tab(page, 'Open')).toContainText('2')
    await expect(tab(page, 'Acknowledged')).toContainText('1')
  })

  await test.step('detail view: image, note, resolve', async () => {
    await page.getByRole('row', { name: /No gloves/ }).click()
    const dialog = page.getByRole('dialog', { name: 'No gloves' })
    await expect(dialog).toContainText('Handling food without gloves')
    await expect(dialog).toContainText('Critical')
    await expect(dialog).toContainText('Test event')
    // The violation is shown visually: the rule, and the missing item struck through.
    const violation = dialog.getByRole('region', { name: 'Violation' })
    await expect(violation).toContainText('Rule broken')
    await expect(violation).toContainText('Gloves must be worn when handling food')
    await expect(violation).toContainText('Missing: Gloves')
    const img = dialog.getByRole('img', { name: 'Snapshot of No gloves' })
    await expect.poll(() => img.evaluate((el: HTMLImageElement) => el.naturalWidth)).toBe(640)

    await dialog.getByLabel('Note').fill('Reminded chef about gloves')
    await dialog.getByRole('button', { name: 'Save note' }).click()
    await expect(dialog.getByRole('button', { name: 'Save note' })).toHaveCount(0)
    await page.screenshot({ path: `${SCREENSHOTS}/12-event-detail.png` })

    await dialog.getByRole('button', { name: 'Resolve' }).click()
    await expect(dialog).toContainText('Resolved')
    await expect(dialog.getByRole('button', { name: 'Reopen' })).toBeVisible()
    await dialog.getByRole('button', { name: 'Close' }).last().click()
    await expect(tab(page, 'Resolved')).toContainText('1')
  })

  await test.step('resolved tab keeps the note; reopen', async () => {
    await tab(page, 'Resolved').click()
    await page.getByRole('row', { name: /No gloves/ }).click()
    const dialog = page.getByRole('dialog', { name: 'No gloves' })
    await expect(dialog.getByLabel('Note')).toHaveValue('Reminded chef about gloves')
    await dialog.getByRole('button', { name: 'Reopen' }).click()
    await expect(dialog.getByRole('button', { name: 'Acknowledge' })).toBeVisible()
    await page.keyboard.press('Escape')
    await expect(tab(page, 'Open')).toContainText('2')
  })

  await test.step('filter by severity', async () => {
    await tab(page, 'All').click()
    await page.getByLabel('Severity').selectOption('critical')
    await expect(page.getByRole('row', { name: /No gloves/ })).toBeVisible()
    await expect(page.getByRole('row', { name: /No mask/ })).toHaveCount(0)
    await page.getByLabel('Severity').selectOption('')
    await expect(page.getByRole('row', { name: /No mask/ })).toBeVisible()
  })

  await test.step('bulk: mark all open as false alarm', async () => {
    await tab(page, 'Open').click()
    await page.getByLabel('Select all on this page').check()
    await expect(page.getByText('2 selected')).toBeVisible()
    await page.getByRole('button', { name: 'False alarm' }).click()
    await expect(page.getByText('No events')).toBeVisible()
    await expect(tab(page, 'False alarm')).toContainText('2')
    await expect(page.getByRole('link', { name: 'Notifications: no open events' })).toBeVisible()
  })
})

test('delete: from a row, from the detail view, and in bulk', async ({ page, request }) => {
  for (const t of ['no_gloves', 'no_mask', 'bin_open', 'no_apron']) await createTestEvent(request, cameraId, t)
  await openEvents(page)
  await expect(tab(page, 'Open')).toContainText('4')

  await test.step('row trash icon, cancel keeps it, confirm deletes it', async () => {
    const row = page.getByRole('row', { name: /Bin lid open/ })
    await row.getByRole('button', { name: /^Delete event/ }).click()
    let dialog = page.getByRole('dialog', { name: 'Delete event' })
    await expect(dialog).toContainText('this Bin lid open event')
    await dialog.getByRole('button', { name: 'Cancel' }).click()
    await expect(row).toBeVisible()

    await row.getByRole('button', { name: /^Delete event/ }).click()
    dialog = page.getByRole('dialog', { name: 'Delete event' })
    await dialog.getByRole('button', { name: 'Delete' }).click()
    await expect(dialog).toBeHidden()
    await expect(page.getByRole('row', { name: /Bin lid open/ })).toHaveCount(0)
    await expect(tab(page, 'Open')).toContainText('3')
  })

  await test.step('detail view asks to confirm, then deletes', async () => {
    await page.getByRole('row', { name: /No apron/ }).click()
    const dialog = page.getByRole('dialog', { name: 'No apron' })
    await dialog.getByRole('button', { name: 'Delete' }).click()
    await expect(dialog).toContainText('Delete this event and its snapshot permanently?')
    await page.screenshot({ path: `${SCREENSHOTS}/17-delete-confirm.png` })
    await dialog.getByRole('button', { name: 'Delete' }).click()
    await expect(dialog).toBeHidden()
    await expect(page.getByRole('row', { name: /No apron/ })).toHaveCount(0)
    await expect(tab(page, 'Open')).toContainText('2')
  })

  await test.step('bulk delete selected', async () => {
    await page.getByLabel('Select all on this page').check()
    await page.getByRole('button', { name: 'Delete', exact: true }).click()
    const dialog = page.getByRole('dialog', { name: 'Delete 2 events' })
    await expect(dialog).toContainText('2 events')
    await dialog.getByRole('button', { name: 'Delete' }).click()
    await expect(page.getByText('No events')).toBeVisible()
    await expect(tab(page, 'All')).toContainText('0')
    await expect(page.getByRole('link', { name: 'Notifications: no open events' })).toBeVisible()
  })
})

test('pagination', async ({ page, request }) => {
  for (let i = 0; i < 27; i++) await createTestEvent(request, cameraId, 'no_apron')
  await openEvents(page)
  await expect(page.getByText('1–25 of 27')).toBeVisible()
  await expect(page.getByRole('row', { name: /No apron/ })).toHaveCount(25)
  await page.getByRole('button', { name: 'Next page' }).click()
  await expect(page.getByText('26–27 of 27')).toBeVisible()
  await expect(page.getByRole('row', { name: /No apron/ })).toHaveCount(2)
  await expect(page.getByRole('button', { name: 'Next page' })).toBeDisabled()
})
