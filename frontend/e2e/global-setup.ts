import { execFileSync } from 'node:child_process'
import path from 'node:path'
import { BACKEND_DIR, PYTHON, TEST_VIDEO } from './paths'

// Create the test-pattern video used as a camera source (640x360, 10 fps).
export default function globalSetup() {
  execFileSync(PYTHON, [path.join(BACKEND_DIR, 'scripts', 'make_test_video.py'), TEST_VIDEO], { cwd: BACKEND_DIR })
}
