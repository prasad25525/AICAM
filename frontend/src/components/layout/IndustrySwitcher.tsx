import { Check, ChevronDown, LoaderCircle } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useIndustries, useIndustry, useSwitchIndustry } from '../../api/industry'
import { apiErrorMessage } from '../../lib/api'
import IndustryIcon from '../IndustryIcon'

/** The active industry in the top bar; a menu to switch (not on installations locked to one industry). */
export default function IndustrySwitcher() {
  const { data: active } = useIndustry()
  const { data: list } = useIndustries()
  const switchTo = useSwitchIndustry()
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const close = (e: MouseEvent) => !ref.current?.contains(e.target as Node) && setOpen(false)
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [open])

  if (!active) return null
  const canSwitch = !active.locked && (list?.industries.length ?? 0) > 1
  const badge = (
    <>
      <IndustryIcon name={active.icon} size={16} className="text-lime-glow" />
      <span className="hidden md:inline">{active.name}</span>
    </>
  )

  if (!canSwitch) {
    return (
      <div className="flex items-center gap-2 rounded-lg border border-forest-600 px-3 py-1.5 text-sm text-emerald-50" aria-label={`Industry: ${active.name}`}>
        {badge}
      </div>
    )
  }

  async function choose(key: string) {
    setOpen(false)
    if (key === active?.key) return
    await switchTo.mutateAsync(key)
    navigate('/dashboard')
  }

  const target = list?.industries.find((i) => i.key === switchTo.variables)

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-2 rounded-lg border border-forest-600 px-3 py-1.5 text-sm text-emerald-50 hover:border-gold-500"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={`Industry: ${active.name}. Switch industry`}
      >
        {badge}
        <ChevronDown size={14} className="text-emerald-100/50" />
      </button>

      {open && (
        <div role="menu" aria-label="Switch industry" className="absolute right-0 z-30 mt-2 w-64 overflow-hidden rounded-xl border border-gold-500/60 bg-forest-900 py-1 shadow-[0_8px_30px_rgba(0,0,0,0.5)]">
          <p className="px-3 py-1.5 text-[10px] font-semibold uppercase tracking-wider text-gold-300">Switch industry</p>
          {list?.industries.map((i) => (
            <button
              key={i.key}
              role="menuitemradio"
              aria-checked={i.key === active.key}
              onClick={() => choose(i.key)}
              className="flex w-full items-start gap-2.5 px-3 py-2 text-left hover:bg-forest-800"
            >
              <IndustryIcon name={i.icon} size={18} className="mt-0.5 shrink-0 text-lime-glow" />
              <span className="min-w-0 flex-1">
                <span className="block text-sm text-white">{i.name}</span>
                <span className="block text-xs text-emerald-100/50">{i.description}</span>
              </span>
              {i.key === active.key && <Check size={16} className="mt-0.5 text-lime-glow" />}
            </button>
          ))}
        </div>
      )}

      {switchTo.isPending && (
        <div role="status" className="fixed inset-0 z-[70] flex items-center justify-center bg-forest-950/80 backdrop-blur-sm">
          <div className="flex items-center gap-3 rounded-xl border border-gold-500/60 bg-forest-900 px-5 py-4 text-sm text-white">
            <LoaderCircle size={18} className="animate-spin text-lime-glow" /> Switching to {target?.name ?? 'industry'}…
          </div>
        </div>
      )}
      {switchTo.isError && (
        <p role="alert" className="absolute right-0 mt-2 w-64 rounded-lg border border-red-400/40 bg-red-500/10 px-3 py-2 text-xs text-red-200">
          {apiErrorMessage(switchTo.error)}
        </p>
      )}
    </div>
  )
}
