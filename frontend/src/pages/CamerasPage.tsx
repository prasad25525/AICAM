import { Camera as CameraIcon, FileVideo, Globe, Image, LoaderCircle, Pencil, Plus, RefreshCw, SlidersHorizontal, Trash2, Webcam } from 'lucide-react'
import { useState } from 'react'
import { useCameras, useCheckCameras, useDeleteCamera, useSaveCamera, type Camera, type SourceType } from '../api/cameras'
import { DEFAULT_DETECTION, useDetectionConfigs, useSaveDetectionConfig, type DetectionConfig } from '../api/detection'
import { areaLabel, useIndustry } from '../api/industry'
import CameraFormModal from '../components/cameras/CameraFormModal'
import DetectionSettingsModal from '../components/cameras/DetectionSettingsModal'
import SnapshotModal from '../components/cameras/SnapshotModal'
import StatusBadge from '../components/cameras/StatusBadge'
import Modal, { btnDanger, btnPrimary, btnSecondary } from '../components/Modal'
import { apiErrorMessage } from '../lib/api'

const SOURCE_ICONS: Record<SourceType, typeof Webcam> = { webcam: Webcam, rtsp: Globe, http: Globe, file: FileVideo }
const SOURCE_LABELS: Record<SourceType, string> = { webcam: 'Webcam', rtsp: 'RTSP', http: 'HTTP', file: 'File' }


function DetectionCell({ camera, config, onSettings }: { camera: Camera; config: DetectionConfig; onSettings: () => void }) {
  const save = useSaveDetectionConfig()
  const on = save.isPending ? !config.enabled : config.enabled
  return (
    <div className="flex items-center gap-2">
      <button
        role="switch"
        aria-checked={on}
        aria-label={`${on ? 'Stop' : 'Start'} detection on ${camera.name}`}
        disabled={save.isPending || !camera.enabled}
        title={camera.enabled ? undefined : 'Enable the camera first'}
        onClick={() => save.mutate({ ...config, enabled: !config.enabled })}
        className={`relative h-6 w-11 shrink-0 rounded-full transition disabled:cursor-not-allowed disabled:opacity-40 ${on ? 'bg-lime-glow' : 'bg-forest-700'}`}
      >
        <span className={`absolute left-0.5 top-0.5 h-5 w-5 rounded-full transition ${on ? 'translate-x-5 bg-forest-950' : 'bg-emerald-100/70'}`} />
      </button>
      <button onClick={onSettings} className="rounded-lg p-1.5 text-emerald-100/60 hover:bg-forest-800 hover:text-lime-glow" aria-label={`Detection settings for ${camera.name}`}>
        <SlidersHorizontal size={15} />
      </button>
    </div>
  )
}

function EnabledToggle({ camera }: { camera: Camera }) {
  const save = useSaveCamera()
  const on = save.isPending ? !camera.enabled : camera.enabled
  return (
    <button
      role="switch"
      aria-checked={on}
      aria-label={`${on ? 'Disable' : 'Enable'} ${camera.name}`}
      disabled={save.isPending}
      onClick={() => save.mutate({ id: camera.id, data: { enabled: !camera.enabled } })}
      className={`relative h-6 w-11 shrink-0 rounded-full transition ${on ? 'bg-lime-glow' : 'bg-forest-700'}`}
    >
      <span className={`absolute left-0.5 top-0.5 h-5 w-5 rounded-full transition ${on ? 'translate-x-5 bg-forest-950' : 'bg-emerald-100/70'}`} />
    </button>
  )
}

function DeleteDialog({ camera, onClose }: { camera: Camera; onClose: () => void }) {
  const del = useDeleteCamera()
  return (
    <Modal
      title="Delete camera"
      onClose={onClose}
      footer={
        <>
          <button onClick={onClose} className={btnSecondary}>Cancel</button>
          <button
            disabled={del.isPending}
            onClick={() => del.mutate(camera.id, { onSuccess: onClose })}
            className={btnDanger}
          >
            {del.isPending ? <LoaderCircle size={14} className="animate-spin" /> : <Trash2 size={14} />} Delete
          </button>
        </>
      }
    >
      <p className="text-sm text-emerald-50">
        Delete <strong className="text-white">{camera.name}</strong>? Its zones will be removed. Past events are kept.
      </p>
      {del.isError && <p className="mt-3 text-sm text-red-200">{apiErrorMessage(del.error)}</p>}
    </Modal>
  )
}

