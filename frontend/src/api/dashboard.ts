import { useQuery } from '@tanstack/react-query'
import { api } from '../lib/api'
import type { EventItem } from './events'

export interface DashboardSummary {
  hygiene_score: number
  hygiene_score_yesterday: number
  violations_today: number
  violations_yesterday: number
  open_alerts: number
  critical_open: number
  cameras_enabled: number
  cameras_online: number
  cameras_offline: number
  by_hour: { hour: number; count: number }[]
  current_hour: number
  by_type: { event_type: string; label: string; count: number }[]
  recent: EventItem[]
  cameras: { id: number; name: string; state: 'online' | 'offline' | 'unknown' | 'disabled' }[]
  score_formula: string
}

export function useDashboard() {
  return useQuery({
    queryKey: ['dashboard'],
    // Minutes east of UTC, so the backend's "today" is the browser's local day.
    queryFn: async () =>
      (await api.get<DashboardSummary>('/dashboard/summary', { params: { tz_offset: -new Date().getTimezoneOffset() } })).data,
    refetchInterval: 15_000,
  })
}
