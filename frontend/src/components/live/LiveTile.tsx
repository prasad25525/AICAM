import { useQueryClient } from '@tanstack/react-query'
import { LoaderCircle, Maximize2, RefreshCw, ScanFace, WifiOff } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import type { Camera } from '../../api/cameras'
import { areaLabel, useIndustry } from '../../api/industry'
import { latestMediaToken, streamUrl, type StreamInfo } from '../../api/streams'
import DetectionOverlay from './DetectionOverlay'
import ZonesOverlay from './ZonesOverlay'

const RETRY_DELAY_MS = 3000
const POLL_FPS = 5 // enough to look live in a grid, while leaving CPU for detection on a laptop

interface Props {
  camera: Camera
  token: string
  info?: StreamInfo
  detection?: { analyses_per_s: number; paused?: boolean } // present when detection is running on this camera
  showDetections?: boolean
  showZones?: boolean
  onExpand?: () => void
  large?: boolean
  /** "stream": one continuous MJPEG connection (smoothest). "poll": fetch the newest frame a few
   * times a second. Use "poll" for grids: browsers allow only ~6 open connections per server, so
   * several MJPEG tiles would starve each other and every other request on the page. */
  mode?: 'stream' | 'poll'
  /** Poll mode only: stop fetching frames (e.g. while another camera is shown enlarged on top). */
  paused?: boolean
}

