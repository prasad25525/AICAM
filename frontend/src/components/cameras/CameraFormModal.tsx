import { CircleCheck, CircleX, FileVideo, Globe, LoaderCircle, PlugZap, RefreshCw, Webcam } from 'lucide-react'
import { useState, type FormEvent, type ReactNode } from 'react'
import { useSaveCamera, useTestSource, useWebcamDevices, type Area, type Camera } from '../../api/cameras'
import { useIndustry } from '../../api/industry'
import { apiErrorMessage } from '../../lib/api'
import Modal, { btnPrimary, btnSecondary, inputBase } from '../Modal'

type SourceMode = 'webcam' | 'stream' | 'file'

const MODES: { id: SourceMode; label: string; icon: typeof Webcam }[] = [
  { id: 'webcam', label: 'Webcam', icon: Webcam },
  { id: 'stream', label: 'Stream URL', icon: Globe },
  { id: 'file', label: 'Video file', icon: FileVideo },
]

function modeOf(camera?: Camera): SourceMode {
  if (!camera || camera.source_type === 'webcam') return 'webcam'
  return camera.source_type === 'file' ? 'file' : 'stream'
}

function Field({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-xs font-medium uppercase tracking-wider text-gold-300">{label}</span>
      {children}
      {hint && <span className="mt-1 block text-xs text-emerald-100/50">{hint}</span>}
    </label>
  )
}

