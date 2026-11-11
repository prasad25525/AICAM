import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { api } from '../lib/api'

export interface ReportSummary {
  start: string
  end: string
  days: { date: string; violations: number; critical: number; warning: number; info: number; false_alarms: number; score: number }[]
  by_type: { event_type: string; label: string; count: number }[]
  by_camera: { name: string; count: number }[]
  by_zone: { name: string; count: number }[]
  by_hour: { hour: number; count: number }[]
  totals: {
    violations: number
    false_alarms: number
    false_alarm_rate: number | null
    open: number
    resolved: number
    avg_resolution_min: number | null
    avg_score: number
    worst_day: string | null
  }
  score_formula: string
}

const tzOffset = () => -new Date().getTimezoneOffset() // minutes east of UTC

export function useReport(start: string, end: string) {
  return useQuery({
    queryKey: ['report', start, end],
    queryFn: async () => (await api.get<ReportSummary>('/reports/summary', { params: { start, end, tz_offset: tzOffset() } })).data,
    placeholderData: keepPreviousData,
    enabled: !!start && !!end,
  })
}

/** Download the events in the range as a CSV file. */
export async function downloadCsv(start: string, end: string) {
  const res = await api.get<Blob>('/reports/export.csv', { params: { start, end, tz_offset: tzOffset() }, responseType: 'blob' })
  const url = URL.createObjectURL(res.data)
  const a = document.createElement('a')
  a.href = url
  a.download = `vigilsiddhi-events-${start}-to-${end}.csv`
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}
