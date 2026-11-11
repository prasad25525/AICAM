import { AlertTriangle, ArrowRight, Ban, CircleCheck, CircleX, Droplets, Hand, HardHat, Mountain, Package, ScanFace, Shirt, Timer, Users, UtensilsCrossed, Wind } from 'lucide-react'
import type { EventItem, Severity } from '../../api/events'

type Icon = typeof Hand

/** What each rule expects, and the item that was missing (for PPE). */
const RULES: Record<string, { icon: Icon; rule: string; item?: string }> = {
  no_hair_cover: { icon: HardHat, rule: 'Hair must be covered in the kitchen', item: 'Hair cap / hairnet' },
  no_mask: { icon: ScanFace, rule: 'A face mask must be worn while preparing food', item: 'Face mask' },
  no_gloves: { icon: Hand, rule: 'Gloves must be worn when handling food', item: 'Gloves' },
  no_apron: { icon: Shirt, rule: 'An apron must be worn in the kitchen', item: 'Apron' },
  handwash_short: { icon: Droplets, rule: 'Hands must be washed long enough' },
  handwash_skipped: { icon: Droplets, rule: 'Hands must be washed before food prep' },
  table_not_cleared: { icon: UtensilsCrossed, rule: 'Tables must be cleared soon after guests leave' },
  // Cement plant
  no_helmet: { icon: HardHat, rule: 'A safety helmet must be worn in the plant', item: 'Safety helmet' },
  no_vest: { icon: Shirt, rule: 'A high-visibility vest must be worn in the plant', item: 'Safety vest' },
  restricted_area: { icon: Ban, rule: 'No entry into restricted or danger areas' },
  conveyor_spillage: { icon: Mountain, rule: 'Conveyor belts must run without spilling material' },
  damaged_bag: { icon: Package, rule: 'Damaged bags must be removed from the line' },
  dust_visible: { icon: Wind, rule: 'Dust emissions must stay controlled' },
}

const TONE: Record<Severity, { box: string; icon: string; text: string; bar: string }> = {
  critical: { box: 'border-red-400/60 bg-red-500/10', icon: 'bg-red-500/20 text-red-300', text: 'text-red-200', bar: 'bg-red-500' },
  warning: { box: 'border-amber-400/60 bg-amber-500/10', icon: 'bg-amber-500/20 text-amber-300', text: 'text-amber-200', bar: 'bg-amber-400' },
  info: { box: 'border-sky-400/60 bg-sky-500/10', icon: 'bg-sky-500/20 text-sky-300', text: 'text-sky-200', bar: 'bg-sky-400' },
}

/** "(needs 20s)" in older hand-wash messages, before the limit was stored with the event. */
const neededFromMessage = (msg: string) => Number(/needs (\d+(?:\.\d+)?)s/.exec(msg)?.[1]) || undefined

/** The violation made visual: which rule, what was missing, and measured value vs the limit. */
export default function ViolationSummary({ event }: { event: EventItem }) {
  const meta = RULES[event.event_type] ?? { icon: AlertTriangle, rule: event.message }
  const tone = TONE[event.severity]
  const ev = event.evidence ?? {}
  const Icon = meta.icon

  return (
    <section aria-label="Violation" className={`rounded-lg border-l-4 border ${tone.box} p-3`}>
      <div className="flex items-start gap-3">
        <span className={`grid size-10 shrink-0 place-items-center rounded-full ${tone.icon}`}>
          <Icon size={20} />
        </span>
        <div className="min-w-0">
          <p className={`text-[11px] font-semibold uppercase tracking-wider ${tone.text}`}>Rule broken</p>
          <p className="text-base font-semibold text-white">{event.type_label}</p>
          <p className="text-xs text-emerald-100/70">{meta.rule}</p>
        </div>
      </div>

      <div className="mt-3 space-y-2.5">
        {meta.item && <MissingItem item={meta.item} tone={tone.text} />}
        {event.event_type === 'handwash_short' && ev.wash_seconds !== undefined && (
          <Gauge
            label="Hand wash time"
            value={ev.wash_seconds}
            limit={ev.handwash_min_s ?? neededFromMessage(event.message) ?? 20}
            unit="s"
            barClass={tone.bar}
            textClass={tone.text}
            verdict={(v, l) => `${Math.round(l - v)}s too short`}
            limitLabel="required"
          />
        )}
        {event.event_type === 'handwash_skipped' && <SkippedSteps zone={event.zone_name} tone={tone.text} />}
        {event.event_type === 'table_not_cleared' && ev.waited_min !== undefined && ev.table_clear_min !== undefined && (
          <Gauge
            label="Left uncleared"
            value={ev.waited_min}
            limit={ev.table_clear_min}
            unit=" min"
            over
            barClass={tone.bar}
            textClass={tone.text}
            verdict={(_, l) => `over the ${l} min limit`}
            limitLabel="limit"
          />
        )}
        {event.event_type === 'table_not_cleared' && !!ev.items?.length && (
          <div className="flex flex-wrap items-center gap-1.5 text-xs">
            <span className="text-emerald-100/70">Still on the table:</span>
            {ev.items.map((i) => (
              <span key={i} className={`rounded-md border border-current/40 px-1.5 py-0.5 capitalize ${tone.text}`}>{i}</span>
            ))}
          </div>
        )}
        <Facts event={event} />
      </div>
    </section>
  )
}

