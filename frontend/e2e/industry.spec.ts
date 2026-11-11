import { expect, test } from '@playwright/test'
import { apiToken, createCamera, resetData, SCREENSHOTS } from './helpers'
import { TEST_VIDEO } from './paths'

test.setTimeout(90_000)
test.beforeEach(({ request }) => resetData(request))

test('cement: person in a restricted area — live marker, alert, evidence', async ({ page, request }) => {
  const headers = await apiToken(request)
  await request.put('/api/industry', { headers, data: { industry: 'cement' } })
  const cameraId = await createCamera(request, { name: 'Crusher cam', source_url: TEST_VIDEO })
  // The e2e test engine sees one person standing at the bottom centre of the picture.
  await request.post(`/api/cameras/${cameraId}/zones`, {
    headers,
    data: { name: 'Crusher danger area', zone_type: 'restricted', polygon: [[0.3, 0.6], [0.7, 0.6], [0.7, 1], [0.3, 1]] },
  })
  await page.goto('/login')
  await expect(page.getByRole('tab', { name: 'Cement plant' })).toHaveAttribute('aria-selected', 'true') // the active one
  await page.getByRole('button', { name: 'Sign in' }).click()
  await page.getByRole('navigation').getByRole('link', { name: 'Live View' }).click()
  await expect(page.getByRole('status', { name: 'Live alerts connected' })).toBeVisible({ timeout: 10_000 })

  // Detection on only now, so the alert happens while this page is open and pops up.
  await request.put(`/api/detection/cameras/${cameraId}/config`, {
    headers,
    data: { enabled: true, checks: ['restricted_area'], min_duration_s: 1, interval_s: 0.5 },
  })

  const marker = page.getByRole('img', { name: 'Detections' }).getByTestId('detection-intrusion')
  await expect(marker).toContainText(/IN DANGER ZONE \d+s/, { timeout: 20_000 })
  await expect(page.getByRole('alert', { name: 'New alert: Restricted area entry' })).toBeVisible({ timeout: 15_000 })
  await page.screenshot({ path: `${SCREENSHOTS}/29-cement-restricted-live.png` })

  await page.getByRole('navigation').getByRole('link', { name: /Events & Alerts/ }).click()
  await page.getByRole('row', { name: /Restricted area entry/ }).click()
  const violation = page.getByRole('dialog', { name: 'Restricted area entry' }).getByRole('region', { name: 'Violation' })
  await expect(violation).toContainText('No entry into restricted or danger areas')
  await expect(violation).toContainText(/Inside Crusher danger area for \d+s when alerted/)
  await page.screenshot({ path: `${SCREENSHOTS}/30-cement-restricted-event.png` })

  await request.put(`/api/detection/cameras/${cameraId}/config`, { headers, data: { enabled: false } })
})

test('cement: conveyor spillage — floor badge, alert, evidence', async ({ page, request }) => {
  const headers = await apiToken(request)
  await request.put('/api/industry', { headers, data: { industry: 'cement' } })
  const cameraId = await createCamera(request, { name: 'Belt cam', source_url: TEST_VIDEO })
  await request.post(`/api/cameras/${cameraId}/zones`, {
    headers,
    data: { name: 'Floor under belt 1', zone_type: 'conveyor_floor', polygon: [[0.3, 0.68], [0.95, 0.68], [0.95, 1], [0.3, 1]] },
  })

  await page.goto('/login')
  await page.getByRole('button', { name: 'Sign in' }).click()
  await page.getByRole('navigation').getByRole('link', { name: 'Live View' }).click()
  await expect(page.getByRole('status', { name: 'Live alerts connected' })).toBeVisible({ timeout: 10_000 })
  await request.put(`/api/detection/cameras/${cameraId}/config`, {
    headers,
    data: { enabled: true, checks: ['conveyor_spillage'], min_duration_s: 1, interval_s: 0.5 },
  })

  const badge = page.getByRole('img', { name: 'Detections' }).getByTestId('detection-zone-state')
  await expect(badge).toHaveAttribute('data-state', 'problem', { timeout: 20_000 })
  await expect(badge).toContainText(/CONVEYOR SPILLAGE \d:\d\d/)
  await expect(page.getByRole('status', { name: 'New alert: Conveyor spillage' })).toBeVisible({ timeout: 15_000 })
  await page.screenshot({ path: `${SCREENSHOTS}/31-cement-spillage-live.png` })

  await page.getByRole('navigation').getByRole('link', { name: /Events & Alerts/ }).click()
  await page.getByRole('row', { name: /Conveyor spillage/ }).click()
  const violation = page.getByRole('dialog', { name: 'Conveyor spillage' }).getByRole('region', { name: 'Violation' })
  await expect(violation).toContainText('Conveyor belts must run without spilling material')
  await expect(violation).toContainText(/Visible on Floor under belt 1 for \d+s when alerted/)

  await request.put(`/api/detection/cameras/${cameraId}/config`, { headers, data: { enabled: false } })
})

