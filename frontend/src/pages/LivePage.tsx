import { BellOff, Grid2x2, Map as MapIcon, MonitorPlay, ScanFace, Settings2, Zap } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useCameras } from '../api/cameras'
import { setDetectionFocus, useDetectionStatus } from '../api/detection'
import { useAppSettings } from '../api/settings'
import { useStreams, useMediaToken } from '../api/streams'
import LiveTile from '../components/live/LiveTile'
import { btnPrimary, btnSecondary, inputBase } from '../components/Modal'
import { apiErrorMessage } from '../lib/api'

const FOCUS_RENEW_MS = 10_000 // the backend drops focus after 30 s without a renewal

export default function LivePage() {
  const cameras = useCameras()
  const token = useMediaToken()
  const streams = useStreams()
  const detection = useDetectionStatus()
  const { data: appSettings } = useAppSettings()
  const [params, setParams] = useSearchParams()
  const [showDetections, setShowDetections] = useState(true)
  const [showZones, setShowZones] = useState(false)
  const [fastDetection, setFastDetection] = useState(true)

  const live = cameras.data?.filter((c) => c.enabled) ?? []
  const selectedId = Number(params.get('camera')) || null
  const selected = live.find((c) => c.id === selectedId) ?? null // unknown / disabled id falls back to the grid
  const infoFor = (id: number) => streams.data?.find((s) => s.camera_id === id)
  const detectionFor = (id: number) => detection.data?.cameras.find((d) => d.camera_id === id)
  const liveCount = live.filter((c) => infoFor(c.id)?.state === 'live').length
  const detectingCount = live.filter((c) => detectionFor(c.id)).length
  const error = cameras.error ?? token.error
  const selectedHasDetection = !!selected && !!detectionFor(selected.id)
  const focusing = !!selected && fastDetection && selectedHasDetection

  function select(id: number | null) {
    setParams(id ? { camera: String(id) } : {}, { replace: true })
  }

  // Focus mode: while one camera is shown with fast detection on, ask the backend to analyse only
  // it, renewing every 10 s. Leaving (or switching back to the grid) ends it straight away.
  const focusId = focusing ? selected.id : null
  useEffect(() => {
    if (focusId === null) return
    setDetectionFocus(focusId).catch(() => {})
    const timer = window.setInterval(() => setDetectionFocus(focusId).catch(() => {}), FOCUS_RENEW_MS)
    return () => {
      window.clearInterval(timer)
      setDetectionFocus(null).catch(() => {})
    }
  }, [focusId])

  return (
    <div className="mx-auto max-w-7xl space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-3">
          <select
            aria-label="Camera to show"
            className={`${inputBase} w-72`}
            value={selected?.id ?? ''}
            onChange={(e) => select(e.target.value ? Number(e.target.value) : null)}
          >
            <option value="">All cameras (grid)</option>
            {live.map((c) => (
              <option key={c.id} value={c.id}>{c.name}</option>
            ))}
          </select>
          {selected && (
            <button onClick={() => select(null)} className={`${btnSecondary} py-2`}>
              <Grid2x2 size={16} /> Back to all
            </button>
          )}
          <p className="text-sm text-emerald-100/60">
            {cameras.data ? `${live.length} camera${live.length === 1 ? '' : 's'} · ${liveCount} streaming · ${detectingCount} with detection` : ' '}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-4">
          {selected && (
            <label className="inline-flex cursor-pointer items-center gap-2 text-sm text-emerald-100/80" title="Analyse only this camera, several times a second. Other cameras pause.">
              <input type="checkbox" checked={fastDetection} onChange={(e) => setFastDetection(e.target.checked)} className="h-4 w-4 accent-lime-400" />
              <Zap size={16} className="text-lime-glow" /> Fast detection
            </label>
          )}
          <label className="inline-flex cursor-pointer items-center gap-2 text-sm text-emerald-100/80">
            <input type="checkbox" checked={showDetections} onChange={(e) => setShowDetections(e.target.checked)} className="h-4 w-4 accent-lime-400" />
            <ScanFace size={16} className="text-lime-glow" /> Show detections
          </label>
          <label className="inline-flex cursor-pointer items-center gap-2 text-sm text-emerald-100/80">
            <input type="checkbox" checked={showZones} onChange={(e) => setShowZones(e.target.checked)} className="h-4 w-4 accent-lime-400" />
            <MapIcon size={16} className="text-gold-400" /> Show zones
          </label>
          <Link to="/cameras" className="inline-flex items-center gap-1.5 text-sm text-gold-300 hover:text-lime-glow">
            <Settings2 size={16} /> Manage cameras
          </Link>
        </div>
      </div>

      {error && <p className="rounded-lg border border-red-400/40 bg-red-500/10 px-4 py-3 text-sm text-red-200">{apiErrorMessage(error)}</p>}

      {detection.data?.engine.state === 'loading' && (
        <p className="rounded-lg border border-gold-500/40 bg-gold-500/10 px-4 py-2 text-sm text-gold-300">Loading detection models… this takes about 15–30 seconds.</p>
      )}
      {detection.data?.engine.state === 'error' && (
        <p className="rounded-lg border border-red-400/40 bg-red-500/10 px-4 py-2 text-sm text-red-200">Detection could not start: {detection.data.engine.error}</p>
      )}
      {focusing && (
        <p role="status" className="flex items-center gap-2 rounded-lg border border-lime-glow/40 bg-lime-glow/10 px-4 py-2 text-sm text-lime-glow">
          <Zap size={16} /> Fast detection: only <strong>{selected.name}</strong> is being analysed. Other cameras are paused (no alerts from them) until you go back to all cameras.
        </p>
      )}
      {appSettings && !appSettings.events_enabled && (
        <p role="status" className="flex items-center gap-2 rounded-lg border border-amber-400/50 bg-amber-500/10 px-4 py-2 text-sm text-amber-100">
          <BellOff size={16} className="shrink-0 text-amber-300" />
          <span className="flex-1">Event recording is off: boxes are drawn here, but no violations are saved or alerted.</span>
          <Link to="/settings" className="font-medium text-gold-300 hover:text-lime-glow">Settings →</Link>
        </p>
      )}
      {selected && !selectedHasDetection && detection.data && (
        <p className="rounded-lg border border-gold-500/40 bg-gold-500/10 px-4 py-2 text-sm text-gold-300">
          Detection is off for this camera. Turn it on under <Link to="/cameras" className="underline hover:text-lime-glow">Cameras → Detection</Link>.
        </p>
      )}

      {cameras.data && live.length === 0 && (
        <div className="flex flex-col items-center rounded-xl border border-gold-500/60 bg-forest-900 px-6 py-16 text-center">
          <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-xl border border-gold-500 bg-forest-800 text-lime-glow">
            <MonitorPlay size={26} />
          </div>
          <h2 className="font-semibold text-white">No cameras to show</h2>
          <p className="mt-1 max-w-sm text-sm text-emerald-100/60">Add a camera, or enable one, to watch it live here.</p>
          <Link to="/cameras" className={`${btnPrimary} mt-5`}>Go to Cameras</Link>
        </div>
      )}

      {/* One camera, large: a continuous stream is fine for a single tile. */}
      {token.data && selected && (
        <div className="mx-auto max-w-5xl">
          <LiveTile
            key={`single:${selected.id}:${selected.source_url}`}
            camera={selected}
            token={token.data}
            info={infoFor(selected.id)}
            detection={detectionFor(selected.id)}
            showDetections={showDetections}
            showZones={showZones}
            large
          />
        </div>
      )}

      {/* All cameras: tiles poll single frames (a stream per tile would exhaust the browser's connections). */}
      {token.data && !selected && live.length > 0 && (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 2xl:grid-cols-3">
          {live.map((c) => (
            <LiveTile
              key={`${c.id}:${c.source_url}`}
              camera={c}
              token={token.data}
              info={infoFor(c.id)}
              detection={detectionFor(c.id)}
              showDetections={showDetections}
              showZones={showZones}
              mode="poll"
              onExpand={() => select(c.id)}
            />
          ))}
        </div>
      )}
    </div>
  )
}
