import { expect, test, type APIRequestContext, type Page } from '@playwright/test'
import { apiToken, createCamera, resetData, login, SCREENSHOTS } from './helpers'
import { TEST_VIDEO, UNREACHABLE_RTSP } from './paths'

test.setTimeout(60_000)
test.beforeEach(({ request }) => resetData(request))

async function openLive(page: Page) {
  await login(page)
  await page.getByRole('navigation').getByRole('link', { name: 'Live View' }).click()
  await expect(page).toHaveURL(/\/live$/)
}

async function openStreams(request: APIRequestContext) {
  const headers = await apiToken(request)
  return (await (await request.get('/api/streams', { headers })).json()) as { camera_id: number; viewers: number; state: string; fps: number }[]
}

/** Wait until the <img> has painted a real frame and keeps receiving new ones. */
async function expectPlaying(page: Page, name: string) {
  const img = page.getByRole('img', { name: `Live view of ${name}` })
  await expect.poll(() => img.evaluate((el: HTMLImageElement) => el.naturalWidth), { timeout: 15_000 }).toBe(640)
  return img
}

test('empty state when no cameras are enabled', async ({ page, request }) => {
  await createCamera(request, { name: 'Spare cam', source_url: TEST_VIDEO, enabled: false })
  await openLive(page)
  await expect(page.getByText('No cameras to show')).toBeVisible()
  await expect(page.getByRole('img', { name: /Live view/ })).toHaveCount(0)
  await page.getByRole('link', { name: 'Go to Cameras' }).click()
  await expect(page).toHaveURL(/\/cameras$/)
})

test('live tiles: streaming, offline camera, expand, and camera released on leave', async ({ page, request }) => {
  await createCamera(request, { name: 'Test pattern', source_url: TEST_VIDEO })
  await createCamera(request, { name: 'Dead IP cam', source_url: UNREACHABLE_RTSP })
  await createCamera(request, { name: 'Spare cam', source_url: TEST_VIDEO, enabled: false })
  await openLive(page)

  await test.step('working camera streams with LIVE badge and fps', async () => {
    await expectPlaying(page, 'Test pattern')
    const tile = page.getByRole('figure').filter({ hasText: 'Test pattern' })
    await expect(tile.getByText('LIVE')).toBeVisible({ timeout: 10_000 })
    await expect(tile.getByLabel('Frame rate')).toHaveText(/^\d+ fps · 640×360$/)
    // The backend reports the stream as live and actually producing frames. (Grid tiles poll single
    // frames, so the open-connection "viewers" count is usually 0 between polls.)
    await expect.poll(async () => (await openStreams(request)).some((s) => s.state === 'live' && s.fps > 5)).toBe(true)
  })

  await test.step('unreachable camera shows offline with the reason', async () => {
    const tile = page.getByRole('figure').filter({ hasText: 'Dead IP cam' })
    await expect(tile.getByRole('alert')).toContainText('Camera offline', { timeout: 20_000 })
    await expect(tile.getByRole('alert')).toContainText(/not reachable|Could not connect|Timed out/)
  })

  await test.step('disabled camera is not shown', async () => {
    await expect(page.getByRole('figure').filter({ hasText: 'Spare cam' })).toHaveCount(0)
    await expect(page.getByText('2 cameras · 1 streaming')).toBeVisible()
    await page.screenshot({ path: `${SCREENSHOTS}/09-live-view.png` })
  })

  await test.step('expand shows that one camera large; "Back to all" returns to the grid', async () => {
    await page.getByRole('figure').filter({ hasText: 'Test pattern' }).hover()
    await page.getByRole('button', { name: 'Expand Test pattern' }).click()
    await expect(page).toHaveURL(/\/live\?camera=\d+$/)
    await expect(page.getByLabel('Camera to show')).toHaveValue(/\d+/)
    await expect(page.getByRole('figure')).toHaveCount(1)
    const big = page.getByRole('img', { name: 'Live view of Test pattern' })
    await expect.poll(() => big.evaluate((el: HTMLImageElement) => el.naturalWidth), { timeout: 15_000 }).toBe(640)
    expect(await big.evaluate((el) => el.getBoundingClientRect().width)).toBeGreaterThan(800)
    await page.screenshot({ path: `${SCREENSHOTS}/10-live-expanded.png` })
    await page.getByRole('button', { name: 'Back to all' }).click()
    await expect(page.getByRole('figure')).toHaveCount(2)
  })

  await test.step('leaving the page releases the cameras', async () => {
    await page.getByRole('navigation').getByRole('link', { name: 'Dashboard' }).click()
    // Idle timeout is 2s in tests; the stream list should empty out once viewers are gone.
    await expect.poll(async () => (await openStreams(request)).length, { timeout: 20_000 }).toBe(0)
  })
})

