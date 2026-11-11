import { expect, test, type Locator, type Page } from '@playwright/test'
import { apiToken, createCamera, login, resetData, SCREENSHOTS } from './helpers'
import { TEST_VIDEO } from './paths'

test.setTimeout(90_000)

let cameraId: number
test.beforeEach(async ({ request }) => {
  await resetData(request)
  cameraId = await createCamera(request, { name: 'Prep cam', source_url: TEST_VIDEO })
})

async function openZones(page: Page) {
  await login(page)
  await page.getByRole('navigation').getByRole('link', { name: 'Zones' }).click()
  await expect(page.getByRole('heading', { level: 1, name: 'Zones' })).toBeVisible()
  const canvas = page.getByTestId('zone-canvas')
  // Camera picture loaded as the background.
  await expect.poll(() => canvas.getByRole('img', { name: 'Current view of Prep cam' }).evaluate((el: HTMLImageElement) => el.naturalWidth), { timeout: 15_000 }).toBe(640)
  return canvas
}

/** Click at fractions (0-1) of the canvas. */
async function clickAt(page: Page, canvas: Locator, x: number, y: number) {
  const b = (await canvas.boundingBox())!
  await page.mouse.click(b.x + x * b.width, b.y + y * b.height)
}

async function drawZone(page: Page, canvas: Locator, points: [number, number][], name: string, type: string) {
  await page.getByRole('button', { name: 'Draw new zone' }).click()
  for (const [x, y] of points) await clickAt(page, canvas, x, y)
  await clickAt(page, canvas, points[0][0], points[0][1]) // clicking the first point closes the shape
  const form = page.getByRole('form', { name: 'New zone' })
  await form.getByLabel('Zone name').fill(name)
  await form.getByLabel('Zone type').selectOption({ label: type })
  await form.getByRole('button', { name: 'Save zone' }).click()
  return form
}

async function apiZones(page: Page) {
  const headers = await apiToken(page.request)
  return (await (await page.request.get(`/api/cameras/${cameraId}/zones`, { headers })).json()) as { name: string; zone_type: string; polygon: number[][] }[]
}

test('draw, rename, reshape and delete a zone', async ({ page }) => {
  const canvas = await openZones(page)
  await expect(page.getByText('No zones yet.')).toBeVisible()

  await test.step('Escape cancels a shape in progress', async () => {
    await page.getByRole('button', { name: 'Draw new zone' }).click()
    await clickAt(page, canvas, 0.2, 0.2)
    await page.keyboard.press('Escape')
    await expect(page.getByRole('button', { name: 'Draw new zone' })).toBeVisible()
  })

  await test.step('draw a sink zone by clicking corners', async () => {
    const form = await drawZone(page, canvas, [[0.1, 0.55], [0.45, 0.55], [0.45, 0.95], [0.1, 0.95]], 'Hand-wash sink', 'Hand-wash sink')
    await expect(form).toBeHidden()
    await expect(page.getByTestId('zone-shape-Hand-wash sink')).toBeVisible()
    await expect(page.getByRole('list', { name: 'Zones' })).toContainText('Hand-wash sink')
    const [z] = await apiZones(page)
    expect(z.zone_type).toBe('sink')
    expect(z.polygon).toHaveLength(4)
    expect(z.polygon[0][0]).toBeCloseTo(0.1, 1)
    expect(z.polygon[2][1]).toBeCloseTo(0.95, 1)
  })

  await test.step('errors are shown: duplicate name, shape too small', async () => {
    const form = await drawZone(page, canvas, [[0.6, 0.1], [0.9, 0.1], [0.9, 0.4]], 'hand-wash SINK', 'Other')
    await expect(form.getByRole('alert')).toContainText('already has a zone named')
    await form.getByLabel('Zone name').fill('Raw prep counter')
    await form.getByLabel('Zone type').selectOption({ label: 'Raw prep' })
    await form.getByRole('button', { name: 'Save zone' }).click()
    await expect(form).toBeHidden()

    const tiny = await drawZone(page, canvas, [[0.5, 0.5], [0.51, 0.5], [0.51, 0.51]], 'Speck', 'Other')
    await expect(tiny.getByRole('alert')).toContainText('too small')
    await tiny.getByRole('button', { name: 'Discard' }).click()
    await page.screenshot({ path: `${SCREENSHOTS}/19-zones.png` })
  })

  await test.step('rename and drag a corner', async () => {
    await page.getByRole('list', { name: 'Zones' }).getByRole('button', { name: /Hand-wash sink/ }).click()
    const form = page.getByRole('form', { name: 'Edit zone' })
    await expect(form.getByLabel('Zone name')).toHaveValue('Hand-wash sink')
    await expect(form.getByRole('button', { name: 'Save changes' })).toBeDisabled()

    await form.getByLabel('Zone name').fill('Main sink')
    const handle = page.getByRole('button', { name: 'Corner 3' })
    const hb = (await handle.boundingBox())!
    const cb = (await canvas.boundingBox())!
    await page.mouse.move(hb.x + hb.width / 2, hb.y + hb.height / 2)
    await page.mouse.down()
    await page.mouse.move(cb.x + 0.3 * cb.width, cb.y + 0.8 * cb.height, { steps: 5 })
    await page.mouse.up()
    await form.getByRole('button', { name: 'Save changes' }).click()
    await expect(form.getByRole('button', { name: 'Save changes' })).toBeDisabled()

    const z = (await apiZones(page)).find((x) => x.name === 'Main sink')!
    expect(z.polygon[2][0]).toBeCloseTo(0.3, 1)
    expect(z.polygon[2][1]).toBeCloseTo(0.8, 1)
  })

  await test.step('delete with confirmation', async () => {
    const form = page.getByRole('form', { name: 'Edit zone' })
    await form.getByRole('button', { name: 'Delete zone' }).click()
    await form.getByRole('button', { name: 'Delete', exact: true }).click()
    await expect(page.getByTestId('zone-shape-Main sink')).toHaveCount(0)
    expect((await apiZones(page)).map((z) => z.name)).toEqual(['Raw prep counter'])
  })
})

test('zones appear on Live View and tag detected events', async ({ page }) => {
  const headers = await apiToken(page.request)
  // The fake detector's person stands at the bottom-centre of the frame.
  await page.request.post(`/api/cameras/${cameraId}/zones`, {
    headers,
    data: { name: 'Prep counter', zone_type: 'raw_prep', polygon: [[0, 0.5], [1, 0.5], [1, 1], [0, 1]] },
  })
  await page.request.put(`/api/detection/cameras/${cameraId}/config`, {
    headers,
    data: { enabled: true, checks: ['no_mask'], min_duration_s: 1, interval_s: 0.3 },
  })

  await login(page)
  await page.getByRole('navigation').getByRole('link', { name: 'Live View' }).click()
  const tile = page.getByRole('figure').filter({ hasText: 'Prep cam' })
  await page.getByLabel('Show zones').check()
  await expect(tile.getByTestId('live-zone')).toHaveCount(1, { timeout: 15_000 })
  await expect(tile.getByRole('img', { name: 'Zones' })).toContainText('Prep counter')
  await page.screenshot({ path: `${SCREENSHOTS}/20-live-zones.png` })

  await page.getByRole('navigation').getByRole('link', { name: /Events & Alerts/ }).click()
  const row = page.getByRole('row', { name: /No mask/ })
  await expect(row).toContainText('Prep counter', { timeout: 15_000 })

  await page.request.put(`/api/detection/cameras/${cameraId}/config`, { headers, data: { enabled: false } })
})
