// Screenshot a page of the running dev app (not a test). Usage:
//   node e2e/tools/live-screenshot.mjs <path> <out.png> [waitSeconds] [zones]
// Pass "zones" as the 4th argument to tick "Show zones" on Live View.
import { chromium } from '@playwright/test'

const [path = '/live', out = 'e2e/screenshots/live-demo.png', wait = '12', extra = ''] = process.argv.slice(2)
const base = 'http://127.0.0.1:5173'

const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } })
await page.goto(`${base}/login`)
await page.getByRole('button', { name: 'Sign in' }).click()
await page.waitForURL(/dashboard/)
await page.goto(`${base}${path}`)
if (extra === 'zones') await page.getByLabel('Show zones').check()
await page.waitForTimeout(Number(wait) * 1000)
await page.screenshot({ path: out, fullPage: true })
await browser.close()
console.log('saved', out)
