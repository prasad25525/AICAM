import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../lib/api'

export type Area = string // from the industry pack, e.g. "kitchen" or "production"
export type SourceType = 'webcam' | 'rtsp' | 'http' | 'file'

export interface CameraStatus {
  state: 'online' | 'offline'
  checked_at: string
  error: string | null
  width: number | null
  height: number | null
  fps: number | null
  latency_ms: number | null
}

export interface SourceTestResult {
  ok: boolean
  error: string | null
  width: number | null
  height: number | null
  fps: number | null
  latency_ms: number | null
  snapshot: string | null
}

export interface Camera {
  status: CameraStatus | null
  id: number
  name: string
  location: string | null
  industry: string
  area: Area
  source_url: string
  source_type: SourceType
  source_display: string
  enabled: boolean
  created_at: string
  updated_at: string
}

export interface CameraInput {
  name: string
  location: string | null
  area: Area
  source_url: string
  enabled: boolean
}

export interface WebcamDevice {
  index: number
  width: number
  height: number
  in_use_by: string | null
}

const KEY = ['cameras']

export function useCameras() {
  return useQuery({ queryKey: KEY, queryFn: async () => (await api.get<Camera[]>('/cameras')).data })
}

export function useWebcamDevices(enabled: boolean) {
  return useQuery({
    queryKey: [...KEY, 'devices'],
    queryFn: async () => (await api.get<WebcamDevice[]>('/cameras/devices')).data,
    enabled,
    staleTime: 0,
  })
}

/** Grab a frame from every enabled camera and refresh the list with their online/offline status. */
export function useCheckCameras() {
  const qc = useQueryClient()
  return useQuery({
    queryKey: ['camera-check'],
    queryFn: async () => {
      const { data } = await api.post<Camera[]>('/cameras/check')
      // Refetch rather than setQueryData: an edit made while the check ran must not be overwritten.
      await qc.invalidateQueries({ queryKey: KEY })
      qc.invalidateQueries({ queryKey: ['dashboard'] })
      return data
    },
    staleTime: 60_000,
    refetchOnWindowFocus: false,
  })
}

export function useTestSource() {
  return useMutation({
    mutationFn: async (source_url: string) => (await api.post<SourceTestResult>('/cameras/test', { source_url })).data,
  })
}

/** Fetch a fresh snapshot as an object URL (the endpoint needs the auth header, so <img src> can't call it directly). */
export async function fetchSnapshot(cameraId: number): Promise<string> {
  try {
    const { data } = await api.get<Blob>(`/cameras/${cameraId}/snapshot`, { responseType: 'blob' })
    return URL.createObjectURL(data)
  } catch (err) {
    // Error bodies arrive as a Blob too; unwrap FastAPI's {"detail": "..."}.
    const body = (err as { response?: { data?: unknown } }).response?.data
    if (body instanceof Blob) {
      const detail = await body.text().then((t) => JSON.parse(t).detail).catch(() => null)
      if (detail) throw new Error(detail)
    }
    throw err
  }
}

export function useSaveCamera() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, data }: { id?: number; data: Partial<CameraInput> }) =>
      id ? (await api.patch<Camera>(`/cameras/${id}`, data)).data : (await api.post<Camera>('/cameras', data)).data,
    onSuccess: (_, { id, data }) => {
      // Show the change straight away; new, re-enabled, or re-pointed cameras have no current status,
      // so also check them (a slow or unreachable camera can take ~15 s, and must not hide the list).
      const needsCheck = !id || data.enabled === true || data.source_url !== undefined
      qc.invalidateQueries({ queryKey: KEY })
      if (needsCheck) qc.invalidateQueries({ queryKey: ['camera-check'] })
      qc.invalidateQueries({ queryKey: ['dashboard'] })
    },
  })
}

export function useDeleteCamera() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (id: number) => api.delete(`/cameras/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: KEY }),
  })
}
