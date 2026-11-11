import { expect, test } from '@playwright/test'
import { login, SCREENSHOTS } from './helpers'

test('login page has credentials prefilled with the password hidden', async ({ page }) => {
  await page.goto('/')
  await expect(page).toHaveURL(/\/login$/)
  // Branding: product name, tagline, and the Azkashine logo actually loaded.
  await expect(page).toHaveTitle('VigilSiddhi – A Vision AI Platform')
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('VigilSiddhi')
  await expect(page.getByText('A Vision AI Platform')).toBeVisible()
  const logo = page.getByRole('img', { name: 'Azkashine Software & Services Pvt. Ltd.' })
  await expect.poll(() => logo.evaluate((el: HTMLImageElement) => el.naturalWidth)).toBeGreaterThan(0)
  await expect(page.getByLabel('Username')).toHaveValue('admin')
  const password = page.getByLabel('Password', { exact: true })
  await expect(password).toHaveValue('admin123')
  await expect(password).toHaveAttribute('type', 'password')

  await page.getByRole('button', { name: 'Show password' }).click()
  await expect(password).toHaveAttribute('type', 'text')
  await page.getByRole('button', { name: 'Hide password' }).click()
  await expect(password).toHaveAttribute('type', 'password')

  await page.screenshot({ path: `${SCREENSHOTS}/01-login.png` })
})

test('wrong password shows an error and stays on login', async ({ page }) => {
  await page.goto('/login')
  await page.getByLabel('Password', { exact: true }).fill('wrong-password')
  await page.getByRole('button', { name: 'Sign in' }).click()
  await expect(page.getByRole('alert')).toHaveText('Invalid username or password')
  await expect(page).toHaveURL(/\/login$/)
})

test('protected pages redirect to login when logged out', async ({ page }) => {
  await page.goto('/cameras')
  await expect(page).toHaveURL(/\/login$/)
})

test('login, see dashboard, navigate, and logout', async ({ page }) => {
  await login(page)
  await expect(page.getByRole('heading', { level: 1, name: 'Dashboard' })).toBeVisible()
  await expect(page.getByText('admin', { exact: true })).toBeVisible() // username from /api/auth/me
  await expect(page.getByText('Violations by hour (today)')).toBeVisible()
  await page.screenshot({ path: `${SCREENSHOTS}/02-dashboard.png`, fullPage: true })

  await page.getByRole('navigation').getByRole('link', { name: 'Cameras' }).click()
  await expect(page).toHaveURL(/\/cameras$/)
  await expect(page.getByRole('heading', { level: 1, name: 'Cameras' })).toBeVisible()

  await page.getByRole('button', { name: 'Logout' }).click()
  await expect(page).toHaveURL(/\/login$/)

  // Token is gone: going back to a protected page lands on login again.
  await page.goto('/dashboard')
  await expect(page).toHaveURL(/\/login$/)
})