function MissingItem({ item, tone }: { item: string; tone: string }) {
  return (
    <div className="flex items-center gap-2 text-sm">
      <span className="text-emerald-100/70">Missing:</span>
      <span className={`inline-flex items-center gap-1 rounded-md border border-current/50 px-2 py-0.5 font-medium ${tone}`}>
        <CircleX size={14} /> <span className="line-through decoration-2">{item}</span>
      </span>
    </div>
  )
}

/** Measured value against the limit: a bar with a marker at the limit. `over` = exceeding the limit is the problem. */
function Gauge({
  label, value, limit, unit, over = false, barClass, textClass, verdict, limitLabel,
}: {
  label: string
  value: number
  limit: number
  unit: string
  over?: boolean
  barClass: string
  textClass: string
  verdict: (value: number, limit: number) => string
  limitLabel: string
}) {
  // Scale so the limit sits at a fixed point and an overrun still fits.
  const scale = Math.max(value, limit) * (over ? 1.15 : 1)
  const pct = (n: number) => `${Math.min(100, (n / scale) * 100)}%`
  const fmtN = (n: number) => (Number.isInteger(n) ? n : n.toFixed(1))
  return (
    <div role="meter" aria-label={label} aria-valuenow={value} aria-valuemin={0} aria-valuemax={scale}>
      <div className="mb-1 flex items-baseline justify-between text-xs">
        <span className="text-emerald-100/70">{label}</span>
        <span>
          <span className={`text-sm font-semibold ${textClass}`}>{fmtN(value)}{unit}</span>
          <span className="text-emerald-100/60"> / {fmtN(limit)}{unit} {limitLabel}</span>
        </span>
      </div>
      <div className="relative h-2.5 rounded-full bg-forest-950 ring-1 ring-forest-600">
        <div className={`h-full rounded-full ${barClass}`} style={{ width: pct(value) }} />
        <div className="absolute -top-1 -bottom-1 w-0.5 bg-lime-glow" style={{ left: pct(limit) }} title={`${limitLabel}: ${fmtN(limit)}${unit}`} />
      </div>
      <p className={`mt-1 text-xs font-medium ${textClass}`}>{verdict(value, limit)}</p>
    </div>
  )
}

function SkippedSteps({ zone, tone }: { zone: string | null; tone: string }) {
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className={`inline-flex items-center gap-1 rounded-md border border-current/50 px-2 py-1 ${tone}`}>
        <CircleX size={14} /> Hand sink skipped
      </span>
      <ArrowRight size={14} className="text-emerald-100/50" />
      <span className="inline-flex items-center gap-1 rounded-md border border-forest-600 px-2 py-1 text-emerald-50">
        <CircleCheck size={14} className="text-emerald-100/60" /> Entered {zone ?? 'prep area'}
      </span>
    </div>
  )
}

function Facts({ event }: { event: EventItem }) {
  const ev = event.evidence ?? {}
  const facts: { icon: Icon; text: string }[] = []
  if (ev.persons_in_violation !== undefined && ev.persons_in_view !== undefined)
    facts.push({ icon: Users, text: `${ev.persons_in_violation} of ${ev.persons_in_view} ${ev.persons_in_view === 1 ? 'person' : 'people'} in view` })
  if (ev.min_duration_s !== undefined) facts.push({ icon: Timer, text: `Seen for ${ev.min_duration_s}s or more` })
  if (ev.seconds_inside !== undefined)
    facts.push({ icon: Timer, text: `Inside ${event.zone_name ?? 'the area'} for ${Math.round(ev.seconds_inside)}s when alerted` })
  if (ev.seconds_seen !== undefined)
    facts.push({ icon: Timer, text: `Visible on ${event.zone_name ?? 'the zone'} for ${Math.round(ev.seconds_seen)}s when alerted` })
  if (!facts.length) return null
  return (
    <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-emerald-100/70">
      {facts.map(({ icon: I, text }) => (
        <span key={text} className="inline-flex items-center gap-1"><I size={13} /> {text}</span>
      ))}
    </div>
  )
}
