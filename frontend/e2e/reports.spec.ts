import { expect, test } from '@playwright/test'
import fs from 'node:fs'
import { apiToken, createCamera, createTestEvent, login, resetData, SCREENSHOTS } from './helpers'
import { TEST_VIDEO } from './paths'

test.setTimeout(60_000)

test.beforeEach(async ({ request }) => {
  await resetData(request)
})

test('reports: totals, breakdowns, ranges, table view and CSV export', async ({ page, request }) => {
  const cameraId = await createCamera(request, { name: 'Prep cam', source_url: TEST_VIDEO })
  await createTestEvent(request, cameraId, 'no_gloves') // critical
  await createTestEvent(request, cameraId, 'no_mask') // warning
  const falseId = await createTestEvent(request, cameraId, 'bin_open')
  const headers = await apiToken(request)
  await request.patch(`/api/events/${falseId}`, { headers, data: { status: 'false_alarm' } })

  await login(page)
  await page.getByRole('navigation').getByRole('link', { name: 'Reports' }).click()
  await expect(page.getByRole('heading', { level: 1, name: 'Reports' })).toBeVisible()

  await test.step('totals and breakdowns for the last 7 days', async () => {
    await expect(page.getByRole('radio', { name: 'Last 7 days' })).toHaveAttribute('aria-checked', 'true')
    await expect(page.getByText(/· 7 days$/)).toBeVisible()
    await expect(page.getByLabel('Violations', { exact: true })).toContainText('2')
    await expect(page.getByLabel('False alarm rate')).toContainText('33%')
    // Today: 100 - 5 - 2 = 93; the other six days 100 -> average 99.
    await expect(page.getByLabel('Average hygiene score')).toContainText('99/100')
    await expect(page.getByLabel('Average hygiene score')).toContainText('Worst day')
    await expect(page.getByRole('list', { name: 'Violations by type' }).getByRole('listitem')).toHaveCount(2)
    await expect(page.getByRole('list', { name: 'Violations by camera' })).toContainText('Prep cam')
    await expect(page.getByRole('list', { name: 'Violations by zone' })).toContainText('No zone')
    await page.screenshot({ path: `${SCREENSHOTS}/23-reports.png`, fullPage: true })
  })

  await test.step('daily table view', async () => {
    await page.getByText('Daily figures as a table').click()
    const table = page.getByRole('table', { name: 'Daily figures' })
    await expect(table.getByRole('row')).toHaveCount(8) // header + 7 days
    await expect(table.getByRole('row').last()).toContainText('93') // today's score
  })

  await test.step('other ranges', async () => {
    await page.getByRole('radio', { name: 'Last 30 days' }).click()
    await expect(page.getByText(/· 30 days$/)).toBeVisible()
    await page.getByRole('radio', { name: 'Custom' }).click()
    const today = new Date()
    const iso = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
    const twoDaysAgo = new Date(today.getTime() - 2 * 86400_000)
    await page.getByLabel('From date').fill(iso(twoDaysAgo))
    await page.getByLabel('To date').fill(iso(today))
    await expect(page.getByText(/· 3 days$/)).toBeVisible()
  })

  await test.step('CSV export downloads every event in the range', async () => {
    const [download] = await Promise.all([page.waitForEvent('download'), page.getByRole('button', { name: 'Export CSV' }).click()])
    expect(download.suggestedFilename()).toMatch(/^vigilsiddhi-events-\d{4}-\d{2}-\d{2}-to-\d{4}-\d{2}-\d{2}\.csv$/)
    const text = fs.readFileSync(await download.path(), 'utf-8').replace(/^﻿/, '')
    const lines = text.trim().split(/\r?\n/)
    expect(lines[0]).toBe('id,occurred_at,camera,zone,type,severity,status,confidence,message,note,acknowledged_at,resolved_at,test_event')
    expect(lines).toHaveLength(4) // header + 3 events (false alarm included, marked by status)
    expect(text).toContain('No gloves,critical,open')
    expect(text).toContain('false_alarm')
  })
})
