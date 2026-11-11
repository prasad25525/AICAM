import { defineConfig, devices } from '@playwright/test'
import os from 'node:os'
import path from 'node:path'
import { BACKEND_DIR, PYTHON } from './e2e/paths'

// Tests run against their own backend (port 8001) and frontend (port 5174) with a
// throwaway SQLite database, so the dev servers and backend/data/aicam.db are never touched.
const BACKEND_PORT = 8001
const FRONTEND_PORT = 5174
const testDb = path.join(os.tmpdir(), `aicam-e2e-${Date.now()}.db`).replaceAll('\\', '/')

export default defineConfig({
  testDir: './e2e',
  globalSetup: './e2e/global-setup.ts',
  fullyParallel: false,
  workers: 1, // tests share one database
  retries: 0,
  reporter: [['list'], ['html', { open: 'never' }]],
  use: {
    baseURL: `http://127.0.0.1:${FRONTEND_PORT}`,
    viewport: { width: 1366, height: 800 },
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'], viewport: { width: 1366, height: 800 } } }],
  webServer: [
    {
      command: `"${PYTHON}" -m uvicorn app.main:app --host 127.0.0.1 --port ${BACKEND_PORT} --timeout-graceful-shutdown 2`,
      cwd: BACKEND_DIR,
      url: `http://127.0.0.1:${BACKEND_PORT}/api/health`,
      // Short idle timeout so tests can check that cameras are released after viewers leave.
      env: {
        AICAM_DATABASE_URL: `sqlite:///${testDb}`,
        AICAM_DATA_DIR: path.join(os.tmpdir(), `aicam-e2e-data-${Date.now()}`), // event snapshots
        AICAM_STREAM_IDLE_TIMEOUT_S: '2',
        // Scripted detector: one person, no mask, everything else worn. No GPU needed.
        AICAM_DETECTION_ENGINE: 'fake',
        AICAM_FAKE_VIOLATIONS: '["no_mask"]',
        // A cup at the top-left; only matters when a table rule and a dining-table zone there exist.
        AICAM_FAKE_OBJECTS: '[["cup", 0.1, 0.1, 0.15, 0.15]]',
        AICAM_FAKE_ZONE_HITS: '["conveyor_spillage"]', // the test engine "sees" spillage on conveyor-floor zones
      },
      reuseExistingServer: false,
      timeout: 120_000,
    },
    {
      command: `npx vite --host 127.0.0.1 --port ${FRONTEND_PORT} --strictPort`,
      url: `http://127.0.0.1:${FRONTEND_PORT}/login`,
      env: { AICAM_API_URL: `http://127.0.0.1:${BACKEND_PORT}` },
      reuseExistingServer: false,
      timeout: 60_000,
    },
  ],
})