export default function CameraFormModal({ camera, onClose }: { camera?: Camera; onClose: () => void }) {
  const [name, setName] = useState(camera?.name ?? '')
  const [location, setLocation] = useState(camera?.location ?? '')
  const { data: industry } = useIndustry()
  // '' = not chosen yet: the industry's default area (also what the server uses).
  const [chosenArea, setArea] = useState<Area>(camera?.area ?? '')
  const area = chosenArea || industry?.default_area || ''
  const [enabled, setEnabled] = useState(camera?.enabled ?? true)
  const [mode, setMode] = useState<SourceMode>(modeOf(camera))
  const [sources, setSources] = useState<Record<SourceMode, string>>({
    webcam: camera?.source_type === 'webcam' ? camera.source_url : '0',
    stream: camera && modeOf(camera) === 'stream' ? camera.source_url : '',
    file: camera?.source_type === 'file' ? camera.source_url : '',
  })
  const [error, setError] = useState('')

  const devices = useWebcamDevices(mode === 'webcam')
  const save = useSaveCamera()
  const test = useTestSource()

  const setSource = (value: string) => setSources((s) => ({ ...s, [mode]: value }))
  const currentSource = sources[mode].trim()
  // Only show a test result while it still matches the source being edited.
  const testIsCurrent = test.variables === currentSource

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError('')
    try {
      await save.mutateAsync({
        id: camera?.id,
        data: { name, location: location.trim() || null, ...(area ? { area } : {}), enabled, source_url: sources[mode].trim() },
      })
      onClose()
    } catch (err) {
      setError(apiErrorMessage(err))
    }
  }

  return (
    <Modal
      title={camera ? `Edit ${camera.name}` : 'Add camera'}
      onClose={onClose}
      footer={
        <>
          <button type="button" onClick={onClose} className={btnSecondary}>Cancel</button>
          <button type="submit" form="camera-form" disabled={save.isPending} className={btnPrimary}>
            {save.isPending && <LoaderCircle size={14} className="animate-spin" />}
            {camera ? 'Save changes' : 'Add camera'}
          </button>
        </>
      }
    >
      <form id="camera-form" onSubmit={handleSubmit} className="space-y-4">
        <Field label="Name">
          <input className={inputBase} value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Kitchen – Prep 1" maxLength={100} required autoFocus />
        </Field>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Field label="Location">
            <input className={inputBase} value={location} onChange={(e) => setLocation(e.target.value)} placeholder="e.g. Above prep counter" maxLength={200} />
          </Field>
          <Field label="Area">
            <select className={inputBase} value={area} onChange={(e) => setArea(e.target.value)}>
              {(industry?.areas ?? []).map(({ key, label }) => (
                <option key={key} value={key}>{label}</option>
              ))}
            </select>
          </Field>
        </div>

        <div>
          <span className="mb-1.5 block text-xs font-medium uppercase tracking-wider text-gold-300">Source</span>
          <div className="mb-3 grid grid-cols-3 gap-1 rounded-lg border border-forest-600 bg-forest-950/70 p-1" role="radiogroup">
            {MODES.map(({ id, label, icon: Icon }) => (
              <button
                key={id}
                type="button"
                role="radio"
                aria-checked={mode === id}
                onClick={() => setMode(id)}
                className={`flex items-center justify-center gap-1.5 rounded-md px-2 py-1.5 text-xs font-medium transition ${
                  mode === id ? 'border border-gold-500 bg-forest-800 text-lime-glow' : 'border border-transparent text-emerald-100/60 hover:text-white'
                }`}
              >
                <Icon size={14} /> {label}
              </button>
            ))}
          </div>

          {mode === 'webcam' && (
            <div className="space-y-2">
              <div className="flex items-center justify-between text-xs text-emerald-100/60">
                <span>Detected webcams</span>
                <button type="button" onClick={() => devices.refetch()} className="flex items-center gap-1 hover:text-lime-glow">
                  <RefreshCw size={12} className={devices.isFetching ? 'animate-spin' : ''} /> Rescan
                </button>
              </div>
              {devices.isFetching && !devices.data && <p className="text-sm text-emerald-100/60">Scanning…</p>}
              {devices.data?.length === 0 && (
                <p className="rounded-lg border border-amber-400/40 bg-amber-500/10 px-3 py-2 text-xs text-amber-200">
                  No webcam found. Close other apps using it (Zoom, Teams, Camera) and rescan, or enter the number below.
                </p>
              )}
              <div className="grid gap-2">
                {devices.data?.map((d) => {
                  const selected = sources.webcam === String(d.index)
                  const usedByOther = d.in_use_by && d.in_use_by !== camera?.name
                  return (
                    <button
                      key={d.index}
                      type="button"
                      onClick={() => setSource(String(d.index))}
                      className={`flex items-center justify-between rounded-lg border px-3 py-2 text-left text-sm transition ${
                        selected ? 'border-lime-glow bg-forest-800 text-white' : 'border-forest-600 text-emerald-100/80 hover:border-gold-500'
                      }`}
                    >
                      <span className="flex items-center gap-2">
                        <Webcam size={16} className={selected ? 'text-lime-glow' : 'text-gold-400'} />
                        Webcam {d.index}
                        <span className="text-xs text-emerald-100/50">{d.width}×{d.height}</span>
                      </span>
                      {usedByOther && <span className="text-xs text-amber-200">used by {d.in_use_by}</span>}
                    </button>
                  )
                })}
              </div>
              <Field label="Webcam number" hint="0 is usually the built-in camera, 1 the first USB camera.">
                <input className={inputBase} value={sources.webcam} onChange={(e) => setSource(e.target.value.replace(/\D/g, ''))} inputMode="numeric" required />
              </Field>
            </div>
          )}

          {mode === 'stream' && (
            <Field label="Stream URL" hint="RTSP or HTTP link from the camera or NVR, e.g. rtsp://user:password@192.168.1.10:554/stream1">
              <input className={inputBase} value={sources.stream} onChange={(e) => setSource(e.target.value)} placeholder="rtsp://…" required />
            </Field>
          )}

          {mode === 'file' && (
            <Field label="Video file path" hint="Full path on the backend machine, e.g. F:\Videos\kitchen.mp4. Useful for testing with recorded footage.">
              <input className={inputBase} value={sources.file} onChange={(e) => setSource(e.target.value)} placeholder="F:\Videos\kitchen.mp4" required />
            </Field>
          )}
        </div>

        <div className="rounded-lg border border-forest-600 p-3">
          <div className="flex items-center justify-between gap-3">
            <span className="text-xs text-emerald-100/60">Check the source works before saving.</span>
            <button
              type="button"
              onClick={() => test.mutate(currentSource)}
              disabled={!currentSource || test.isPending}
              className={`${btnSecondary} shrink-0 py-1.5`}
            >
              {test.isPending ? <LoaderCircle size={14} className="animate-spin" /> : <PlugZap size={14} />}
              {test.isPending ? 'Testing…' : 'Test connection'}
            </button>
          </div>

          {testIsCurrent && test.isSuccess && test.data.ok && (
            <div className="mt-3 space-y-2">
              <p role="status" className="flex items-center gap-1.5 text-sm text-lime-glow">
                <CircleCheck size={16} /> Connected · {test.data.width}×{test.data.height}
                {test.data.fps ? ` · ${test.data.fps} fps` : ''} · {((test.data.latency_ms ?? 0) / 1000).toFixed(1)}s
              </p>
              <img src={test.data.snapshot!} alt="Test snapshot" className="w-full rounded-md border border-gold-500/50" />
            </div>
          )}
          {testIsCurrent && ((test.isSuccess && !test.data.ok) || test.isError) && (
            <p role="status" className="mt-3 flex items-start gap-1.5 text-sm text-red-200">
              <CircleX size={16} className="mt-0.5 shrink-0" />
              {test.isError ? apiErrorMessage(test.error) : test.data?.error}
            </p>
          )}
        </div>

        <label className="flex cursor-pointer items-center justify-between rounded-lg border border-forest-600 px-3 py-2.5">
          <span>
            <span className="block text-sm text-white">Enabled</span>
            <span className="block text-xs text-emerald-100/50">Disabled cameras are kept but not monitored.</span>
          </span>
          <input type="checkbox" checked={enabled} onChange={(e) => setEnabled(e.target.checked)} className="peer sr-only" />
          <span className="relative h-6 w-11 rounded-full bg-forest-700 transition after:absolute after:left-0.5 after:top-0.5 after:h-5 after:w-5 after:rounded-full after:bg-emerald-100/70 after:transition peer-checked:bg-lime-glow peer-checked:after:translate-x-5 peer-checked:after:bg-forest-950 peer-focus-visible:ring-2 peer-focus-visible:ring-lime-glow/50" />
        </label>

        {error && (
          <p role="alert" className="rounded-lg border border-red-400/40 bg-red-500/10 px-3 py-2 text-sm text-red-200">{error}</p>
        )}
      </form>
    </Modal>
  )
}
