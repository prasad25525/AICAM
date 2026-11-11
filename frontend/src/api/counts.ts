import { useQuery } from '@tanstack/react-query'
import { api } from '../lib/api'

export interface CountSummary {
  kind: string // e.g. "bags"
  today: number
  yesterday_same_time: number
  by_camera: { camera_id: number | null; camera_name: string; count: number }[]
  by_hour: number[] // local hours 0-23
}

/** Items counted today (e.g. cement bags) for the active industry. */
export function useCountsToday(kind: string | undefined) {
  return useQuery({
    queryKey: ['counts', 'today', kind],
    queryFn: async () =>
      (await api.get<CountSummary>('/counts/today', { params: { kind, tz_offset: -new Date().getTimezoneOffset() } })).data,
    enabled: !!kind,
    refetchInterval: 5000,
  })
}
