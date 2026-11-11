import { format, formatDistanceToNowStrict, isToday } from 'date-fns'
import { BellOff, ChevronLeft, ChevronRight, FlaskConical, ImageOff, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useCameras } from '../api/cameras'
import { useAppSettings } from '../api/settings'
import {
  RANGE_LABELS,
  SEVERITY_LABELS,
  STATUS_LABELS,
  eventImageUrl,
  useBulkUpdateEvents,
  useEventTypes,
  useEvents,
  useUpdateEvent,
  type EventItem,
  type EventStatus,
  type Severity,
  type TimeRange,
} from '../api/events'
import { useMediaToken } from '../api/streams'
import { ACTION_META, NEXT_ACTIONS } from '../components/events/EventActions'
import DeleteEventsDialog from '../components/events/DeleteEventsDialog'
import EventDetailModal from '../components/events/EventDetailModal'
import EventStatusBadge from '../components/events/EventStatusBadge'
import TestEventModal from '../components/events/TestEventModal'
import { btnDanger, btnPrimary, btnSecondary, inputBase } from '../components/Modal'
import SeverityBadge from '../components/SeverityBadge'
import { apiErrorMessage } from '../lib/api'

const PAGE_SIZE = 25
const TABS: (EventStatus | 'all')[] = ['open', 'acknowledged', 'resolved', 'false_alarm', 'all']

function QuickAction({ event }: { event: EventItem }) {
  const update = useUpdateEvent()
  const next = NEXT_ACTIONS[event.status][0]
  const { label, icon: Icon } = ACTION_META[next]
  return (
    <button
      onClick={(e) => {
        e.stopPropagation()
        update.mutate({ id: event.id, status: next })
      }}
      disabled={update.isPending}
      className="inline-flex items-center gap-1 whitespace-nowrap rounded-md border border-forest-600 px-2 py-1 text-xs text-emerald-100/80 hover:border-gold-500 hover:text-white disabled:opacity-50"
      aria-label={`${label} event ${event.id}`}
    >
      <Icon size={12} /> {label}
    </button>
  )
}

