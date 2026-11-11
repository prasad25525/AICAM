import { useQuery, type QueryClient } from '@tanstack/react-query'
import { api, type LoginResponse } from '../lib/api'

export interface StreamInfo {
  camera_id: number
  state: 'connecting' | 'live' | 'error' | 'stopped'
  error: string | null
  fps: number
  width: number | null
  height: number | null
  viewers: number
}

const TOKEN_KEY = ['media-token']

/** Short-lived token for <img src> / EventSource URLs (streams, event images, live alerts). */
export const mediaTokenQuery = {
  queryKey: TOKEN_KEY,
  queryFn: async () => (await api.post<LoginResponse>('/auth/media-token')).data.access_token,
  staleTime: 3 * 60_000,
}

/** The media token, refreshed before it expires (5 min). */
export function useMediaToken() {
  return useQuery({ ...mediaTokenQuery, refetchInterval: 3 * 60_000 })
}

export function latestMediaToken(qc: QueryClient): string | undefined {
  return qc.getQueryData<string>(TOKEN_KEY)
}

/** Open streams with their state (connecting / live / error) and measured fps. */
export function useStreams() {
  return useQuery({
    queryKey: ['streams'],
    queryFn: async () => (await api.get<StreamInfo[]>('/streams')).data,
    refetchInterval: 2000,
  })
}

export function streamUrl(cameraId: number, token: string, attempt = 0) {
  return `/api/cameras/${cameraId}/stream?token=${encodeURIComponent(token)}${attempt ? `&r=${attempt}` : ''}`
}