test('dropdown: one camera at a time with fast detection (focus mode)', async ({ page, request }) => {
  const headers = await apiToken(request)
  const ids: number[] = []
  for (const name of ['Kitchen A', 'Kitchen B']) {
    const id = await createCamera(request, { name, source_url: TEST_VIDEO })
    ids.push(id)
    await request.put(`/api/detection/cameras/${id}/config`, { headers, data: { enabled: true, checks: ['no_mask'], interval_s: 1 } })
  }
  const status = async () => (await (await request.get('/api/detection/status', { headers })).json()) as {
    focus_camera_id: number | null
    cameras: { camera_id: number; paused: boolean }[]
  }

  await openLive(page)
  await expect(page.getByRole('figure')).toHaveCount(2)
  await expect(page.getByLabel('Camera to show')).toHaveValue('')

  await page.getByLabel('Camera to show').selectOption({ label: 'Kitchen B' })
  await expect(page.getByRole('figure')).toHaveCount(1)
  await expect(page.getByRole('status').filter({ hasText: 'Fast detection' })).toContainText('only Kitchen B is being analysed')
  await expect.poll(async () => (await status()).focus_camera_id).toBe(ids[1])
  await expect.poll(async () => (await status()).cameras.find((c) => c.camera_id === ids[0])?.paused).toBe(true)
  const tile = page.getByRole('figure')
  await expect(tile.getByLabel('Detection rate')).toContainText(/AI \d/, { timeout: 15_000 })
  await page.screenshot({ path: `${SCREENSHOTS}/24-live-focus.png` })

  // Unticking fast detection (or going back to all) ends focus mode right away.
  await page.getByLabel('Fast detection').uncheck()
  await expect.poll(async () => (await status()).focus_camera_id).toBeNull()
  await page.getByLabel('Fast detection').check()
  await expect.poll(async () => (await status()).focus_camera_id).toBe(ids[1])
  await page.getByLabel('Camera to show').selectOption({ label: 'All cameras (grid)' })
  await expect(page.getByRole('figure')).toHaveCount(2)
  await expect.poll(async () => (await status()).focus_camera_id).toBeNull()

  for (const id of ids) await request.put(`/api/detection/cameras/${id}/config`, { headers, data: { enabled: false } })
})

test('disabling a camera removes its tile', async ({ page, request }) => {
  await createCamera(request, { name: 'Test pattern', source_url: TEST_VIDEO })
  await openLive(page)
  await expectPlaying(page, 'Test pattern')

  await page.getByRole('navigation').getByRole('link', { name: 'Cameras' }).click()
  await page.getByRole('switch', { name: 'Disable Test pattern' }).click()
  await expect(page.getByRole('switch', { name: 'Enable Test pattern' })).toBeVisible()
  await page.getByRole('navigation').getByRole('link', { name: 'Live View' }).click()
  await expect(page.getByText('No cameras to show')).toBeVisible()
  await expect.poll(async () => (await openStreams(request)).length, { timeout: 10_000 }).toBe(0)
})
