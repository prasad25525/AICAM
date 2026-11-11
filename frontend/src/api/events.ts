import { keepPreviousData, useMutation, useQuery, useQueryClient, type QueryClient } from '@tanstack/react-query'
import { api } from '../lib/api'
import type { Area } from './cameras'

export type Severity = 'critical' | 'warning' | 'info'
export type EventStatus = 'open' | 'acknowledged' | 'resolved' | 'false_alarm'
export type TimeRange = 'today' | '24h' | '7d' | 'all'

export interface EventItem {
  id: number
  camera_id: number | null
  camera_name: string | null
  zone_id: number | null
  zone_name: string | null
  event_type: string
  type_label: string
  severity: Severity
  status: EventStatus
  message: string
  confidence: number | null
  has_image: boolean
  simulated: boolean
  note: string | null
  occurred_at: string
  acknowledged_at: string | null
  resolved_at: string | null
  evidence?: EventEvidence
}

/** Measured facts behind a violation (only the keys that apply to its type are present). */
export interface EventEvidence {
  wash_seconds?: number
  handwash_min_s?: number
  items?: string[]
  waited_min?: number
  table_clear_min?: number
  persons_in_view?: number
  persons_in_violation?: number
  min_duration_s?: number
  seconds_inside?: number // restricted area: how long the person had been inside
  seconds_seen?: number // image zone checks (e.g. spillage): how long the problem had been visible
}

export interface EventList {
  items: EventItem[]
  total: number
  counts: Record<EventStatus, number>
}

export interface EventType {
  key: string
  label: string
  severity: Severity
  area: Area
}

export interface EventFilters {
  status?: EventStatus
  severity?: Severity
  camera_id?: number
  event_type?: string
  range: TimeRange
  limit: number
  offset: number
}

export const STATUS_LABELS: Record<EventStatus, string> = {
  open: 'Open',
  acknowledged: 'Acknowledged',
  resolved: 'Resolved',
  false_alarm: 'False alarm',
}

export const SEVERITY_LABELS: Record<Severity, string> = { critical: 'Critical', warning: 'Warning', info: 'Info' }

export const RANGE_LABELS: Record<TimeRange, string> = { today: 'Today', '24h': 'Last 24 hours', '7d': 'Last 7 days', all: 'All time' }

function rangeStart(range: TimeRange): string | undefined {
  const now = new Date()
  if (range === 'today') return new Date(now.getFullYear(), now.getMonth(), now.getDate()).toISOString()
  if (range === '24h') return new Date(now.getTime() - 24 * 3600_000).toISOString()
  if (range === '7d') return new Date(now.getTime() - 7 * 24 * 3600_000).toISOString()
  return undefined
}

const KEY = ['events']

/** Event changes affect the list, the open-count badges, and the dashboard. */
function invalidateAfterChange(qc: QueryClient) {
  qc.invalidateQueries({ queryKey: KEY })
  qc.invalidateQueries({ queryKey: ['dashboard'] })
}

export function useEvents(filters: EventFilters) {
  return useQuery({
    queryKey: [...KEY, filters],
    queryFn: async () => {
      const { range, ...rest } = filters
      // The start time is worked out when fetching, so "Today" stays correct on each refresh.
      const params = { ...rest, since: rangeStart(range) }
      return (await api.get<EventList>('/events', { params })).data
    },
    placeholderData: keepPreviousData,
    refetchInterval: 10_000,
  })
}

/** Number of open events, for the sidebar badge and the bell. */
export function useOpenEventCount() {
  return useQuery({
    queryKey: [...KEY, 'open-count'],
    queryFn: async () => (await api.get<EventList>('/events', { params: { status: 'open', limit: 1 } })).data.total,
    refetchInterval: 10_000,
  })
}

export function useEventTypes() {
  return useQuery({
    queryKey: ['event-types'],
    queryFn: async () => (await api.get<EventType[]>('/events/types')).data,
    staleTime: Infinity,
  })
}

export function useUpdateEvent() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, ...data }: { id: number; status?: EventStatus; note?: string | null }) =>
      (await api.patch<EventItem>(`/events/${id}`, data)).data,
    onSuccess: () => invalidateAfterChange(qc),
  })
}

export function useBulkUpdateEvents() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (data: { ids: number[]; status: EventStatus }) => (await api.post<EventItem[]>('/events/bulk', data)).data,
    onSuccess: () => invalidateAfterChange(qc),
  })
}

export function useCreateTestEvent() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (data: { camera_id: number; event_type: string }) => (await api.post<EventItem>('/events/test', data)).data,
    onSuccess: () => invalidateAfterChange(qc),
  })
}

/** Permanently delete events (and their images). */
export function useDeleteEvents() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (ids: number[]) => {
      if (ids.length === 1) await api.delete(`/events/${ids[0]}`)
      else await api.post('/events/bulk-delete', { ids })
    },
    onSuccess: () => invalidateAfterChange(qc),
  })
}

export function eventImageUrl(eventId: number, token: string) {
  return `/api/events/${eventId}/image?token=${encodeURIComponent(token)}`
}