export default function LiveTile({
  camera, token, info, detection, showDetections = true, showZones = false, onExpand, large = false, mode = 'stream', paused = false,
}: Props) {
  const qc = useQueryClient()
  const { data: industry } = useIndustry()
  // The URL is fixed per connection: refreshing the token must not reconnect a working stream.
  const [src, setSrc] = useState(() => (mode === 'stream' ? streamUrl(camera.id, token) : undefined))
  const [hasFrame, setHasFrame] = useState(false)
  const [broken, setBroken] = useState(false)
  const attempt = useRef(0)
  const retryTimer = useRef<number | undefined>(undefined)
  const imgRef = useRef<HTMLImageElement>(null)

  // Poll mode: short requests for the newest frame; each shown as a blob URL, previous one freed.
  useEffect(() => {
    if (mode !== 'poll' || paused) return
    let stopped = false
    let timer: number | undefined
    let shown: string | undefined
    const tick = async () => {
      const started = performance.now()
      let delay = 1000 / POLL_FPS
      try {
        const t = latestMediaToken(qc) ?? token
        const res = await fetch(`/api/cameras/${camera.id}/frame?token=${encodeURIComponent(t)}`, { cache: 'no-store' })
        if (!res.ok) throw new Error(String(res.status))
        const url = URL.createObjectURL(await res.blob())
        if (stopped) return URL.revokeObjectURL(url)
        const previous = shown
        shown = url
        setSrc(url)
        setBroken(false)
        if (previous) window.setTimeout(() => URL.revokeObjectURL(previous), 1000) // after the swap has painted
        delay = Math.max(30, delay - (performance.now() - started))
      } catch {
        if (stopped) return
        setBroken(true)
        delay = RETRY_DELAY_MS
      }
      if (!stopped) timer = window.setTimeout(tick, delay)
    }
    tick()
    return () => {
      stopped = true
      window.clearTimeout(timer)
      if (shown) URL.revokeObjectURL(shown)
    }
  }, [mode, paused, camera.id, qc, token])

  useEffect(() => {
    const img = imgRef.current
    return () => {
      window.clearTimeout(retryTimer.current)
      // Browsers can keep an MJPEG connection open after the <img> is removed; clearing src aborts it
      // so the backend sees the viewer leave and can release the camera.
      if (img) img.src = ''
    }
  }, [])

  function reconnect() {
    window.clearTimeout(retryTimer.current)
    setBroken(false)
    if (mode === 'poll') return // the poll loop keeps retrying by itself
    attempt.current += 1
    setHasFrame(false)
    setSrc(streamUrl(camera.id, latestMediaToken(qc) ?? token, attempt.current))
  }

  function handleError() {
    if (mode === 'poll') return // handled by the poll loop
    setBroken(true)
    retryTimer.current = window.setTimeout(reconnect, RETRY_DELAY_MS)
  }

  const state = info?.state
  // While the backend is still connecting, a failed frame request just means "not yet": keep showing
  // "Connecting…" until it reports the error, so "Camera offline" always comes with its reason.
  const showError = state === 'error' || (broken && state !== 'connecting')
  const connecting = !showError && (!hasFrame || state === 'connecting')

  return (
    <figure
      className={`group relative overflow-hidden rounded-xl border bg-forest-950 ${
        state === 'live' && hasFrame ? 'border-gold-500/70' : showError ? 'border-red-400/50' : 'border-forest-600'
      }`}
    >
      <div className="relative aspect-video">
        <img
          ref={imgRef}
          src={src}
          alt={`Live view of ${camera.name}`}
          onLoad={() => setHasFrame(true)}
          onError={handleError}
          className={`h-full w-full object-contain transition-opacity ${hasFrame && !showError ? 'opacity-100' : 'opacity-0'}`}
        />

        {connecting && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 text-sm text-emerald-100/60">
            <LoaderCircle size={22} className="animate-spin text-lime-glow" />
            Connecting…
          </div>
        )}

        {showError && (
          <div role="alert" className="absolute inset-0 flex flex-col items-center justify-center gap-2 bg-forest-950/90 px-6 text-center">
            <WifiOff size={24} className="text-red-300" />
            <span className="text-sm font-medium text-red-200">Camera offline</span>
            {info?.error && <span className="line-clamp-2 text-xs text-red-200/70">{info.error}</span>}
            <button onClick={reconnect} className="mt-1 inline-flex items-center gap-1 rounded-md border border-forest-600 px-2 py-1 text-xs text-emerald-100/80 hover:border-gold-500 hover:text-white">
              <RefreshCw size={12} /> Retry now
            </button>
          </div>
        )}

        {showZones && hasFrame && !showError && info?.width && info.height && <ZonesOverlay cameraId={camera.id} width={info.width} height={info.height} />}
        {detection && showDetections && hasFrame && !showError && <DetectionOverlay cameraId={camera.id} analysesPerSecond={detection.analyses_per_s} />}

        {/* Top overlay: LIVE badge + fps + AI */}
        {info?.state === 'live' && hasFrame && !showError && (
          <div className="pointer-events-none absolute left-3 top-3 flex flex-wrap items-center gap-2">
            <span className="inline-flex items-center gap-1.5 rounded-md bg-red-600/90 px-2 py-0.5 text-xs font-bold tracking-wide text-white">
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-white" /> LIVE
            </span>
            <span className="rounded-md bg-black/60 px-2 py-0.5 text-xs tabular-nums text-emerald-50" aria-label="Frame rate">
              {info.fps.toFixed(0)} fps{info.width ? ` · ${info.width}×${info.height}` : ''}
            </span>
            {detection && (
              <span
                className={`inline-flex items-center gap-1 rounded-md border bg-black/60 px-2 py-0.5 text-xs ${detection.paused ? 'border-forest-600 text-emerald-100/60' : 'border-lime-glow/60 text-lime-glow'}`}
                aria-label="Detection rate"
              >
                <ScanFace size={12} /> {detection.paused ? 'AI paused' : `AI ${detection.analyses_per_s.toFixed(1)}/s`}
              </span>
            )}
          </div>
        )}

        {onExpand && (
          <button
            onClick={onExpand}
            className="absolute right-3 top-3 rounded-md bg-black/60 p-1.5 text-emerald-50 opacity-0 transition hover:text-lime-glow focus:opacity-100 group-hover:opacity-100"
            aria-label={`Expand ${camera.name}`}
          >
            <Maximize2 size={16} />
          </button>
        )}
      </div>

      <figcaption className={`flex items-center justify-between border-t border-forest-700 bg-forest-900 px-4 ${large ? 'py-3' : 'py-2.5'}`}>
        <div className="min-w-0">
          <div className="truncate text-sm font-medium text-white">{camera.name}</div>
          <div className="truncate text-xs text-emerald-100/50">
            {areaLabel(industry, camera.area)}
            {camera.location ? ` · ${camera.location}` : ''}
          </div>
        </div>
      </figcaption>
    </figure>
  )
}
