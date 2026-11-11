import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../lib/api'

// Which checks exist (and their labels) depends on the industry: see api/industry.ts.
export type CheckKey = string
export type CheckState = 'ok' | 'violation' | 'unknown'

export interface DetectionConfig {
  camera_id: number
  enabled: boolean
  checks: CheckKey[]
  min_duration_s: number
  cooldown_s: number
  interval_s: number
  handwash_min_s: number
  wash_valid_min: number
  table_clear_min: number
}

/** Settings of a camera with none saved yet (the server sends the same; checks = all of the industry's). */
export const DEFAULT_DETECTION: Omit<DetectionConfig, 'camera_id' | 'checks'> = {
  enabled: false,
  min_duration_s: 5,
  cooldown_s: 120,
  interval_s: 0.5,
  handwash_min_s: 20,
  wash_valid_min: 30,
  table_clear_min: 10,
}

export interface DetectionStatus {
  engine: { state: 'idle' | 'loading' | 'ready' | 'error'; name: string | null; device: string | null; error: string | null }
  cameras: {
    camera_id: number
    camera_name: string
    analyses_per_s: number
    last_ms: number | null
    last_at: string | null
    persons: number
    observations: Partial<Record<CheckKey, CheckState>>
    error: string | null
    paused: boolean // skipped while focus mode is on another camera
  }[]
  available_checks: CheckKey[]
  focus_camera_id: number | null
}

/** Focus mode: analyse only this camera (others pause). Expires after 30 s unless renewed. */
export async function setDetectionFocus(cameraId: number | null) {
  await api.put('/detection/focus', { camera_id: cameraId })
}

export interface LatestDetection {
  camera_id: number
  at: string
  age_ms: number
  width: number
  height: number
  inference_ms: number
  persons: {
    box: [number, number, number, number]
    score: number
    checks: Partial<Record<CheckKey, { state: CheckState; p_present: number | null; regions: [number, number, number, number][] }>>
  }[]
  /** Tableware seen (only while the "table not cleared" rule runs). */
  objects?: { label: string; box: [number, number, number, number] }[]
  /** Each dining-table zone's state for that rule. */
  tables?: {
    zone_id: number
    name: string
    state: 'occupied' | 'clear' | 'waiting' | 'not_cleared'
    items: string[]
    waited_s: number
    limit_s: number
    anchor: [number, number] // top-centre of the zone, 0..1
  }[]
  /** People inside restricted zones right now (cement plant). */
  intrusions?: { box: [number, number, number, number]; zone: string; seconds: number }[]
  /** Image checks on zones, e.g. spillage on the floor under a conveyor. */
  zone_states?: {
    zone_id: number
    name: string
    rule: string
    label: string // e.g. "Conveyor spillage"
    state: 'problem' | 'clear' | 'unsure'
    p: number
    seconds: number // problem seen for this long
    anchor: [number, number] // top-centre of the zone, 0..1
  }[]
  /** Counting lines, e.g. bags on a packing belt. */
  counters?: {
    zone_id: number
    name: string
    kind: string // e.g. "bags"
    total: number // since detection started on this camera
    per_minute: number
    line: [number, number, number] // x, y0, y1 as fractions
    passing: boolean
  }[]
}

export function useDetectionStatus() {
  return useQuery({
    queryKey: ['detection', 'status'],
    queryFn: async () => (await api.get<DetectionStatus>('/detection/status')).data,
    refetchInterval: 2000,
  })
}

export function useDetectionConfigs() {
  return useQuery({
    queryKey: ['detection', 'configs'],
    queryFn: async () => (await api.get<DetectionConfig[]>('/detection/configs')).data,
  })
}

export function useSaveDetectionConfig() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ camera_id, ...body }: DetectionConfig) =>
      (await api.put<DetectionConfig>(`/detection/cameras/${camera_id}/config`, body)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['detection'] }),
  })
}

/** Newest boxes for a camera, polled while shown. */
export function useLatestDetection(cameraId: number, enabled: boolean) {
  return useQuery({
    queryKey: ['detection', 'latest', cameraId],
    queryFn: async () => {
      try {
        return (await api.get<LatestDetection>(`/detection/cameras/${cameraId}/latest`)).data
      } catch {
        return null // no results yet
      }
    },
    enabled,
    refetchInterval: 700,
  })
}
