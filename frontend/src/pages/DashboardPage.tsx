import { format, isToday } from 'date-fns'
import { AlertTriangle, Camera, CircleDashed, CircleOff, Package, ShieldCheck, TrendingDown, TrendingUp, Wifi, WifiOff, type LucideIcon } from 'lucide-react'
import type { ReactNode } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { useDashboard, type DashboardSummary } from '../api/dashboard'
import EventStatusBadge from '../components/events/EventStatusBadge'
import SeverityBadge from '../components/SeverityBadge'
import { useCountsToday } from '../api/counts'
import { useIndustry } from '../api/industry'
import { apiErrorMessage } from '../lib/api'

const LIME = '#b5f23d'
const AXIS = 'rgba(232,243,234,0.55)'
const GRID = 'rgba(232,243,234,0.08)'
const MIN_HOURS_SHOWN = 8

function Panel({ title, action, children, className = '' }: { title: string; action?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={`rounded-xl border border-gold-500/60 bg-forest-900 ${className}`}>
      <div className="flex items-center justify-between border-b border-forest-700 px-5 py-3">
        <h2 className="text-sm font-semibold text-gold-300">{title}</h2>
        {action}
      </div>
      <div className="p-5">{children}</div>
    </section>
  )
}

function StatTile({ label, value, sub, icon: Icon, accent = false, title, to }: {
  label: string
  value: ReactNode
  sub: ReactNode
  icon: LucideIcon
  accent?: boolean
  title?: string
  to?: string
}) {
  const body = (
    <>
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium uppercase tracking-wider text-emerald-100/60">{label}</span>
        <Icon size={18} className="text-gold-400" />
      </div>
      <div className="mt-2 text-3xl font-semibold tabular-nums text-white">{value}</div>
      <div className="mt-1 text-xs text-emerald-100/60">{sub}</div>
    </>
  )
  const className = `block rounded-xl border bg-forest-900 p-5 ${accent ? 'border-lime-glow/70 shadow-[0_0_24px_rgba(181,242,61,0.10)]' : 'border-gold-500/60'} ${to ? 'transition hover:border-lime-glow' : ''}`
  return to ? (
    <Link to={to} className={className} title={title} aria-label={label}>{body}</Link>
  ) : (
    <div className={className} title={title} role="group" aria-label={label}>{body}</div>
  )
}

/** "+3 vs same time yesterday", coloured by whether the change is good. */
function Delta({ diff, higherIsBetter, unit = '' }: { diff: number; higherIsBetter: boolean; unit?: string }) {
  if (diff === 0) return <span>Same as this time yesterday</span>
  const good = diff > 0 === higherIsBetter
  const Icon = diff > 0 ? TrendingUp : TrendingDown
  return (
    <span className={`inline-flex items-center gap-1 ${good ? 'text-lime-glow' : 'text-red-300'}`}>
      <Icon size={12} /> {diff > 0 ? '+' : ''}{diff}{unit} vs this time yesterday
    </span>
  )
}

const CAMERA_STATE: Record<DashboardSummary['cameras'][number]['state'], { label: string; icon: LucideIcon; className: string }> = {
  online: { label: 'Online', icon: Wifi, className: 'text-lime-glow' },
  offline: { label: 'Offline', icon: WifiOff, className: 'text-red-300' },
  unknown: { label: 'Not checked', icon: CircleDashed, className: 'text-emerald-100/50' },
  disabled: { label: 'Disabled', icon: CircleOff, className: 'text-emerald-100/40' },
}

function scoreColor(score: number) {
  if (score >= 85) return 'text-lime-glow'
  if (score >= 60) return 'text-gold-300'
  return 'text-red-300'
}

