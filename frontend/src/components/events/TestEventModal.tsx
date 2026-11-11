import { FlaskConical, LoaderCircle } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { useCameras } from '../../api/cameras'
import { SEVERITY_LABELS, useCreateTestEvent, useEventTypes } from '../../api/events'
import { apiErrorMessage } from '../../lib/api'
import Modal, { btnPrimary, btnSecondary, inputBase } from '../Modal'

export default function TestEventModal({ onClose }: { onClose: () => void }) {
  const cameras = useCameras()
  const types = useEventTypes()
  const create = useCreateTestEvent()
  const [cameraId, setCameraId] = useState<string>('')
  const [eventType, setEventType] = useState('no_gloves')

  const selectedCamera = cameraId || String(cameras.data?.[0]?.id ?? '')

  async function submit(e: FormEvent) {
    e.preventDefault()
    await create.mutateAsync({ camera_id: Number(selectedCamera), event_type: eventType })
    onClose()
  }

  return (
    <Modal
      title="Create test event"
      onClose={onClose}
      footer={
        <>
          <button type="button" onClick={onClose} className={btnSecondary}>Cancel</button>
          <button type="submit" form="test-event-form" disabled={create.isPending || !selectedCamera} className={btnPrimary}>
            {create.isPending ? <LoaderCircle size={14} className="animate-spin" /> : <FlaskConical size={14} />}
            {create.isPending ? 'Capturing…' : 'Create'}
          </button>
        </>
      }
    >
      <form id="test-event-form" onSubmit={submit} className="space-y-4">
        <p className="text-sm text-emerald-100/70">
          Records a sample violation using the camera's current picture, so you can try the alert workflow before detection is running. It is marked as a test event.
        </p>
        {cameras.data?.length === 0 && <p className="text-sm text-amber-200">Add a camera first.</p>}
        <label className="block">
          <span className="mb-1.5 block text-xs font-medium uppercase tracking-wider text-gold-300">Camera</span>
          <select className={inputBase} value={selectedCamera} onChange={(e) => setCameraId(e.target.value)} required>
            {cameras.data?.map((c) => (
              <option key={c.id} value={c.id}>{c.name}{c.enabled ? '' : ' (disabled – no picture)'}</option>
            ))}
          </select>
        </label>
        <label className="block">
          <span className="mb-1.5 block text-xs font-medium uppercase tracking-wider text-gold-300">Violation</span>
          <select className={inputBase} value={eventType} onChange={(e) => setEventType(e.target.value)}>
            {types.data?.map((t) => (
              <option key={t.key} value={t.key}>{t.label} · {SEVERITY_LABELS[t.severity]}</option>
            ))}
          </select>
        </label>
        {create.isError && <p role="alert" className="text-sm text-red-200">{apiErrorMessage(create.error)}</p>}
      </form>
    </Modal>
  )
}
