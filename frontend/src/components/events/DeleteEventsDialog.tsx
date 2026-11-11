import { LoaderCircle, Trash2 } from 'lucide-react'
import { useDeleteEvents } from '../../api/events'
import { apiErrorMessage } from '../../lib/api'
import Modal, { btnDanger, btnSecondary } from '../Modal'

/** Confirm, then permanently delete one or more events. */
export default function DeleteEventsDialog({ ids, label, onClose, onDeleted }: {
  ids: number[]
  label: string // e.g. "this No mask event" or "3 events"
  onClose: () => void
  onDeleted?: () => void
}) {
  const del = useDeleteEvents()

  async function confirm() {
    await del.mutateAsync(ids)
    onDeleted?.()
    onClose()
  }

  return (
    <Modal
      title={ids.length === 1 ? 'Delete event' : `Delete ${ids.length} events`}
      onClose={onClose}
      footer={
        <>
          <button onClick={onClose} className={btnSecondary}>Cancel</button>
          <button onClick={confirm} disabled={del.isPending} className={btnDanger}>
            {del.isPending ? <LoaderCircle size={14} className="animate-spin" /> : <Trash2 size={14} />} Delete
          </button>
        </>
      }
    >
      <p className="text-sm text-emerald-50">
        Permanently delete <strong className="text-white">{label}</strong>? The saved snapshot{ids.length === 1 ? ' is' : 's are'} removed too. This cannot be undone.
      </p>
      <p className="mt-2 text-xs text-emerald-100/50">To keep a record but stop counting it, mark it as a false alarm instead.</p>
      {del.isError && <p role="alert" className="mt-3 text-sm text-red-200">{apiErrorMessage(del.error)}</p>}
    </Modal>
  )
}
