import { format } from 'date-fns'
import { AlertTriangle, FlaskConical, ImageOff, LoaderCircle, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { eventImageUrl, useDeleteEvents, useUpdateEvent, type EventItem, type EventStatus, type Severity } from '../../api/events'
import { apiErrorMessage } from '../../lib/api'
import Modal, { btnDanger, btnPrimary, btnSecondary, inputBase } from '../Modal'
import SeverityBadge from '../SeverityBadge'
import { ACTION_META, NEXT_ACTIONS } from './EventActions'
import EventStatusBadge from './EventStatusBadge'
import ViolationSummary from './ViolationSummary'

const fmt = (iso: string) => format(new Date(iso), 'd MMM yyyy, HH:mm:ss')

const FRAME: Record<Severity, string> = { critical: 'border-red-500', warning: 'border-amber-400', info: 'border-sky-400' }
const TAG: Record<Severity, string> = { critical: 'bg-red-600 text-white', warning: 'bg-amber-400 text-black', info: 'bg-sky-400 text-black' }

export default function EventDetailModal({ event, token, onClose }: { event: EventItem; token?: string; onClose: () => void }) {
  const update = useUpdateEvent()
  const [note, setNote] = useState(event.note ?? '')
  const [current, setCurrent] = useState(event)
  const noteChanged = note.trim() !== (current.note ?? '')
  const del = useDeleteEvents()
  const [confirmingDelete, setConfirmingDelete] = useState(false)

  async function remove() {
    await del.mutateAsync([event.id])
    onClose()
  }

  async function save(status?: EventStatus) {
    const updated = await update.mutateAsync({ id: event.id, ...(status ? { status } : {}), ...(noteChanged ? { note: note.trim() || null } : {}) })
    setCurrent(updated)
    setNote(updated.note ?? '')
  }

  return (
    <Modal
      title={current.type_label}
      onClose={onClose}
      size="xl"
      footer={
        confirmingDelete ? (
          <>
            <span className="mr-auto self-center text-sm text-red-200">Delete this event and its snapshot permanently?</span>
            <button onClick={() => setConfirmingDelete(false)} className={btnSecondary}>Cancel</button>
            <button onClick={remove} disabled={del.isPending} className={btnDanger}>
              {del.isPending ? <LoaderCircle size={14} className="animate-spin" /> : <Trash2 size={14} />} Delete
            </button>
          </>
        ) : (
        <>
          <button onClick={() => setConfirmingDelete(true)} className={`${btnDanger} mr-auto`}>
            <Trash2 size={14} /> Delete
          </button>
          <button onClick={onClose} className={btnSecondary}>Close</button>
          {NEXT_ACTIONS[current.status].map((s, i) => {
            const { label, icon: Icon } = ACTION_META[s]
            return (
              <button key={s} onClick={() => save(s)} disabled={update.isPending} className={i === 0 ? btnPrimary : btnSecondary}>
                <Icon size={14} /> {label}
              </button>
            )
          })}
        </>
        )
      }
    >
      <div className="grid gap-5 lg:grid-cols-[1fr_320px]">
        <div className={`relative flex aspect-video items-center justify-center overflow-hidden rounded-lg border-2 bg-forest-950 ${FRAME[current.severity]}`}>
          {current.has_image && token ? (
            <>
              <img src={eventImageUrl(current.id, token)} alt={`Snapshot of ${current.type_label}`} className="h-full w-full object-contain" />
              <span className={`absolute left-2 top-2 inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-bold uppercase tracking-wide shadow-lg ${TAG[current.severity]}`}>
                <AlertTriangle size={13} /> {current.type_label}
              </span>
            </>
          ) : (
            <div className="flex flex-col items-center gap-2 text-sm text-emerald-100/50">
              <ImageOff size={28} /> No image saved
            </div>
          )}
        </div>

        <div className="space-y-4 text-sm">
          <div className="flex flex-wrap items-center gap-2">
            <SeverityBadge severity={current.severity} />
            <EventStatusBadge status={current.status} />
            {current.simulated && (
              <span className="inline-flex items-center gap-1 rounded-md border border-sky-400/40 px-2 py-0.5 text-xs text-sky-200">
                <FlaskConical size={12} /> Test event
              </span>
            )}
          </div>
          <ViolationSummary event={current} />
          <p className="text-emerald-50">{current.message}</p>

          <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5">
            <dt className="text-gold-300">Camera</dt>
            <dd className="text-white">{current.camera_name ?? '—'}{current.camera_id === null && current.camera_name ? ' (deleted)' : ''}</dd>
            {current.zone_name && (
              <>
                <dt className="text-gold-300">Zone</dt>
                <dd className="text-white">{current.zone_name}</dd>
              </>
            )}
            {current.confidence !== null && (
              <>
                <dt className="text-gold-300">Confidence</dt>
                <dd className="text-white">{Math.round(current.confidence * 100)}%</dd>
              </>
            )}
            <dt className="text-gold-300">Detected</dt>
            <dd className="text-white">{fmt(current.occurred_at)}</dd>
            {current.acknowledged_at && (
              <>
                <dt className="text-gold-300">Acknowledged</dt>
                <dd className="text-white">{fmt(current.acknowledged_at)}</dd>
              </>
            )}
            {current.resolved_at && (
              <>
                <dt className="text-gold-300">{current.status === 'false_alarm' ? 'Dismissed' : 'Resolved'}</dt>
                <dd className="text-white">{fmt(current.resolved_at)}</dd>
              </>
            )}
          </dl>

          <label className="block">
            <span className="mb-1.5 block text-xs font-medium uppercase tracking-wider text-gold-300">Note</span>
            <textarea
              className={`${inputBase} min-h-[84px] resize-y`}
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="What was done, e.g. reminded staff about gloves"
              maxLength={1000}
            />
          </label>
          {noteChanged && (
            <button onClick={() => save()} disabled={update.isPending} className={`${btnSecondary} py-1.5`}>
              {update.isPending && <LoaderCircle size={14} className="animate-spin" />} Save note
            </button>
          )}
          {update.isError && <p role="alert" className="text-sm text-red-200">{apiErrorMessage(update.error)}</p>}
          {del.isError && <p role="alert" className="text-sm text-red-200">{apiErrorMessage(del.error)}</p>}
        </div>
      </div>
    </Modal>
  )
}
