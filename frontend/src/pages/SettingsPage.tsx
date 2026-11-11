import { Bell, BellOff, Database, DatabaseZap, Volume2, VolumeX } from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { SEVERITY_LABELS, type Severity } from '../api/events'
import { useAppSettings, useSaveAppSettings, type AppSettings } from '../api/settings'
import SeverityBadge from '../components/SeverityBadge'
import { apiErrorMessage } from '../lib/api'
import { useAlerts } from '../lib/alerts'

const SEVERITIES: Severity[] = ['critical', 'warning', 'info']

function Switch({ on, label, disabled, onChange }: { on: boolean; label: string; disabled?: boolean; onChange: (on: boolean) => void }) {
  return (
    <button
      role="switch"
      aria-checked={on}
      aria-label={label}
      disabled={disabled}
      onClick={() => onChange(!on)}
      className={`relative h-6 w-11 shrink-0 rounded-full transition disabled:cursor-not-allowed disabled:opacity-40 ${on ? 'bg-lime-glow' : 'bg-forest-700'}`}
    >
      <span className={`absolute left-0.5 top-0.5 h-5 w-5 rounded-full transition ${on ? 'translate-x-5 bg-forest-950' : 'bg-emerald-100/70'}`} />
    </button>
  )
}

function Row({ icon, title, text, children }: { icon: ReactNode; title: string; text: string; children: ReactNode }) {
  return (
    <div className="flex items-start gap-4 border-b border-forest-700 px-5 py-4 last:border-b-0">
      <span className="mt-0.5 text-lime-glow">{icon}</span>
      <div className="min-w-0 flex-1">
        <h3 className="font-medium text-white">{title}</h3>
        <p className="mt-0.5 text-sm text-emerald-100/60">{text}</p>
      </div>
      {children}
    </div>
  )
}

export default function SettingsPage() {
  const { data: s, isLoading, error } = useAppSettings()
  const save = useSaveAppSettings()
  const { muted, setMuted } = useAlerts()
  // Clicks not saved yet, held in this page's own state so the controls switch in the same render
  // as the click (the shared cache notifies a moment later, which would make them flicker back).
  const [unsaved, setUnsaved] = useState<Partial<AppSettings>>({})
  const current = s && { ...s, ...unsaved }

  function change(data: Partial<AppSettings>) {
    setUnsaved((u) => ({ ...u, ...data }))
    save.mutate(data, { onSettled: () => setUnsaved({}) }) // fires after the last queued save
  }

  function toggleSeverity(sev: Severity, on: boolean) {
    if (!current) return
    const next = on ? [...current.notify_severities, sev] : current.notify_severities.filter((x) => x !== sev)
    change({ notify_severities: next })
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <p className="text-sm text-emerald-100/60">Switch event recording and alerts on or off for the whole system.</p>
      {isLoading && <p className="text-sm text-emerald-100/60">Loading settings…</p>}
      {error && <p role="alert" className="text-sm text-red-200">{apiErrorMessage(error)}</p>}

      {current && (
        <>
          <section aria-labelledby="events-h" className="rounded-xl border border-gold-500/60 bg-forest-900">
            <h2 id="events-h" className="border-b border-forest-700 px-5 py-3 text-xs font-semibold uppercase tracking-wider text-gold-300">Events</h2>
            <Row
              icon={current.events_enabled ? <Database size={20} /> : <DatabaseZap size={20} className="text-red-300" />}
              title="Record events"
              text={
                current.events_enabled
                  ? 'Detected violations are saved to Events & Alerts with a snapshot.'
                  : 'Off: detection still draws boxes on Live View, but nothing is saved and no alerts are sent.'
              }
            >
              <Switch on={current.events_enabled} label="Record events" onChange={(on) => change({ events_enabled: on })} />
            </Row>
          </section>

          <section aria-labelledby="notif-h" className="rounded-xl border border-gold-500/60 bg-forest-900">
            <h2 id="notif-h" className="border-b border-forest-700 px-5 py-3 text-xs font-semibold uppercase tracking-wider text-gold-300">Notifications</h2>
            <Row
              icon={current.notifications_enabled ? <Bell size={20} /> : <BellOff size={20} className="text-red-300" />}
              title="Pop-up alerts"
              text={
                current.notifications_enabled
                  ? 'New events pop up in the top-right corner.'
                  : 'Off: events are still saved; see them in Events & Alerts.'
              }
            >
              <Switch
                on={current.notifications_enabled}
                label="Pop-up alerts"
                onChange={(on) => change({ notifications_enabled: on })}
              />
            </Row>
            <Row icon={<span className="block w-5" />} title="Alert for" text="Which severities pop up.">
              <fieldset className="flex flex-wrap justify-end gap-3" disabled={!current.notifications_enabled}>
                <legend className="sr-only">Alert for</legend>
                {SEVERITIES.map((sev) => (
                  <label key={sev} className="flex cursor-pointer items-center gap-1.5 has-[:disabled]:cursor-not-allowed has-[:disabled]:opacity-40">
                    <input
                      type="checkbox"
                      className="accent-lime-400"
                      checked={current.notify_severities.includes(sev)}
                      onChange={(e) => toggleSeverity(sev, e.target.checked)}
                      aria-label={SEVERITY_LABELS[sev]}
                    />
                    <SeverityBadge severity={sev} />
                  </label>
                ))}
              </fieldset>
            </Row>
            <Row
              icon={muted ? <VolumeX size={20} className="text-red-300" /> : <Volume2 size={20} />}
              title="Alert sound"
              text="Beeps for critical (3) and warning (1) alerts. Saved in this browser only."
            >
              <Switch on={!muted} label="Alert sound" disabled={!current.notifications_enabled} onChange={(on) => setMuted(!on)} />
            </Row>
          </section>
          {save.isError && <p role="alert" className="text-sm text-red-200">{apiErrorMessage(save.error)}</p>}
        </>
      )}
    </div>
  )
}
