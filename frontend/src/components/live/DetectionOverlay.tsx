import { useLatestDetection, type CheckKey, type LatestDetection } from '../../api/detection'
import { missingLabel, useIndustry } from '../../api/industry'

const MIN_STALE_MS = 3000
const MAX_STALE_MS = 15000
const RED = '#f87171'
const LIME = '#b5f23d'
const GOLD = '#e8c547'
const AMBER = '#fbbf24'
const GREY = '#c4cbc5'

type Table = NonNullable<LatestDetection['tables']>[number]

/** Intersection over union of two [x0, y0, x1, y1] boxes. */
function overlap(a: number[], b: number[]) {
  const iw = Math.max(0, Math.min(a[2], b[2]) - Math.max(a[0], b[0]))
  const ih = Math.max(0, Math.min(a[3], b[3]) - Math.max(a[1], b[1]))
  const inter = iw * ih
  const union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
  return union > 0 ? inter / union : 0
}

const mmss = (s: number) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}`

/** A filled label whose bottom-left corner is at (x, y). */
function Label({ x, y, text, font, colour }: { x: number; y: number; text: string; font: number; colour: string }) {
  return (
    <g>
      <rect x={x} y={y - font - 4} width={text.length * font * 0.58 + 10} height={font + 6} fill={colour} rx={3} />
      <text x={x + 5} y={y - 3} fontSize={font} fontWeight={700} fill="#06120b" fontFamily="Inter, system-ui, sans-serif">
        {text}
      </text>
    </g>
  )
}

/** The table rule's progress, at the top of the table zone: nobody there + items left = timer running. */
function TableBadge({ table: t, x, y, font }: { table: Table; x: number; y: number; font: number }) {
  const text =
    t.state === 'occupied' ? `${t.name}: guests seated`
    : t.state === 'clear' ? `${t.name}: clear`
    : t.state === 'waiting' ? `${t.name}: not cleared ${mmss(t.waited_s)} / ${mmss(t.limit_s)}`
    : `${t.name}: NOT CLEARED ${mmss(t.waited_s)}`
  const colour = t.state === 'not_cleared' ? RED : t.state === 'waiting' ? AMBER : LIME
  const width = text.length * font * 0.58 + 10
  return (
    <g data-testid="detection-table" data-state={t.state}>
      <Label x={Math.max(0, x - width / 2)} y={Math.max(font + 6, y - 4)} text={text} font={font} colour={colour} />
    </g>
  )
}

/** Boxes drawn over the live video. The SVG uses the frame's own size as its viewBox and
 * "meet" scaling, which lines up exactly with the <img>'s object-contain.
 * Boxes are hidden once older than ~2.5 analysis intervals (a busy GPU analyses less often). */
export default function DetectionOverlay({ cameraId, analysesPerSecond }: { cameraId: number; analysesPerSecond: number }) {
  const { data } = useLatestDetection(cameraId, true)
  const { data: industry } = useIndustry()
  const staleMs = Math.min(MAX_STALE_MS, Math.max(MIN_STALE_MS, 2500 / Math.max(analysesPerSecond, 0.1)))
  if (!data || data.age_ms > staleMs) return null

  const stroke = Math.max(2, data.width / 320)
  const font = Math.max(12, data.width / 45)

  return (
    <svg
      className="pointer-events-none absolute inset-0 h-full w-full"
      viewBox={`0 0 ${data.width} ${data.height}`}
      preserveAspectRatio="xMidYMid meet"
      aria-label="Detections"
      role="img"
    >
      {data.objects?.map((o, i) => {
        const [x0, y0, x1, y1] = o.box
        return (
          <g key={`o${i}`} data-testid="detection-object">
            <rect x={x0} y={y0} width={x1 - x0} height={y1 - y0} fill="none" stroke={GOLD} strokeWidth={stroke * 0.75} rx={stroke} />
            <Label x={x0} y={y0 - 2} text={o.label} font={font * 0.8} colour={GOLD} />
          </g>
        )
      })}
      {data.tables?.map((t) => (
        <TableBadge key={t.zone_id} table={t} x={t.anchor[0] * data.width} y={t.anchor[1] * data.height} font={font} />
      ))}
      {data.counters?.map((c) => {
        const [lx, ly0, ly1] = c.line
        const x = lx * data.width
        const top = ly0 * data.height
        const text = `${c.kind.toUpperCase()} ${c.total} · ${c.per_minute}/min`
        const width = text.length * font * 0.58 + 10
        return (
          <g key={`count-${c.zone_id}`} data-testid="detection-counter" data-total={c.total}>
            {/* The counting line: gold while a bag is on it. */}
            <line x1={x} y1={top} x2={x} y2={ly1 * data.height} stroke={c.passing ? GOLD : LIME} strokeWidth={stroke * 1.5} strokeDasharray={`${stroke * 3} ${stroke * 2}`} />
            <Label x={Math.max(0, Math.min(x - width / 2, data.width - width))} y={Math.max(font + 6, top - 4)} text={text} font={font} colour={LIME} />
          </g>
        )
      })}
      {data.zone_states?.map((z) => {
        const text =
          z.state === 'problem' ? `${z.label.toUpperCase()} ${mmss(z.seconds)}` : z.state === 'clear' ? `${z.name}: clear` : `${z.name}: checking…`
        const colour = z.state === 'problem' ? RED : z.state === 'clear' ? LIME : AMBER
        const width = text.length * font * 0.58 + 10
        const x = Math.max(0, z.anchor[0] * data.width - width / 2)
        const y = Math.max(font + 6, z.anchor[1] * data.height - 4)
        return (
          <g key={`${z.rule}-${z.zone_id}`} data-testid="detection-zone-state" data-state={z.state}>
            <Label x={x} y={y} text={text} font={font} colour={colour} />
          </g>
        )
      })}
      {data.intrusions?.map((t, i) => {
        const [x0, y0, x1, y1] = t.box
        const pad = stroke * 3
        const below = y1 + pad + font + 6
        return (
          <g key={`in${i}`} data-testid="detection-intrusion">
            <rect x={x0 - pad} y={y0 - pad} width={x1 - x0 + 2 * pad} height={y1 - y0 + 2 * pad} fill="none" stroke={RED} strokeWidth={stroke * 2} strokeDasharray={`${stroke * 4} ${stroke * 2}`} rx={stroke * 2} />
            {/* Under the person, or inside the box's bottom when they reach the bottom of the picture. */}
            <Label x={x0 - pad} y={below <= data.height ? below : y1 - pad} text={`IN DANGER ZONE ${Math.floor(t.seconds)}s`} font={font} colour={RED} />
          </g>
        )
      })}
      {data.persons.map((p, i) => {
        const missing = (Object.entries(p.checks) as [CheckKey, { state: string }][]).filter(([, c]) => c.state === 'violation').map(([k]) => k)
        // Someone in a danger zone is not "OK", even with all their PPE: the red danger marker says it all.
        if (!missing.length && data.intrusions?.some((t) => overlap(t.box, p.box) > 0.7)) return null
        if (Object.keys(p.checks).length === 0) {
          // No worker checks on this camera (e.g. only counting or zone rules): a plain box, never "OK".
          const [bx0, by0, bx1, by1] = p.box
          return (
            <g key={i} data-testid="detection-person" data-violations="">
              <rect x={bx0} y={by0} width={bx1 - bx0} height={by1 - by0} fill="none" stroke={GREY} strokeWidth={stroke * 0.75} strokeDasharray={`${stroke * 2} ${stroke * 2}`} rx={stroke * 2} />
            </g>
          )
        }
        const colour = missing.length ? RED : LIME
        const [x0, y0, x1, y1] = p.box
        const labels = missing.length ? missing.map((k) => missingLabel(industry, k)) : ['OK']
        return (
          <g key={i} data-testid="detection-person" data-violations={missing.join(',')}>
            <rect x={x0} y={y0} width={x1 - x0} height={y1 - y0} fill="none" stroke={colour} strokeWidth={stroke} rx={stroke * 2} />
            {labels.map((text, j) => (
              <Label key={text} x={x0} y={y0 + (j + 1) * (font + 6) + 3} text={text} font={font} colour={colour} />
            ))}
          </g>
        )
      })}
    </svg>
  )
}