export default function CamerasPage() {
  const { data: cameras, isLoading, error } = useCameras()
  const check = useCheckCameras() // runs once when the page opens
  const [editing, setEditing] = useState<Camera | 'new' | null>(null)
  const [deleting, setDeleting] = useState<Camera | null>(null)
  const [viewing, setViewing] = useState<Camera | null>(null)
  const [tuning, setTuning] = useState<Camera | null>(null)
  const configs = useDetectionConfigs()
  const { data: industry } = useIndustry()
  const allChecks = [...(industry?.ppe_checks ?? []), ...(industry?.zone_rules ?? [])].map((c) => c.key)
  const configFor = (id: number): DetectionConfig =>
    configs.data?.find((c) => c.camera_id === id) ?? { camera_id: id, checks: allChecks, ...DEFAULT_DETECTION }

  const enabledCount = cameras?.filter((c) => c.enabled).length ?? 0
  const onlineCount = cameras?.filter((c) => c.enabled && c.status?.state === 'online').length ?? 0

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-emerald-100/60">
          {cameras ? `${cameras.length} camera${cameras.length === 1 ? '' : 's'} · ${enabledCount} enabled · ${onlineCount} online` : ' '}
        </p>
        <div className="flex gap-2">
          {!!cameras?.length && (
            <button onClick={() => check.refetch()} disabled={check.isFetching} className={btnSecondary}>
              <RefreshCw size={16} className={check.isFetching ? 'animate-spin' : ''} />
              {check.isFetching ? 'Checking…' : 'Check now'}
            </button>
          )}
          <button onClick={() => setEditing('new')} className={btnPrimary}>
            <Plus size={16} /> Add camera
          </button>
        </div>
      </div>

      <section className="overflow-hidden rounded-xl border border-gold-500/60 bg-forest-900">
        {isLoading && <p className="p-6 text-sm text-emerald-100/60">Loading cameras…</p>}
        {error && <p className="p-6 text-sm text-red-200">{apiErrorMessage(error)}</p>}

        {cameras?.length === 0 && (
          <div className="flex flex-col items-center px-6 py-16 text-center">
            <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-xl border border-gold-500 bg-forest-800 text-lime-glow">
              <CameraIcon size={26} />
            </div>
            <h2 className="font-semibold text-white">No cameras yet</h2>
            <p className="mt-1 max-w-sm text-sm text-emerald-100/60">Add your webcam to start. IP cameras and recorded videos can be added the same way.</p>
            <button onClick={() => setEditing('new')} className={`${btnPrimary} mt-5`}>
              <Plus size={16} /> Add camera
            </button>
          </div>
        )}

        {!!cameras?.length && (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[1000px] text-left text-sm">
              <thead className="text-xs uppercase tracking-wider text-emerald-100/50">
                <tr className="border-b border-forest-700">
                  <th className="px-5 py-3 font-medium">Camera</th>
                  <th className="px-5 py-3 font-medium">Area</th>
                  <th className="px-5 py-3 font-medium">Source</th>
                  <th className="px-5 py-3 font-medium">Status</th>
                  <th className="px-5 py-3 font-medium">Enabled</th>
                  <th className="px-5 py-3 font-medium">Detection</th>
                  <th className="px-5 py-3 text-right font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {cameras.map((c) => {
                  const Icon = SOURCE_ICONS[c.source_type]
                  return (
                    <tr key={c.id} className={`border-b border-forest-800 last:border-0 hover:bg-forest-800/50 ${c.enabled ? '' : 'opacity-60'}`}>
                      <td className="px-5 py-3">
                        <div className="whitespace-nowrap font-medium text-white">{c.name}</div>
                        <div className="text-xs text-emerald-100/50">{c.location ?? '—'}</div>
                      </td>
                      <td className="px-5 py-3 text-emerald-100/80">{areaLabel(industry, c.area)}</td>
                      <td className="px-5 py-3">
                        <div className="flex items-center gap-2">
                          <span className="inline-flex items-center gap-1 rounded-md border border-gold-500/50 px-1.5 py-0.5 text-xs text-gold-300">
                            <Icon size={12} /> {SOURCE_LABELS[c.source_type]}
                          </span>
                          <span className="max-w-[260px] truncate font-mono text-xs text-emerald-100/70" title={c.source_display}>
                            {c.source_type === 'webcam' ? `Device ${c.source_display}` : c.source_display}
                          </span>
                        </div>
                      </td>
                      <td className="px-5 py-3"><StatusBadge camera={c} checking={check.isFetching} /></td>
                      <td className="px-5 py-3"><EnabledToggle camera={c} /></td>
                      <td className="px-5 py-3"><DetectionCell camera={c} config={configFor(c.id)} onSettings={() => setTuning(c)} /></td>
                      <td className="px-5 py-3">
                        <div className="flex justify-end gap-1">
                          <button
                            onClick={() => setViewing(c)}
                            disabled={!c.enabled}
                            title={c.enabled ? 'Take snapshot' : 'Enable the camera to take a snapshot'}
                            className="rounded-lg p-2 text-emerald-100/70 hover:bg-forest-800 hover:text-lime-glow disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:bg-transparent disabled:hover:text-emerald-100/70"
                            aria-label={`Snapshot ${c.name}`}
                          >
                            <Image size={16} />
                          </button>
                          <button onClick={() => setEditing(c)} className="rounded-lg p-2 text-emerald-100/70 hover:bg-forest-800 hover:text-lime-glow" aria-label={`Edit ${c.name}`}>
                            <Pencil size={16} />
                          </button>
                          <button onClick={() => setDeleting(c)} className="rounded-lg p-2 text-emerald-100/70 hover:bg-red-500/15 hover:text-red-300" aria-label={`Delete ${c.name}`}>
                            <Trash2 size={16} />
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
      </section>

      {editing && <CameraFormModal camera={editing === 'new' ? undefined : editing} onClose={() => setEditing(null)} />}
      {deleting && <DeleteDialog camera={deleting} onClose={() => setDeleting(null)} />}
      {viewing && <SnapshotModal camera={viewing} onClose={() => setViewing(null)} />}
      {tuning && <DetectionSettingsModal camera={tuning} config={configFor(tuning.id)} onClose={() => setTuning(null)} />}
    </div>
  )
}
