import { format, parseISO, startOfMonth, subDays } from 'date-fns'
import { CalendarRange, Download, LoaderCircle, ShieldCheck, Timer, TrendingDown, TriangleAlert, type LucideIcon } from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { useIndustry } from '../api/industry'
import { downloadCsv, useReport, type ReportSummary } from '../api/reports'
import { btnSecondary, inputBase } from '../components/Modal'
import { apiErrorMessage } from '../lib/api'

const LIME = '#b5f23d'
const AXIS = 'rgba(232,243,234,0.55)'
const GRID = 'rgba(232,243,234,0.08)'
const ymd = (d: Date) => format(d, 'yyyy-MM-dd')

type Preset = '7d' | '30d' | 'month' | 'custom'
const PRESETS: { id: Preset; label: string }[] = [
  { id: '7d', label: 'Last 7 days' },
  { id: '30d', label: 'Last 30 days' },
  { id: 'month', label: 'This month' },
  { id: 'custom', label: 'Custom' },
]

function presetRange(p: Exclude<Preset, 'custom'>): [string, string] {
  const today = new Date()
  if (p === '7d') return [ymd(subDays(today, 6)), ymd(today)]
  if (p === '30d') return [ymd(subDays(today, 29)), ymd(today)]
  return [ymd(startOfMonth(today)), ymd(today)]
}

function Panel({ title, children, className = '' }: { title: string; children: ReactNode; className?: string }) {
  return (
    <section className={`rounded-xl border border-gold-500/60 bg-forest-900 ${className}`} aria-label={title}>
      <h2 className="border-b border-forest-700 px-5 py-3 text-sm font-semibold text-gold-300">{title}</h2>
      <div className="p-5">{children}</div>
    </section>
  )
}

function Tile({ label, value, sub, icon: Icon, title }: { label: string; value: ReactNode; sub?: ReactNode; icon: LucideIcon; title?: string }) {
  return (
    <div className="rounded-xl border border-gold-500/60 bg-forest-900 p-5" role="group" aria-label={label} title={title}>
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium uppercase tracking-wider text-emerald-100/60">{label}</span>
        <Icon size={18} className="text-gold-400" />
      </div>
      <div className="mt-2 text-3xl font-semibold tabular-nums text-white">{value}</div>
      {sub && <div className="mt-1 text-xs text-emerald-100/60">{sub}</div>}
    </div>
  )
}

function ChartTooltip({ active, payload, label, render }: { active?: boolean; payload?: readonly { payload?: unknown }[]; label?: ReactNode; render: (row: never) => ReactNode }) {
  if (!active || !payload?.length || !payload[0].payload) return null
  return (
    <div className="rounded-lg border border-gold-500 bg-forest-950 px-3 py-2 text-xs shadow-lg">
      <div className="text-emerald-100/60">{label}</div>
      {render(payload[0].payload as never)}
    </div>
  )
}

function BarList({ rows, empty, label }: { rows: { name: string; count: number }[]; empty: string; label: string }) {
  const max = Math.max(1, ...rows.map((r) => r.count))
  if (!rows.length) return <p className="py-6 text-center text-sm text-emerald-100/50">{empty}</p>
  return (
    <ul className="space-y-3" aria-label={label}>
      {rows.slice(0, 10).map((r) => (
        <li key={r.name} title={`${r.name}: ${r.count}`}>
          <div className="mb-1 flex justify-between gap-3 text-sm">
            <span className="truncate text-emerald-50">{r.name}</span>
            <span className="tabular-nums text-emerald-100/70">{r.count}</span>
          </div>
          <div className="h-2 rounded-full bg-forest-800">
            <div className="h-2 rounded-full bg-lime-glow" style={{ width: `${(r.count / max) * 100}%` }} />
          </div>
        </li>
      ))}
    </ul>
  )
}

type Day = ReportSummary['days'][number]

