import { Clock, LoaderCircle, Map as MapIcon, ScanFace, TriangleAlert } from 'lucide-react'
import { useState, type FormEvent, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import type { Camera } from '../../api/cameras'
import { useSaveDetectionConfig, type CheckKey, type DetectionConfig } from '../../api/detection'
import { useIndustry, type ZoneRule } from '../../api/industry'
import { useZones } from '../../api/zones'
import { apiErrorMessage } from '../../lib/api'
import Modal, { btnPrimary, btnSecondary, inputBase } from '../Modal'

/** Does the camera have the zones this rule needs? (Every group needs at least one of its types.) */
function zonesReady(rule: ZoneRule, types: Set<string>) {
  return rule.zone_types.every((group) => group.some((t) => types.has(t)))
}

function NumberField({ label, hint, value, onChange, min, max, step }: {
  label: string; hint: ReactNode; value: string; onChange: (v: string) => void; min: number; max: number; step: number
}) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-xs font-medium uppercase tracking-wider text-gold-300">{label}</span>
      <input className={inputBase} type="number" min={min} max={max} step={step} value={value} onChange={(e) => onChange(e.target.value)} required />
      <span className="mt-1 block text-xs text-emerald-100/50">{hint}</span>
    </label>
  )
}

export default function DetectionSettingsModal({ camera, config, onClose }: { camera: Camera; config: DetectionConfig; onClose: () => void }) {
  const save = useSaveDetectionConfig()
  const { data: industry } = useIndustry()
  const zones = useZones(camera.id)
  const zoneTypes = new Set((zones.data ?? []).map((z) => z.zone_type))
  const [enabled, setEnabled] = useState(config.enabled)
  const [checks, setChecks] = useState<CheckKey[]>(config.checks)
  const [minDuration, setMinDuration] = useState(String(config.min_duration_s))
  const [cooldownMin, setCooldownMin] = useState(String(config.cooldown_s / 60))
  const [washSeconds, setWashSeconds] = useState(String(config.handwash_min_s))
  const [washValidMin, setWashValidMin] = useState(String(config.wash_valid_min))
  const [tableMin, setTableMin] = useState(String(config.table_clear_min))

  const ppe = industry?.ppe_checks ?? []
  const rules = industry?.zone_rules ?? []
  const toggle = (check: CheckKey) => setChecks((cs) => (cs.includes(check) ? cs.filter((c) => c !== check) : [...cs, check]))

  async function submit(e: FormEvent) {
    e.preventDefault()
    await save.mutateAsync({
      ...config,
      enabled,
      checks,
      min_duration_s: Number(minDuration),
      cooldown_s: Math.round(Number(cooldownMin) * 60),
      handwash_min_s: Number(washSeconds),
      wash_valid_min: Number(washValidMin),
      table_clear_min: Number(tableMin),
    })
    onClose()
  }

  const anyHandwash = checks.includes('handwash_skipped') || checks.includes('handwash_short')

  return (
    <Modal
      title={`Detection · ${camera.name}`}
      onClose={onClose}
      footer={
        <>
          <button type="button" onClick={onClose} className={btnSecondary}>Cancel</button>
          <button type="submit" form="detection-form" disabled={save.isPending} className={btnPrimary}>
            {save.isPending && <LoaderCircle size={14} className="animate-spin" />} Save
          </button>
        </>
      }
    >
      <form id="detection-form" onSubmit={submit} className="space-y-5">
        <label className="flex cursor-pointer items-center justify-between rounded-lg border border-forest-600 px-3 py-2.5">
          <span className="flex items-center gap-2">
            <ScanFace size={18} className="text-lime-glow" />
            <span>
              <span className="block text-sm text-white">Detect violations</span>
              <span className="block text-xs text-emerald-100/50">Keeps this camera open and analyses it continuously.</span>
            </span>
          </span>
          <input type="checkbox" checked={enabled} onChange={(e) => setEnabled(e.target.checked)} className="peer sr-only" />
          <span className="relative h-6 w-11 shrink-0 rounded-full bg-forest-700 transition after:absolute after:left-0.5 after:top-0.5 after:h-5 after:w-5 after:rounded-full after:bg-emerald-100/70 after:transition peer-checked:bg-lime-glow peer-checked:after:translate-x-5 peer-checked:after:bg-forest-950 peer-focus-visible:ring-2 peer-focus-visible:ring-lime-glow/50" />
        </label>

        {ppe.length > 0 && (
          <fieldset>
            <legend className="mb-2 text-xs font-medium uppercase tracking-wider text-gold-300">Staff must wear</legend>
            <div className="grid grid-cols-2 gap-2">
              {ppe.map((check) => (
                <label key={check.key} className="flex cursor-pointer items-center gap-2 rounded-lg border border-forest-600 px-3 py-2 text-sm text-emerald-50 hover:border-gold-500">
                  <input type="checkbox" checked={checks.includes(check.key)} onChange={() => toggle(check.key)} className="h-4 w-4 accent-lime-400" />
                  {check.item}
                </label>
              ))}
            </div>
          </fieldset>
        )}

        <div className="grid grid-cols-2 gap-4">
          <NumberField
            label="Alert after (seconds)"
            hint={checks.includes('restricted_area') ? 'How long a missing item, or a person in a restricted area, must last.' : 'How long a missing item must last. Filters out brief glitches.'}
            value={minDuration} onChange={setMinDuration} min={1} max={300} step={1}
          />
          <NumberField label="Repeat after (minutes)" hint="Before the same alert fires again on this camera." value={cooldownMin} onChange={setCooldownMin} min={0.5} max={60} step={0.5} />
        </div>

        {rules.length > 0 && (
          <fieldset className="space-y-2 border-t border-forest-700 pt-4">
            <legend className="mb-2 flex items-center gap-1.5 text-xs font-medium uppercase tracking-wider text-gold-300">
              <MapIcon size={14} /> Zone rules
            </legend>
            {rules.map((rule) => {
              const ready = zonesReady(rule, zoneTypes)
              return (
                <label key={rule.key} className="flex cursor-pointer items-start gap-2 rounded-lg border border-forest-600 px-3 py-2 text-sm text-emerald-50 hover:border-gold-500">
                  <input type="checkbox" checked={checks.includes(rule.key)} onChange={() => toggle(rule.key)} className="mt-0.5 h-4 w-4 accent-lime-400" />
                  <span className="flex-1">
                    {rule.label}
                    <span className={`mt-0.5 flex items-center gap-1 text-xs ${ready ? 'text-emerald-100/50' : 'text-amber-200'}`}>
                      {!ready && <TriangleAlert size={12} />}
                      {ready ? rule.needs.replace('Needs', 'Uses') : `${rule.needs} — none drawn yet`}
                    </span>
                  </span>
                </label>
              )
            })}
            {rules.some((r) => checks.includes(r.key) && !zonesReady(r, zoneTypes)) && (
              <p className="text-xs text-emerald-100/60">
                Draw the missing zones on the <Link to="/zones" className="text-gold-300 underline hover:text-lime-glow">Zones page</Link>. Rules without their zones simply do nothing.
              </p>
            )}
          </fieldset>
        )}

        {(anyHandwash || checks.includes('table_not_cleared')) && (
          <div className="grid grid-cols-3 gap-3">
            {anyHandwash && (
              <>
                <NumberField label="Wash at least (s)" hint="A proper hand wash." value={washSeconds} onChange={setWashSeconds} min={5} max={120} step={1} />
                <NumberField label="Wash valid (min)" hint="Counts before prep for this long." value={washValidMin} onChange={setWashValidMin} min={1} max={480} step={1} />
              </>
            )}
            {checks.includes('table_not_cleared') && (
              <NumberField label="Clear table within (min)" hint="After guests leave." value={tableMin} onChange={setTableMin} min={0.1} max={120} step={0.1} />
            )}
          </div>
        )}

        {!!industry?.planned.length && (
          <section aria-label="Coming soon" className="border-t border-forest-700 pt-4">
            <h3 className="mb-2 flex items-center gap-1.5 text-xs font-medium uppercase tracking-wider text-gold-300">
              <Clock size={14} /> Coming soon for {industry.name}
            </h3>
            <ul className="flex flex-wrap gap-1.5">
              {industry.planned.map((p) => (
                <li key={p} className="rounded-md border border-dashed border-forest-600 px-2 py-1 text-xs text-emerald-100/50">{p}</li>
              ))}
            </ul>
          </section>
        )}

        {enabled && checks.length === 0 && <p className="text-xs text-amber-200">Pick at least one item or rule, or nothing will be checked.</p>}
        {save.isError && <p role="alert" className="text-sm text-red-200">{apiErrorMessage(save.error)}</p>}
      </form>
    </Modal>
  )
}