test('cement: bag counting — counting line on Live View, tile on the Dashboard', async ({ page, request }) => {
  const headers = await apiToken(request)
  await request.put('/api/industry', { headers, data: { industry: 'cement' } })
  const cameraId = await createCamera(request, { name: 'Packer 1', source_url: TEST_VIDEO })
  await request.post(`/api/cameras/${cameraId}/zones`, {
    headers,
    data: { name: 'Loader belt', zone_type: 'packing_line', polygon: [[0, 0.3], [1, 0.3], [1, 0.6], [0, 0.6]] },
  })
  await request.put(`/api/detection/cameras/${cameraId}/config`, { headers, data: { enabled: true, checks: ['bag_count'], interval_s: 1 } })

  await page.goto('/login')
  await page.getByRole('button', { name: 'Sign in' }).click()
  // The test video isn't a conveyor, so the count itself isn't checked here (the backend tests do that).
  await expect(page.getByRole('group', { name: 'Bags counted today' })).toContainText(/\d/)
  await page.getByRole('navigation').getByRole('link', { name: 'Live View' }).click()
  const counter = page.getByRole('img', { name: 'Detections' }).getByTestId('detection-counter')
  await expect(counter).toContainText(/BAGS \d+ · \d+\/min/, { timeout: 20_000 })
  await page.screenshot({ path: `${SCREENSHOTS}/32-cement-bag-counter.png` })

  await request.put(`/api/detection/cameras/${cameraId}/config`, { headers, data: { enabled: false } })
})

test('pick an industry at login; everything follows it; switch from the top bar', async ({ page, browser, request }) => {
  await createCamera(request, { name: 'Kitchen cam', source_url: TEST_VIDEO }) // restaurant is active after reset

  await test.step('login page: industry tabs, restaurant selected (the active one)', async () => {
    await page.goto('/login')
    const tabs = page.getByRole('tablist', { name: 'Industry' })
    await expect(tabs.getByRole('tab')).toHaveText(['Restaurant', 'Cement plant'])
    await expect(tabs.getByRole('tab', { name: 'Restaurant' })).toHaveAttribute('aria-selected', 'true')
    await tabs.getByRole('tab', { name: 'Cement plant' }).click()
    await expect(tabs.getByRole('tab', { name: 'Cement plant' })).toHaveAttribute('aria-selected', 'true')
    await expect(tabs.getByRole('tab', { name: 'Restaurant' })).toHaveAttribute('aria-selected', 'false')
    await expect(page.getByText('Worker safety & plant monitoring')).toBeVisible()
    await page.waitForTimeout(300) // let the tab's colour transition finish before the screenshot
    await page.screenshot({ path: `${SCREENSHOTS}/27-login-industry.png` })
    await page.getByRole('button', { name: 'Sign in' }).click()
    await expect(page).toHaveURL(/\/dashboard$/)
  })

  await test.step('cement: own score name, no restaurant cameras', async () => {
    await expect(page.getByRole('button', { name: 'Industry: Cement plant. Switch industry' })).toBeVisible()
    await expect(page.getByText('Safety score')).toBeVisible()
    await page.getByRole('navigation').getByRole('link', { name: 'Cameras' }).click()
    await expect(page.getByText('No cameras yet')).toBeVisible() // the kitchen camera belongs to the restaurant
  })

  await test.step('cement camera: its areas, checks, coming-soon list and zone types', async () => {
    await page.getByRole('button', { name: 'Add camera' }).first().click()
    const form = page.getByRole('dialog', { name: 'Add camera' })
    await expect(form.getByLabel('Area').locator('option')).toHaveText(['Production', 'Packing & dispatch', 'Yard & gate', 'Other'])
    await page.keyboard.press('Escape')

    await createCamera(request, { name: 'Kiln cam', source_url: TEST_VIDEO }) // cement is active now
    await page.reload()
    await expect(page.getByRole('row', { name: /Kiln cam/ })).toContainText('Production')
    await page.getByRole('button', { name: 'Detection settings for Kiln cam' }).click()
    const dialog = page.getByRole('dialog', { name: 'Detection · Kiln cam' })
    await expect(dialog.getByRole('checkbox')).toHaveCount(6) // the on/off switch + helmet + vest + restricted area + spillage + bag counting
    await expect(dialog.getByText('Restricted area entry').locator('..')).toContainText('Needs a Restricted / danger area zone — none drawn yet')
    await expect(dialog.getByLabel('Safety helmet')).toBeChecked()
    await expect(dialog.getByLabel('Safety vest')).toBeChecked()
    await expect(dialog.getByText('Hair cap / hairnet')).toHaveCount(0)
    await expect(dialog.getByRole('region', { name: 'Coming soon' })).toContainText('Damaged cement bag detection')
    await page.screenshot({ path: `${SCREENSHOTS}/28-cement-detection-settings.png` })
    await page.keyboard.press('Escape')
  })

  await test.step('switch back from the top bar; another open browser is told', async () => {
    const other = await browser.newPage({ storageState: await page.context().storageState() })
    await other.goto('/dashboard')
    await expect(other.getByText('Safety score')).toBeVisible()
    await expect(other.getByRole('status', { name: 'Live alerts connected' })).toBeVisible({ timeout: 10_000 })

    await page.getByRole('button', { name: 'Industry: Cement plant. Switch industry' }).click()
    await page.getByRole('menuitemradio', { name: /Restaurant/ }).click()
    await expect(page).toHaveURL(/\/dashboard$/)
    await expect(page.getByText('Hygiene score')).toBeVisible()
    await page.getByRole('navigation').getByRole('link', { name: 'Cameras' }).click()
    await expect(page.getByRole('row', { name: /Kitchen cam/ })).toBeVisible()
    await expect(page.getByRole('row', { name: /Kiln cam/ })).toHaveCount(0)

    await expect(other.getByRole('status').filter({ hasText: 'Industry changed to Restaurant' })).toBeVisible({ timeout: 5_000 })
    await expect(other.getByText('Hygiene score')).toBeVisible()
    await other.close()
  })
})