export default function ReportsPage() {
  const [today] = useState(() => ymd(new Date()))
  const [preset, setPreset] = useState<Preset>('7d')
  const [custom, setCustom] = useState<[string, string]>(() => presetRange('30d'))
  const [start, end] = preset === 'custom' ? custom : presetRange(preset)
  const report = useReport(start, end)
  const { data: industry } = useIndustry()
  const score = industry?.score_label ?? 'Score'
  const [exporting, setExporting] = useState(false)
  const [exportError, setExportError] = useState('')
  const r = report.data

  async function exportCsv() {
    setExporting(true)
    setExportError('')
    try {
      await downloadCsv(start, end)
    } catch (err) {
      setExportError(apiErrorMessage(err))
    } finally {
      setExporting(false)
    }
  }

  const days = (r?.days ?? []).map((d) => ({ ...d, label: format(parseISO(d.date), 'd MMM') }))
  const t = r?.totals

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      {/* Range + export */}
      <div className="flex flex-wrap items-center gap-3">
        <div role="radiogroup" aria-label="Date range" className="flex flex-wrap gap-1 rounded-lg border border-forest-600 bg-forest-900 p-1">
          {PRESETS.map((p) => (
            <button
              key={p.id}
              role="radio"
              aria-checked={preset === p.id}
              onClick={() => setPreset(p.id)}
              className={`rounded-md px-3 py-1.5 text-sm transition ${preset === p.id ? 'border border-gold-500 bg-forest-800 font-medium text-lime-glow' : 'border border-transparent text-emerald-100/70 hover:text-white'}`}
            >
              {p.label}
            </button>
          ))}
        </div>
        {preset === 'custom' && (
          <div className="flex items-center gap-2 text-sm text-emerald-100/70">
            <CalendarRange size={16} className="text-gold-400" />
            <input aria-label="From date" type="date" className={`${inputBase} w-40`} value={custom[0]} max={custom[1]} onChange={(e) => setCustom([e.target.value, custom[1]])} />
            to
            <input aria-label="To date" type="date" className={`${inputBase} w-40`} value={custom[1]} min={custom[0]} max={today} onChange={(e) => setCustom([custom[0], e.target.value])} />
          </div>
        )}
        <button onClick={exportCsv} disabled={exporting} className={`${btnSecondary} ml-auto`}>
          {exporting ? <LoaderCircle size={16} className="animate-spin" /> : <Download size={16} />} Export CSV
        </button>
      </div>
      {exportError && <p role="alert" className="text-sm text-red-200">{exportError}</p>}
      {report.error && <p role="alert" className="rounded-lg border border-red-400/40 bg-red-500/10 px-4 py-3 text-sm text-red-200">{apiErrorMessage(report.error)}</p>}
      {report.isLoading && <p className="text-sm text-emerald-100/60">Loading report…</p>}

      {r && t && (
        <>
          <p className="text-sm text-emerald-100/60">
            {format(parseISO(r.start), 'd MMM yyyy')} – {format(parseISO(r.end), 'd MMM yyyy')} · {r.days.length} day{r.days.length === 1 ? '' : 's'}
          </p>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <Tile
              label={`Average ${score.toLowerCase()}`}
              icon={ShieldCheck}
              title={r.score_formula}
              value={<>{t.avg_score.toFixed(0)}<span className="text-lg text-emerald-100/50">/100</span></>}
              sub={t.worst_day ? `Worst day: ${format(parseISO(t.worst_day), 'd MMM')}` : 'No violations in this period'}
            />
            <Tile label="Violations" icon={TrendingDown} value={t.violations} sub={`${t.open} still open · ${t.resolved} resolved`} />
            <Tile
              label="False alarm rate"
              icon={TriangleAlert}
              value={t.false_alarm_rate === null ? '—' : `${Math.round(t.false_alarm_rate * 100)}%`}
              sub={`${t.false_alarms} marked false alarm`}
            />
            <Tile
              label="Avg. time to resolve"
              icon={Timer}
              value={t.avg_resolution_min === null ? '—' : t.avg_resolution_min < 60 ? `${t.avg_resolution_min.toFixed(0)} min` : `${(t.avg_resolution_min / 60).toFixed(1)} h`}
              sub="From detection to resolved"
            />
          </div>

          <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
            <Panel title={`${score} by day`}>
              <div className="h-60" role="img" aria-label={`Line chart of the ${score.toLowerCase()} per day`}>
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={days} margin={{ top: 8, right: 8, left: -20, bottom: 0 }}>
                    <CartesianGrid vertical={false} stroke={GRID} />
                    <XAxis dataKey="label" tick={{ fill: AXIS, fontSize: 11 }} tickLine={false} axisLine={{ stroke: GRID }} interval="preserveStartEnd" minTickGap={16} />
                    <YAxis domain={[0, 100]} ticks={[0, 25, 50, 75, 100]} tick={{ fill: AXIS, fontSize: 11 }} tickLine={false} axisLine={false} />
                    <Tooltip
                      cursor={{ stroke: 'rgba(181,242,61,0.35)' }}
                      content={(p) => <ChartTooltip {...p} render={(d: Day) => <div className="font-semibold text-white">Score {d.score}/100 · {d.violations} violations</div>} />}
                    />
                    <Line type="monotone" dataKey="score" stroke={LIME} strokeWidth={2} dot={{ r: 4, fill: LIME, strokeWidth: 0 }} activeDot={{ r: 6 }} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </Panel>

            <Panel title="Violations by day">
              <div className="h-60" role="img" aria-label="Bar chart of violations per day">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={days} margin={{ top: 8, right: 8, left: -20, bottom: 0 }}>
                    <CartesianGrid vertical={false} stroke={GRID} />
                    <XAxis dataKey="label" tick={{ fill: AXIS, fontSize: 11 }} tickLine={false} axisLine={{ stroke: GRID }} interval="preserveStartEnd" minTickGap={16} />
                    <YAxis allowDecimals={false} tick={{ fill: AXIS, fontSize: 11 }} tickLine={false} axisLine={false} />
                    <Tooltip
                      cursor={{ fill: 'rgba(181,242,61,0.08)' }}
                      content={(p) => (
                        <ChartTooltip
                          {...p}
                          render={(d: Day) => (
                            <>
                              <div className="font-semibold text-white">{d.violations} violations</div>
                              <div className="text-emerald-100/70">{d.critical} critical · {d.warning} warning · {d.info} info</div>
                              {d.false_alarms > 0 && <div className="text-emerald-100/50">+{d.false_alarms} false alarms (not counted)</div>}
                            </>
                          )}
                        />
                      )}
                    />
                    <Bar dataKey="violations" fill={LIME} radius={[4, 4, 0, 0]} maxBarSize={28} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </Panel>
          </div>

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
            <Panel title="By violation type">
              <BarList label="Violations by type" rows={r.by_type.map((x) => ({ name: x.label, count: x.count }))} empty="No violations." />
            </Panel>
            <Panel title="By camera">
              <BarList label="Violations by camera" rows={r.by_camera} empty="No violations." />
            </Panel>
            <Panel title="By zone">
              <BarList label="Violations by zone" rows={r.by_zone} empty="No violations." />
            </Panel>
          </div>

          <Panel title="Busiest hours (all days in range)">
            <div className="h-52" role="img" aria-label="Bar chart of violations by hour of day">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={r.by_hour.map((h) => ({ ...h, label: `${String(h.hour).padStart(2, '0')}:00` }))} margin={{ top: 8, right: 8, left: -20, bottom: 0 }}>
                  <CartesianGrid vertical={false} stroke={GRID} />
                  <XAxis dataKey="label" tick={{ fill: AXIS, fontSize: 11 }} tickLine={false} axisLine={{ stroke: GRID }} interval={2} />
                  <YAxis allowDecimals={false} tick={{ fill: AXIS, fontSize: 11 }} tickLine={false} axisLine={false} />
                  <Tooltip
                    cursor={{ fill: 'rgba(181,242,61,0.08)' }}
                    content={(p) => <ChartTooltip {...p} render={(h: { count: number }) => <div className="font-semibold text-white">{h.count} violations</div>} />}
                  />
                  <Bar dataKey="count" fill={LIME} radius={[4, 4, 0, 0]} maxBarSize={22} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Panel>

          {/* Accessible table view of the daily figures */}
          <details className="rounded-xl border border-forest-700 bg-forest-900 text-sm">
            <summary className="cursor-pointer px-5 py-3 text-gold-300">Daily figures as a table</summary>
            <div className="overflow-x-auto px-5 pb-4">
              <table className="w-full min-w-[560px] text-left" aria-label="Daily figures">
                <thead className="text-xs uppercase tracking-wider text-emerald-100/50">
                  <tr>
                    {['Date', 'Score', 'Violations', 'Critical', 'Warning', 'Info', 'False alarms'].map((h) => <th key={h} className="py-2 pr-4 font-medium">{h}</th>)}
                  </tr>
                </thead>
                <tbody className="tabular-nums text-emerald-50">
                  {r.days.map((d) => (
                    <tr key={d.date} className="border-t border-forest-800">
                      <td className="py-1.5 pr-4">{format(parseISO(d.date), 'EEE d MMM')}</td>
                      <td className="pr-4">{d.score}</td>
                      <td className="pr-4">{d.violations}</td>
                      <td className="pr-4">{d.critical}</td>
                      <td className="pr-4">{d.warning}</td>
                      <td className="pr-4">{d.info}</td>
                      <td className="pr-4">{d.false_alarms}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </details>
        </>
      )}
    </div>
  )
}