export default function EventsPage() {
  const { data: appSettings } = useAppSettings()
  const [tab, setTab] = useState<EventStatus | 'all'>('open')
  const [severity, setSeverity] = useState<Severity | ''>('')
  const [cameraId, setCameraId] = useState('')
  const [eventType, setEventType] = useState('')
  const [range, setRange] = useState<TimeRange>('7d')
  const [page, setPage] = useState(0)
  const [viewing, setViewing] = useState<EventItem | null>(null)
  const [creatingTest, setCreatingTest] = useState(false)
  const [deleting, setDeleting] = useState<{ ids: number[]; label: string } | null>(null)

  const filters = {
    status: tab === 'all' ? undefined : tab,
    severity: severity || undefined,
    camera_id: cameraId ? Number(cameraId) : undefined,
    event_type: eventType || undefined,
    range,
    limit: PAGE_SIZE,
    offset: page * PAGE_SIZE,
  }
  const events = useEvents(filters)
  const types = useEventTypes()
  const cameras = useCameras()
  const token = useMediaToken()
  const bulk = useBulkUpdateEvents()

  // Selection belongs to one page of one filter set; changing either clears it.
  const filtersKey = JSON.stringify(filters)
  const [selection, setSelection] = useState<{ key: string; ids: Set<number> }>({ key: '', ids: new Set() })
  const selected = selection.key === filtersKey ? selection.ids : new Set<number>()
  const setSelected = (ids: Set<number>) => setSelection({ key: filtersKey, ids })

  const resetPage = <T,>(setter: (v: T) => void) => (v: T) => {
    setter(v)
    setPage(0)
  }

  const items = events.data?.items ?? []
  const total = events.data?.total ?? 0
  const counts = events.data?.counts
  const allCount = counts ? Object.values(counts).reduce((a, b) => a + b, 0) : 0
  const allSelected = items.length > 0 && items.every((e) => selected.has(e.id))

  async function bulkSet(status: EventStatus) {
    await bulk.mutateAsync({ ids: [...selected], status })
    setSelected(new Set())
  }

  return (
    <div className="mx-auto max-w-7xl space-y-5">
      {appSettings && (!appSettings.events_enabled || !appSettings.notifications_enabled) && (
        <div role="status" className="flex items-center gap-2 rounded-lg border border-amber-400/50 bg-amber-500/10 px-4 py-2.5 text-sm text-amber-100">
          <BellOff size={16} className="shrink-0 text-amber-300" />
          <span className="flex-1">
            {!appSettings.events_enabled
              ? 'Event recording is off: new violations are not being saved.'
              : 'Pop-up alerts are off: new events are saved here without notifying.'}
          </span>
          <Link to="/settings" className="font-medium text-gold-300 hover:text-lime-glow">Settings →</Link>
        </div>
      )}
      {/* Status tabs + test button */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div role="tablist" className="flex flex-wrap gap-1 rounded-lg border border-forest-600 bg-forest-900 p-1">
          {TABS.map((t) => {
            const n = t === 'all' ? allCount : counts?.[t]
            return (
              <button
                key={t}
                role="tab"
                aria-selected={tab === t}
                onClick={() => resetPage(setTab)(t)}
                className={`flex items-center gap-2 rounded-md px-3 py-1.5 text-sm transition ${
                  tab === t ? 'border border-gold-500 bg-forest-800 font-medium text-lime-glow' : 'border border-transparent text-emerald-100/70 hover:text-white'
                }`}
              >
                {t === 'all' ? 'All' : STATUS_LABELS[t]}
                {n !== undefined && <span className="rounded bg-forest-950/70 px-1.5 text-xs tabular-nums text-emerald-100/70">{n}</span>}
              </button>
            )
          })}
        </div>
        <button onClick={() => setCreatingTest(true)} className={btnSecondary}>
          <FlaskConical size={16} /> Create test event
        </button>
      </div>

      {/* Filters */}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <select aria-label="Time range" className={inputBase} value={range} onChange={(e) => resetPage(setRange)(e.target.value as TimeRange)}>
          {Object.entries(RANGE_LABELS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
        </select>
        <select aria-label="Severity" className={inputBase} value={severity} onChange={(e) => resetPage(setSeverity)(e.target.value as Severity | '')}>
          <option value="">All severities</option>
          {Object.entries(SEVERITY_LABELS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
        </select>
        <select aria-label="Camera" className={inputBase} value={cameraId} onChange={(e) => resetPage(setCameraId)(e.target.value)}>
          <option value="">All cameras</option>
          {cameras.data?.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
        <select aria-label="Violation type" className={inputBase} value={eventType} onChange={(e) => resetPage(setEventType)(e.target.value)}>
          <option value="">All violations</option>
          {types.data?.map((t) => <option key={t.key} value={t.key}>{t.label}</option>)}
        </select>
      </div>

      {/* Bulk actions */}
      {selected.size > 0 && (
        <div className="flex flex-wrap items-center gap-2 rounded-lg border border-gold-500/60 bg-forest-900 px-4 py-2 text-sm">
          <span className="mr-2 text-gold-300">{selected.size} selected</span>
          {(['acknowledged', 'resolved', 'false_alarm'] as EventStatus[]).map((s) => {
            const { label, icon: Icon } = ACTION_META[s]
            return (
              <button key={s} onClick={() => bulkSet(s)} disabled={bulk.isPending} className={`${btnSecondary} py-1.5`}>
                <Icon size={14} /> {label}
              </button>
            )
          })}
          <button
            onClick={() => setDeleting({ ids: [...selected], label: `${selected.size} event${selected.size === 1 ? '' : 's'}` })}
            className={`${btnDanger} py-1.5`}
          >
            <Trash2 size={14} /> Delete
          </button>
          <button onClick={() => setSelected(new Set())} className="ml-auto text-xs text-emerald-100/60 hover:text-white">Clear</button>
        </div>
      )}

      {/* Table */}
      <section className="overflow-hidden rounded-xl border border-gold-500/60 bg-forest-900">
        {events.isLoading && <p className="p-6 text-sm text-emerald-100/60">Loading events…</p>}
        {events.error && <p className="p-6 text-sm text-red-200">{apiErrorMessage(events.error)}</p>}

        {events.data && items.length === 0 && (
          <div className="flex flex-col items-center px-6 py-16 text-center">
            <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-xl border border-gold-500 bg-forest-800 text-lime-glow">
              <BellOff size={26} />
            </div>
            <h2 className="font-semibold text-white">No events</h2>
            <p className="mt-1 max-w-sm text-sm text-emerald-100/60">
              Nothing matches these filters. Detected violations will appear here; until detection is running you can create a test event.
            </p>
            <button onClick={() => setCreatingTest(true)} className={`${btnPrimary} mt-5`}>
              <FlaskConical size={16} /> Create test event
            </button>
          </div>
        )}

        {items.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[960px] text-left text-sm">
              <thead className="text-xs uppercase tracking-wider text-emerald-100/50">
                <tr className="border-b border-forest-700">
                  <th className="w-10 px-4 py-3">
                    <input
                      type="checkbox"
                      aria-label="Select all on this page"
                      checked={allSelected}
                      onChange={() => setSelected(allSelected ? new Set() : new Set(items.map((e) => e.id)))}
                      className="h-4 w-4 accent-lime-400"
                    />
                  </th>
                  <th className="px-3 py-3 font-medium">Snapshot</th>
                  <th className="px-3 py-3 font-medium">When</th>
                  <th className="px-3 py-3 font-medium">Violation</th>
                  <th className="px-3 py-3 font-medium">Camera</th>
                  <th className="px-3 py-3 font-medium">Severity</th>
                  <th className="px-3 py-3 font-medium">Status</th>
                  <th className="px-3 py-3 text-right font-medium">Action</th>
                </tr>
              </thead>
              <tbody>
                {items.map((e) => {
                  const when = new Date(e.occurred_at)
                  return (
                    <tr
                      key={e.id}
                      onClick={() => setViewing(e)}
                      className={`cursor-pointer border-b border-forest-800 last:border-0 hover:bg-forest-800/50 ${selected.has(e.id) ? 'bg-forest-800/40' : ''}`}
                    >
                      <td className="px-4 py-2" onClick={(ev) => ev.stopPropagation()}>
                        <input
                          type="checkbox"
                          aria-label={`Select event ${e.id}`}
                          checked={selected.has(e.id)}
                          onChange={() => {
                            const next = new Set(selected)
                            if (next.has(e.id)) next.delete(e.id)
                            else next.add(e.id)
                            setSelected(next)
                          }}
                          className="h-4 w-4 accent-lime-400"
                        />
                      </td>
                      <td className="px-3 py-2">
                        <div className="flex h-12 w-20 items-center justify-center overflow-hidden rounded border border-forest-600 bg-forest-950">
                          {e.has_image && token.data ? (
                            <img src={eventImageUrl(e.id, token.data)} alt="" loading="lazy" className="h-full w-full object-cover" />
                          ) : (
                            <ImageOff size={16} className="text-emerald-100/30" />
                          )}
                        </div>
                      </td>
                      <td className="whitespace-nowrap px-3 py-2">
                        <div className="tabular-nums text-white">{format(when, isToday(when) ? 'HH:mm:ss' : 'd MMM HH:mm')}</div>
                        <div className="text-xs text-emerald-100/50">{formatDistanceToNowStrict(when, { addSuffix: true })}</div>
                      </td>
                      <td className="px-3 py-2">
                        <div className="flex items-center gap-2 font-medium text-white">
                          {e.type_label}
                          {e.simulated && <span className="rounded border border-sky-400/40 px-1.5 text-[10px] font-normal uppercase tracking-wide text-sky-200">Test</span>}
                        </div>
                        <div className="max-w-[280px] truncate text-xs text-emerald-100/50">{e.message}</div>
                      </td>
                      <td className="px-3 py-2 text-emerald-100/80">
                        {e.camera_name ?? '—'}
                        {e.zone_name && <div className="text-xs text-emerald-100/40">{e.zone_name}</div>}
                      </td>
                      <td className="px-3 py-2"><SeverityBadge severity={e.severity} /></td>
                      <td className="px-3 py-2"><EventStatusBadge status={e.status} /></td>
                      <td className="px-3 py-2">
                        <div className="flex items-center justify-end gap-1">
                          <QuickAction event={e} />
                          <button
                            onClick={(ev) => {
                              ev.stopPropagation()
                              setDeleting({ ids: [e.id], label: `this ${e.type_label} event` })
                            }}
                            className="rounded-md p-1.5 text-emerald-100/60 hover:bg-red-500/15 hover:text-red-300"
                            aria-label={`Delete event ${e.id}`}
                          >
                            <Trash2 size={14} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}

        {total > PAGE_SIZE && (
          <div className="flex items-center justify-between border-t border-forest-700 px-4 py-2.5 text-sm text-emerald-100/70">
            <span className="tabular-nums">
              {page * PAGE_SIZE + 1}–{Math.min(total, (page + 1) * PAGE_SIZE)} of {total}
            </span>
            <div className="flex gap-1">
              <button onClick={() => setPage(page - 1)} disabled={page === 0} className="rounded-md p-1.5 hover:bg-forest-800 disabled:opacity-30" aria-label="Previous page">
                <ChevronLeft size={18} />
              </button>
              <button onClick={() => setPage(page + 1)} disabled={(page + 1) * PAGE_SIZE >= total} className="rounded-md p-1.5 hover:bg-forest-800 disabled:opacity-30" aria-label="Next page">
                <ChevronRight size={18} />
              </button>
            </div>
          </div>
        )}
      </section>

      {viewing && <EventDetailModal key={viewing.id} event={viewing} token={token.data} onClose={() => setViewing(null)} />}
      {creatingTest && <TestEventModal onClose={() => setCreatingTest(false)} />}
      {deleting && (
        <DeleteEventsDialog
          ids={deleting.ids}
          label={deleting.label}
          onClose={() => setDeleting(null)}
          onDeleted={() => {
            setSelected(new Set())
            // Deleting the last rows of a later page would leave it empty; step back.
            if (page > 0 && deleting.ids.length >= items.length) setPage(page - 1)
          }}
        />
      )}
    </div>
  )
}
