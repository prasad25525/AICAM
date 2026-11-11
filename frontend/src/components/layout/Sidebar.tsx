import { useQuery } from '@tanstack/react-query'
import { Cpu, ScanEye, ScanFace, X } from 'lucide-react'
import { NavLink } from 'react-router-dom'
import { useDetectionStatus } from '../../api/detection'
import { useOpenEventCount } from '../../api/events'
import { api } from '../../lib/api'
import AzkashineLogo from '../AzkashineLogo'
import { NAV_ITEMS } from './nav'

interface SystemInfo {
  cuda: boolean
  gpu: string | null
}

export default function Sidebar({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { data: system } = useQuery({
    queryKey: ['system-info'],
    queryFn: async () => (await api.get<SystemInfo>('/system/info')).data,
  })
  const { data: openEvents } = useOpenEventCount()
  const { data: detection } = useDetectionStatus()
  const engineState = detection?.engine.state
  const activeCameras = detection?.cameras.length ?? 0
  const detecting = engineState === 'ready' && activeCameras > 0

  return (
    <>
      {/* Mobile backdrop */}
      <div
        onClick={onClose}
        className={`fixed inset-0 z-30 bg-black/60 lg:hidden ${open ? 'block' : 'hidden'}`}
      />

      <aside
        className={`fixed inset-y-0 left-0 z-40 flex w-64 flex-col border-r border-gold-500/60 bg-forest-900 transition-transform lg:static lg:translate-x-0 ${
          open ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <div className="flex h-16 items-center justify-between border-b border-gold-500/40 px-5">
          <div className="flex items-center gap-2.5">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-gold-500 bg-forest-800 text-lime-glow">
              <ScanEye size={20} />
            </div>
            <div className="leading-tight">
              <span className="block text-lg font-semibold tracking-tight text-white">
                Vigil<span className="text-lime-glow">Siddhi</span>
              </span>
              <span className="block text-[10px] font-medium uppercase tracking-[0.14em] text-gold-300">A Vision AI Platform</span>
            </div>
          </div>
          <button onClick={onClose} className="rounded p-1 text-emerald-100/60 hover:text-lime-glow lg:hidden" aria-label="Close menu">
            <X size={18} />
          </button>
        </div>

        <nav className="flex-1 space-y-1 p-3">
          {NAV_ITEMS.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              onClick={onClose}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-lg border px-3 py-2.5 text-sm transition ${
                  isActive
                    ? 'border-gold-500 bg-forest-800 font-medium text-lime-glow shadow-[inset_3px_0_0_var(--color-lime-glow)]'
                    : 'border-transparent text-emerald-100/70 hover:border-forest-600 hover:bg-forest-800/60 hover:text-white'
                }`
              }
            >
              <Icon size={18} />
              {label}
              {to === '/events' && !!openEvents && (
                <span className="ml-auto rounded-full bg-lime-glow px-2 py-0.5 text-xs font-semibold tabular-nums text-forest-950" aria-label={`${openEvents} open events`}>
                  {openEvents > 99 ? '99+' : openEvents}
                </span>
              )}
            </NavLink>
          ))}
        </nav>

        <div className="m-3 rounded-lg border border-forest-600 bg-forest-950/60 p-3 text-xs">
          <div className="mb-1 flex items-center gap-1.5 font-medium text-gold-300">
            <Cpu size={14} /> Inference engine
          </div>
          <div className="flex items-center gap-2 text-emerald-100/70">
            <span className={`h-2 w-2 rounded-full ${system?.cuda ? 'bg-lime-glow' : 'bg-amber-400'}`} />
            {system ? (system.gpu ?? 'CPU only') : 'Checking…'}
          </div>
          <div className="mt-1.5 flex items-center gap-2 text-emerald-100/70" aria-label="Detection status">
            <ScanFace size={12} className={detecting ? 'text-lime-glow' : engineState === 'error' ? 'text-red-300' : 'text-emerald-100/40'} />
            {detecting && `Detecting on ${activeCameras} camera${activeCameras === 1 ? '' : 's'}`}
            {engineState === 'loading' && 'Loading models…'}
            {engineState === 'error' && 'Detection error'}
            {!detecting && engineState !== 'loading' && engineState !== 'error' && 'Detection off'}
          </div>
        </div>

        <div className="mx-3 mb-3 flex items-center justify-between gap-2">
          <span className="text-[10px] uppercase tracking-wider text-emerald-100/40">Powered by</span>
          <AzkashineLogo className="h-7" />
        </div>
      </aside>
    </>
  )
}
