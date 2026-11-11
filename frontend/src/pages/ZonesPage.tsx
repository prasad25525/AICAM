import { useQuery } from '@tanstack/react-query'
import { Camera as CameraIcon, Check, ImageOff, LoaderCircle, MousePointerClick, PenLine, Plus, RefreshCw, Trash2, Undo2, X } from 'lucide-react'
import { useEffect, useRef, useState, type FormEvent, type PointerEvent as ReactPointerEvent } from 'react'
import { fetchSnapshot, useCameras, type Camera } from '../api/cameras'
import { centroid, useCreateZone, useDeleteZone, useUpdateZone, useZones, type Point, type Zone, type ZoneType } from '../api/zones'
import { useIndustry, zoneTypeOf } from '../api/industry'
import { btnDanger, btnPrimary, btnSecondary, inputBase } from '../components/Modal'
import { apiErrorMessage } from '../lib/api'

const CLOSE_DISTANCE_PX = 14 // clicking this close to the first point closes the shape
const clamp = (v: number) => Math.min(1, Math.max(0, v))
const pct = (v: number) => `${v * 100}%`

type Mode = { kind: 'view' } | { kind: 'drawing'; points: Point[] } | { kind: 'naming'; points: Point[] }

function useBackground(camera: Camera | undefined) {
  return useQuery({
    queryKey: ['zone-background', camera?.id],
    queryFn: async () => {
      const url = await fetchSnapshot(camera!.id)
      const img = new Image()
      img.src = url
      await img.decode()
      return { url, width: img.naturalWidth, height: img.naturalHeight }
    },
    enabled: !!camera?.enabled,
    gcTime: 0,
    retry: false,
    refetchOnWindowFocus: false,
  })
}

function ZoneFields({ name, type, onName, onType }: { name: string; type: ZoneType; onName: (v: string) => void; onType: (v: ZoneType) => void }) {
  const { data: industry } = useIndustry()
  return (
    <>
      <label className="block">
        <span className="mb-1.5 block text-xs font-medium uppercase tracking-wider text-gold-300">Zone name</span>
        <input className={inputBase} value={name} onChange={(e) => onName(e.target.value)} placeholder={industry?.key === 'cement' ? 'e.g. Kiln area' : 'e.g. Hand-wash sink'} maxLength={100} required autoFocus />
      </label>
      <label className="block">
        <span className="mb-1.5 block text-xs font-medium uppercase tracking-wider text-gold-300">Zone type</span>
        <select className={inputBase} value={type} onChange={(e) => onType(e.target.value as ZoneType)}>
          {(industry?.zone_types ?? []).map((t) => (
            <option key={t.key} value={t.key}>{t.label}</option>
          ))}
        </select>
      </label>
    </>
  )
}

