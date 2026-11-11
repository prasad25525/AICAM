import os from 'node:os'
import path from 'node:path'

export const BACKEND_DIR = path.resolve(import.meta.dirname, '../../backend')
export const PYTHON = path.join(BACKEND_DIR, '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python')
export const TEST_VIDEO = path.join(os.tmpdir(), 'aicam-e2e-test-pattern.mp4')

// Documentation address (TEST-NET-1): never routable, so connecting always fails.
export const UNREACHABLE_RTSP = 'rtsp://admin:secret@192.0.2.1:554/stream1'