export default function DashboardPage() {
  const { data: d, isLoading, error } = useDashboard()
  const { data: industry } = useIndustry()
  // Industries that count things (e.g. cement bags) get a production tile.
  const countKind = industry?.zone_rules.find((r) => r.counts)?.counts ?? undefined
  const { data: counted } = useCountsToday(countKind)
  const navigate = useNavigate()

  if (isLoading) return <p className="text-sm text-emerald-100/60">Loading dashboard…</p>
  if (error || !d) return <p className="rounded-lg border border-red-400/40 bg-red-500/10 px-4 py-3 text-sm text-red-200">{apiErrorMessage(error)}</p>

  const hours = d.by_hour
    .slice(0, Math.max(d.current_hour + 1, MIN_HOURS_SHOWN))
    .map((h) => ({ ...h, label: `${String(h.hour).padStart(2, '0')}:00` }))
  const maxType = Math.max(1, ...d.by_type.map((t) => t.count))
  const notChecked = d.cameras.filter((c) => c.state === 'unknown').length

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      {/* KPIs */}
      <div className={`grid grid-cols-1 gap-4 sm:grid-cols-2 ${countKind ? 'xl:grid-cols-5' : 'xl:grid-cols-4'}`}>
        <StatTile
          accent
          label={industry?.score_label ?? 'Score'}
          icon={ShieldCheck}
          title={`How it's calculated: ${d.score_formula}`}
          value={<span className={scoreColor(d.hygiene_score)}>{d.hygiene_score}<span className="text-lg text-emerald-100/50">/100</span></span>}
          sub={<Delta diff={d.hygiene_score - d.hygiene_score_yesterday} higherIsBetter unit=" pts" />}
        />
        <StatTile
          label="Open alerts"
          icon={AlertTriangle}
          to="/events"
          value={d.open_alerts}
          sub={d.critical_open ? <span className="text-red-300">{d.critical_open} critical</span> : 'None critical'}
        />
        <StatTile
          label="Violations today"
          icon={TrendingDown}
          value={d.violations_today}
          sub={<Delta diff={d.violations_today - d.violations_yesterday} higherIsBetter={false} />}
        />
        <StatTile
          label="Cameras online"
          icon={Camera}
          to="/cameras"
          value={<>{d.cameras_online}<span className="text-lg text-emerald-100/50">/{d.cameras_enabled}</span></>}
          sub={[d.cameras_offline && `${d.cameras_offline} offline`, notChecked && `${notChecked} not checked`].filter(Boolean).join(' · ') || 'All reporting'}
        />
        {countKind && (
          <StatTile
            label={`${countKind[0].toUpperCase()}${countKind.slice(1)} counted today`}
            icon={Package}
            value={counted?.today.toLocaleString() ?? '…'}
            sub={counted ? <Delta diff={counted.today - counted.yesterday_same_time} higherIsBetter /> : ' '}
          />
        )}
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
        <Panel title="Violations by hour (today)" className="xl:col-span-2">
          <div className="h-64" role="img" aria-label={`Bar chart of violations per hour today; ${d.violations_today} in total`}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={hours} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
                <CartesianGrid vertical={false} stroke={GRID} />
                <XAxis dataKey="label" tick={{ fill: AXIS, fontSize: 11 }} tickLine={false} axisLine={{ stroke: GRID }} interval="preserveStartEnd" />
                <YAxis allowDecimals={false} tick={{ fill: AXIS, fontSize: 11 }} tickLine={false} axisLine={false} />
                <Tooltip
                  cursor={{ fill: 'rgba(181,242,61,0.08)' }}
                  content={({ active, payload, label }) =>
                    active && payload?.length ? (
                      <div className="rounded-lg border border-gold-500 bg-forest-950 px-3 py-2 text-xs shadow-lg">
                        <div className="text-emerald-100/60">{label}</div>
                        <div className="font-semibold text-white">{payload[0].value} violation{payload[0].value === 1 ? '' : 's'}</div>
                      </div>
                    ) : null
                  }
                />
                <Bar dataKey="count" fill={LIME} radius={[4, 4, 0, 0]} maxBarSize={28} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Panel>

        <Panel title="Violations by type (today)">
          {d.by_type.length === 0 ? (
            <p className="py-10 text-center text-sm text-emerald-100/50">No violations today.</p>
          ) : (
            <ul className="space-y-3.5" aria-label="Violations by type">
              {d.by_type.slice(0, 8).map((t) => (
                <li key={t.event_type} title={`${t.label}: ${t.count}`}>
                  <div className="mb-1 flex justify-between text-sm">
                    <span className="text-emerald-50">{t.label}</span>
                    <span className="tabular-nums text-emerald-100/70">{t.count}</span>
                  </div>
                  <div className="h-2 rounded-full bg-forest-800">
                    <div className="h-2 rounded-full bg-lime-glow" style={{ width: `${(t.count / maxType) * 100}%` }} />
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Panel>
      </div>

      {/* Alerts + cameras */}
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
        <Panel
          title="Recent alerts"
          className="xl:col-span-2"
          action={<Link to="/events" className="text-xs text-gold-300 hover:text-lime-glow">View all</Link>}
        >
          {d.recent.length === 0 ? (
            <p className="py-10 text-center text-sm text-emerald-100/50">No alerts yet.</p>
          ) : (
            <div className="-mx-5 -my-5 overflow-x-auto">
              <table className="w-full min-w-[640px] text-left text-sm" aria-label="Recent alerts">
                <thead className="text-xs uppercase tracking-wider text-emerald-100/50">
                  <tr className="border-b border-forest-700">
                    <th className="px-5 py-3 font-medium">Time</th>
                    <th className="px-5 py-3 font-medium">Alert</th>
                    <th className="px-5 py-3 font-medium">Camera</th>
                    <th className="px-5 py-3 font-medium">Severity</th>
                    <th className="px-5 py-3 font-medium">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {d.recent.map((a) => {
                    const when = new Date(a.occurred_at)
                    return (
                      <tr key={a.id} onClick={() => navigate('/events')} className="cursor-pointer border-b border-forest-800 last:border-0 hover:bg-forest-800/50">
                        <td className="whitespace-nowrap px-5 py-3 tabular-nums text-emerald-100/70">{format(when, isToday(when) ? 'HH:mm' : 'd MMM HH:mm')}</td>
                        <td className="px-5 py-3 text-white">
                          {a.type_label}
                          {a.simulated && <span className="ml-2 rounded border border-sky-400/40 px-1.5 text-[10px] uppercase tracking-wide text-sky-200">Test</span>}
                        </td>
                        <td className="px-5 py-3 text-emerald-100/70">{a.camera_name ?? '—'}</td>
                        <td className="px-5 py-3"><SeverityBadge severity={a.severity} /></td>
                        <td className="px-5 py-3"><EventStatusBadge status={a.status} /></td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </Panel>

        <Panel title="Camera status" action={<Link to="/cameras" className="text-xs text-gold-300 hover:text-lime-glow">Manage</Link>}>
          {d.cameras.length === 0 ? (
            <p className="py-10 text-center text-sm text-emerald-100/50">No cameras added.</p>
          ) : (
            <ul className="space-y-2" aria-label="Camera status">
              {d.cameras.map((c) => {
                const s = CAMERA_STATE[c.state]
                return (
                  <li key={c.id} className="flex items-center justify-between rounded-lg border border-forest-700 px-3 py-2 text-sm">
                    <span className="flex min-w-0 items-center gap-2 text-emerald-50">
                      <Camera size={14} className="shrink-0 text-gold-400" />
                      <span className="truncate">{c.name}</span>
                    </span>
                    <span className={`flex shrink-0 items-center gap-1.5 text-xs ${s.className}`}>
                      <s.icon size={12} /> {s.label}
                    </span>
                  </li>
                )
              })}
            </ul>
          )}
        </Panel>
      </div>
    </div>
  )
}