function ZoneEditor({ camera }: { camera: Camera }) {
  const zones = useZones(camera.id)
  const bg = useBackground(camera)
  const create = useCreateZone(camera.id)
  const update = useUpdateZone()
  const del = useDeleteZone()
  const { data: industry } = useIndustry()

  const [mode, setMode] = useState<Mode>({ kind: 'view' })
  const [hover, setHover] = useState<Point | null>(null)
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [draft, setDraft] = useState<{ polygon: Point[]; name: string; type: ZoneType } | null>(null)
  const [newName, setNewName] = useState('')
  // '' = not chosen yet: the industry's first zone type.
  const [chosenType, setNewType] = useState<ZoneType>('')
  const newType = chosenType || industry?.zone_types[0]?.key || 'other'
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [error, setError] = useState('')
  const boxRef = useRef<HTMLDivElement>(null)
  const dragIndex = useRef<number | null>(null)

  const selected = zones.data?.find((z) => z.id === selectedId) ?? null
  const width = bg.data?.width ?? camera.status?.width ?? 16
  const height = bg.data?.height ?? camera.status?.height ?? 9

  // Free the snapshot's memory when it is replaced.
  useEffect(() => () => {
    if (bg.data) URL.revokeObjectURL(bg.data.url)
  }, [bg.data])

  function select(zone: Zone | null) {
    setSelectedId(zone?.id ?? null)
    setDraft(zone ? { polygon: zone.polygon, name: zone.name, type: zone.zone_type } : null)
    setConfirmDelete(false)
    setError('')
  }

  function startDrawing() {
    select(null)
    setMode({ kind: 'drawing', points: [] })
  }

  function cancelDrawing() {
    setMode({ kind: 'view' })
    setHover(null)
    setError('')
  }

  function finishDrawing() {
    if (mode.kind === 'drawing' && mode.points.length >= 3) {
      setMode({ kind: 'naming', points: mode.points })
      setHover(null)
      setNewName('')
    }
  }

  // Keyboard: Enter finishes a shape, Escape cancels, Backspace removes the last point.
  useEffect(() => {
    if (mode.kind !== 'drawing') return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') cancelDrawing()
      if (e.key === 'Enter') finishDrawing()
      if (e.key === 'Backspace') setMode((m) => (m.kind === 'drawing' ? { ...m, points: m.points.slice(0, -1) } : m))
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  })

  function toPoint(e: { clientX: number; clientY: number }): Point {
    const r = boxRef.current!.getBoundingClientRect()
    return [clamp((e.clientX - r.left) / r.width), clamp((e.clientY - r.top) / r.height)]
  }

  function onPointerDown(e: ReactPointerEvent) {
    if (mode.kind !== 'drawing') {
      if (e.target === e.currentTarget || (e.target as Element).tagName === 'IMG' || (e.target as Element).tagName === 'svg') select(null)
      return
    }
    const p = toPoint(e)
    const first = mode.points[0]
    if (first && mode.points.length >= 3) {
      const r = boxRef.current!.getBoundingClientRect()
      const dist = Math.hypot((p[0] - first[0]) * r.width, (p[1] - first[1]) * r.height)
      if (dist <= CLOSE_DISTANCE_PX) return finishDrawing()
    }
    setMode({ kind: 'drawing', points: [...mode.points, p] })
  }

  function onPointerMove(e: ReactPointerEvent) {
    if (mode.kind === 'drawing') setHover(toPoint(e))
    if (dragIndex.current !== null && draft) {
      const p = toPoint(e)
      setDraft({ ...draft, polygon: draft.polygon.map((q, i) => (i === dragIndex.current ? p : q)) })
    }
  }

  async function saveNew(e: FormEvent) {
    e.preventDefault()
    if (mode.kind !== 'naming') return
    setError('')
    try {
      const zone = await create.mutateAsync({ name: newName.trim(), zone_type: newType, polygon: mode.points })
      setMode({ kind: 'view' })
      select(zone)
    } catch (err) {
      setError(apiErrorMessage(err))
    }
  }

  async function saveChanges(e: FormEvent) {
    e.preventDefault()
    if (!selected || !draft) return
    setError('')
    try {
      const zone = await update.mutateAsync({ id: selected.id, name: draft.name.trim(), zone_type: draft.type, polygon: draft.polygon })
      select(zone)
    } catch (err) {
      setError(apiErrorMessage(err))
    }
  }

  async function remove() {
    if (!selected) return
    await del.mutateAsync(selected.id)
    select(null)
  }

  const dirty =
    !!selected && !!draft &&
    (draft.name.trim() !== selected.name || draft.type !== selected.zone_type || JSON.stringify(draft.polygon) !== JSON.stringify(selected.polygon))

  // Selected zone is drawn from its draft so edits show immediately.
  const shapes = (zones.data ?? []).map((z) => ({ zone: z, polygon: z.id === selectedId && draft ? draft.polygon : z.polygon }))
  const drawingPoints = mode.kind === 'drawing' || mode.kind === 'naming' ? mode.points : []

  return (
    <div className="grid gap-5 xl:grid-cols-[1fr_320px]">
      <section className="space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          {mode.kind === 'view' && (
            <button onClick={startDrawing} className={btnPrimary}>
              <Plus size={16} /> Draw new zone
            </button>
          )}
          {mode.kind === 'drawing' && (
            <>
              <button onClick={finishDrawing} disabled={mode.points.length < 3} className={btnPrimary}>
                <Check size={16} /> Finish shape
              </button>
              <button onClick={() => setMode({ ...mode, points: mode.points.slice(0, -1) })} disabled={!mode.points.length} className={btnSecondary}>
                <Undo2 size={16} /> Undo point
              </button>
              <button onClick={cancelDrawing} className={btnSecondary}>
                <X size={16} /> Cancel
              </button>
            </>
          )}
          {camera.enabled && (
            <button onClick={() => bg.refetch()} disabled={bg.isFetching} className={`${btnSecondary} ml-auto`}>
              <RefreshCw size={16} className={bg.isFetching ? 'animate-spin' : ''} /> Refresh picture
            </button>
          )}
        </div>

        <p className="flex items-center gap-2 text-xs text-emerald-100/60" role="status">
          <MousePointerClick size={14} className="text-gold-400" />
          {mode.kind === 'drawing'
            ? mode.points.length < 3
              ? `Click on the picture to add corner points (${mode.points.length} so far, at least 3).`
              : 'Keep adding points, then click the first point, press Enter, or Finish shape.'
            : mode.kind === 'naming'
              ? 'Name the zone and pick its type.'
              : 'Click a zone to edit it. Drag its corner handles to reshape.'}
        </p>

        <div
          ref={boxRef}
          data-testid="zone-canvas"
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={() => (dragIndex.current = null)}
          onPointerLeave={() => setHover(null)}
          className={`relative w-full touch-none select-none overflow-hidden rounded-lg border border-gold-500/60 bg-forest-950 ${mode.kind === 'drawing' ? 'cursor-crosshair' : ''}`}
          style={{ aspectRatio: `${width} / ${height}` }}
        >
          {bg.data ? (
            <img src={bg.data.url} alt={`Current view of ${camera.name}`} draggable={false} className="absolute inset-0 h-full w-full" />
          ) : (
            <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 text-sm text-emerald-100/50">
              {bg.isFetching ? <LoaderCircle size={24} className="animate-spin text-lime-glow" /> : <ImageOff size={24} />}
              {bg.isFetching ? 'Getting a picture from the camera…' : camera.enabled ? 'Picture unavailable — you can still draw zones.' : 'Camera disabled — enable it to see its picture.'}
            </div>
          )}

          <svg className="absolute inset-0 h-full w-full" viewBox="0 0 1 1" preserveAspectRatio="none">
            {shapes.map(({ zone, polygon }) => {
              const c = zoneTypeOf(industry, zone.zone_type).colour
              const active = zone.id === selectedId
              return (
                <polygon
                  key={zone.id}
                  data-testid={`zone-shape-${zone.name}`}
                  points={polygon.map((p) => p.join(',')).join(' ')}
                  fill={c}
                  fillOpacity={active ? 0.35 : 0.2}
                  stroke={c}
                  strokeWidth={active ? 3 : 2}
                  vectorEffect="non-scaling-stroke"
                  className={mode.kind === 'view' ? 'cursor-pointer' : 'pointer-events-none'}
                  onPointerDown={(e) => {
                    if (mode.kind !== 'view') return
                    e.stopPropagation()
                    select(zone)
                  }}
                />
              )
            })}
            {drawingPoints.length > 0 && (
              <polyline
                points={[...drawingPoints, ...(hover && mode.kind === 'drawing' ? [hover] : mode.kind === 'naming' ? [drawingPoints[0]] : [])]
                  .map((p) => p.join(','))
                  .join(' ')}
                fill={mode.kind === 'naming' ? '#b5f23d' : 'none'}
                fillOpacity={0.2}
                stroke="#b5f23d"
                strokeWidth={2}
                strokeDasharray={mode.kind === 'drawing' ? '6 4' : undefined}
                vectorEffect="non-scaling-stroke"
                className="pointer-events-none"
              />
            )}
          </svg>

          {/* Labels (HTML, so text isn't stretched by the SVG) */}
          {shapes.map(({ zone, polygon }) => {
            const [cx, cy] = centroid(polygon)
            return (
              <span
                key={zone.id}
                className="pointer-events-none absolute -translate-x-1/2 -translate-y-1/2 whitespace-nowrap rounded px-1.5 py-0.5 text-xs font-semibold text-white shadow"
                style={{ left: pct(cx), top: pct(cy), background: zoneTypeOf(industry, zone.zone_type).colour }}
              >
                {zone.name}
              </span>
            )
          })}

          {/* Corner handles for the selected zone */}
          {mode.kind === 'view' &&
            draft?.polygon.map((p, i) => (
              <span
                key={i}
                role="button"
                aria-label={`Corner ${i + 1}`}
                onPointerDown={(e) => {
                  e.stopPropagation()
                  boxRef.current?.setPointerCapture(e.pointerId)
                  dragIndex.current = i
                }}
                className="absolute h-3.5 w-3.5 -translate-x-1/2 -translate-y-1/2 cursor-move rounded-full border-2 border-forest-950 bg-lime-glow shadow"
                style={{ left: pct(p[0]), top: pct(p[1]) }}
              />
            ))}

          {/* Points placed while drawing; the first is larger because clicking it closes the shape */}
          {drawingPoints.map((p, i) => (
            <span
              key={i}
              className={`pointer-events-none absolute -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-forest-950 bg-lime-glow ${i === 0 ? 'h-4 w-4' : 'h-2.5 w-2.5'}`}
              style={{ left: pct(p[0]), top: pct(p[1]) }}
            />
          ))}
        </div>
      </section>

      <aside className="space-y-4">
        {mode.kind === 'naming' && (
          <form onSubmit={saveNew} className="space-y-4 rounded-xl border border-lime-glow/60 bg-forest-900 p-4" aria-label="New zone">
            <h3 className="font-semibold text-lime-glow">New zone · {mode.points.length} points</h3>
            <ZoneFields name={newName} type={newType} onName={setNewName} onType={setNewType} />
            {error && <p role="alert" className="text-sm text-red-200">{error}</p>}
            <div className="flex gap-2">
              <button type="submit" disabled={create.isPending} className={btnPrimary}>
                {create.isPending && <LoaderCircle size={14} className="animate-spin" />} Save zone
              </button>
              <button type="button" onClick={cancelDrawing} className={btnSecondary}>Discard</button>
            </div>
          </form>
        )}

        {selected && draft && mode.kind === 'view' && (
          <form onSubmit={saveChanges} className="space-y-4 rounded-xl border border-gold-500 bg-forest-900 p-4" aria-label="Edit zone">
            <h3 className="flex items-center gap-2 font-semibold text-gold-300">
              <PenLine size={16} /> Edit zone
            </h3>
            <ZoneFields name={draft.name} type={draft.type} onName={(name) => setDraft({ ...draft, name })} onType={(type) => setDraft({ ...draft, type })} />
            <p className="text-xs text-emerald-100/50">{draft.polygon.length} corners — drag the handles on the picture to reshape.</p>
            {error && <p role="alert" className="text-sm text-red-200">{error}</p>}
            <div className="flex flex-wrap gap-2">
              <button type="submit" disabled={!dirty || update.isPending} className={btnPrimary}>
                {update.isPending && <LoaderCircle size={14} className="animate-spin" />} Save changes
              </button>
              <button type="button" onClick={() => select(selected)} disabled={!dirty} className={btnSecondary}>Undo</button>
            </div>
            <div className="border-t border-forest-700 pt-3">
              {confirmDelete ? (
                <div className="flex flex-wrap items-center gap-2 text-sm text-red-200">
                  Delete "{selected.name}"?
                  <button type="button" onClick={remove} disabled={del.isPending} className={`${btnDanger} py-1.5`}>
                    <Trash2 size={14} /> Delete
                  </button>
                  <button type="button" onClick={() => setConfirmDelete(false)} className={`${btnSecondary} py-1.5`}>Cancel</button>
                </div>
              ) : (
                <button type="button" onClick={() => setConfirmDelete(true)} className={`${btnDanger} py-1.5`}>
                  <Trash2 size={14} /> Delete zone
                </button>
              )}
            </div>
          </form>
        )}

        <section className="rounded-xl border border-gold-500/60 bg-forest-900">
          <h3 className="border-b border-forest-700 px-4 py-2.5 text-sm font-semibold text-gold-300">Zones on {camera.name}</h3>
          {zones.data?.length === 0 ? (
            <p className="px-4 py-6 text-center text-sm text-emerald-100/50">No zones yet. Click “Draw new zone”.</p>
          ) : (
            <ul className="p-2" aria-label="Zones">
              {zones.data?.map((z) => (
                <li key={z.id}>
                  <button
                    onClick={() => {
                      if (mode.kind !== 'view') cancelDrawing()
                      select(z)
                    }}
                    className={`flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm ${z.id === selectedId ? 'bg-forest-800 text-white' : 'text-emerald-100/80 hover:bg-forest-800/60'}`}
                  >
                    <span className="h-3 w-3 shrink-0 rounded-sm" style={{ background: zoneTypeOf(industry, z.zone_type).colour }} />
                    <span className="flex-1 truncate">{z.name}</span>
                    <span className="text-xs text-emerald-100/50">{zoneTypeOf(industry, z.zone_type).label}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>
      </aside>
    </div>
  )
}

export default function ZonesPage() {
  const cameras = useCameras()
  const [cameraId, setCameraId] = useState<number | null>(null)
  const current = cameras.data?.find((c) => c.id === cameraId) ?? cameras.data?.find((c) => c.enabled) ?? cameras.data?.[0]

  if (cameras.isLoading) return <p className="text-sm text-emerald-100/60">Loading cameras…</p>
  if (!current)
    return (
      <div className="mx-auto flex max-w-xl flex-col items-center rounded-xl border border-gold-500/60 bg-forest-900 px-6 py-16 text-center">
        <CameraIcon size={32} className="mb-3 text-lime-glow" />
        <h2 className="font-semibold text-white">No cameras yet</h2>
        <p className="mt-1 text-sm text-emerald-100/60">Add a camera first, then draw its zones here.</p>
      </div>
    )

  return (
    <div className="mx-auto max-w-7xl space-y-5">
      <div className="flex flex-wrap items-center gap-3">
        <label className="flex items-center gap-2 text-sm text-emerald-100/70">
          Camera
          <select aria-label="Camera" className={`${inputBase} w-64`} value={current.id} onChange={(e) => setCameraId(Number(e.target.value))}>
            {cameras.data?.map((c) => (
              <option key={c.id} value={c.id}>{c.name}{c.enabled ? '' : ' (disabled)'}</option>
            ))}
          </select>
        </label>
        <p className="text-xs text-emerald-100/50">Zones mark areas like the hand-wash sink or raw prep. Alerts are tagged with the zone the person is standing in.</p>
      </div>
      {/* Keyed by camera so switching resets the editor. */}
      <ZoneEditor key={current.id} camera={current} />
    </div>
  )
}
