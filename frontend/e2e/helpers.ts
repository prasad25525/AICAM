import { expect, type APIRequestContext, type Page } from '@playwright/test'

export const SCREENSHOTS = 'e2e/screenshots'

/** Log in with the prefilled dev credentials and land on the dashboard. */
export async function login(page: Page) {
  await page.goto('/login')
  await page.getByRole('button', { name: 'Sign in' }).click()
  await expect(page).toHaveURL(/\/dashboard$/)
}

export async function apiToken(request: APIRequestContext) {
  const res = await request.post('/api/auth/login', { data: { username: 'admin', password: 'admin123' } })
  return { Authorization: `Bearer ${(await res.json()).access_token}` }
}

/** Remove every camera through the API so each test starts from an empty list. */
export async function deleteAllCameras(request: APIRequestContext) {
  const headers = await apiToken(request)
  const cameras: { id: number }[] = await (await request.get('/api/cameras', { headers })).json()
  for (const c of cameras) await request.delete(`/api/cameras/${c.id}`, { headers })
}

/** Remove every event through the API. */
export async function deleteAllEvents(request: APIRequestContext) {
  const headers = await apiToken(request)
  for (;;) {
    const { items }: { items: { id: number }[] } = await (await request.get('/api/events?limit=200', { headers })).json()
    if (!items.length) return
    for (const e of items) await request.delete(`/api/events/${e.id}`, { headers })
  }
}

/** Start a test from a clean slate: restaurant industry, no events, no cameras, default settings (everything on). */
export async function resetData(request: APIRequestContext) {
  const headers = await apiToken(request)
  for (const industry of ['cement', 'restaurant']) {
    // Lists only show the active industry, so clear each one (ending on restaurant, the default).
    await request.put('/api/industry', { headers, data: { industry } })
    await deleteAllEvents(request)
    await deleteAllCameras(request)
  }
  await request.put('/api/settings', {
    headers,
    data: { events_enabled: true, notifications_enabled: true, notify_severities: ['critical', 'warning', 'info'] },
  })
}

/** Create a test event through the API; returns its id. */
export async function createTestEvent(request: APIRequestContext, camera_id: number, event_type: string) {
  const headers = await apiToken(request)
  const res = await request.post('/api/events/test', { headers, data: { camera_id, event_type } })
  expect(res.status()).toBe(201)
  return (await res.json()).id as number
}

/** Create a camera directly through the API (faster than the form when the form isn't under test). */
export async function createCamera(request: APIRequestContext, data: { name: string; source_url: string; enabled?: boolean }) {
  const headers = await apiToken(request)
  const res = await request.post('/api/cameras', { headers, data })
  expect(res.status()).toBe(201)
  return (await res.json()).id as number
}
